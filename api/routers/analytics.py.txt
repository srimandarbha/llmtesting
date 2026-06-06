"""Analytics router — aggregated metrics for the Analytics page."""

from __future__ import annotations

import psycopg2
from fastapi import APIRouter

from agents.config import DATABASE_TARGET
from api.schemas import AnalyticsSummaryOut

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_analytics_summary():
    """
    Returns aggregated analytics data for:
    - MTTR by cluster/alert
    - Auto-resolved vs human-intervened breakdown
    - LLM accuracy (approved as-is / edited / rejected)
    - Top recurring alerts
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    # 1. MTTR per cluster + alert (resolved incidents only)
    cur.execute(
        """
        SELECT cluster, alert_name,
               AVG(EXTRACT(EPOCH FROM (resolved_at - created_at))) AS avg_mttr_seconds,
               COUNT(*) AS incident_count
        FROM incidents_v2
        WHERE status = 'RESOLVED' AND resolved_at IS NOT NULL
        GROUP BY cluster, alert_name
        ORDER BY avg_mttr_seconds DESC
        LIMIT 20;
        """
    )
    mttr_rows = cur.fetchall()
    mttr_data = [
        {"cluster": r[0], "alert_name": r[1], "avg_mttr_seconds": float(r[2] or 0), "incident_count": r[3]}
        for r in mttr_rows
    ]

    # 2. Auto-resolved vs human-intervened
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'RESOLVED' AND risk_tier = 'LOW') AS auto_resolved,
            COUNT(*) FILTER (WHERE status IN ('RESOLVED','REJECTED') AND risk_tier = 'HIGH') AS human_intervened,
            COUNT(*) FILTER (WHERE status IN ('RESOLVED','REJECTED','ESCALATED','FAILED')) AS total
        FROM incidents_v2;
        """
    )
    res_row = cur.fetchone()
    auto_resolved = res_row[0] or 0
    human_intervened = res_row[1] or 0
    total_closed = res_row[2] or 1  # avoid div-by-zero

    resolution_stats = {
        "auto_resolved": auto_resolved,
        "human_intervened": human_intervened,
        "total": total_closed,
        "auto_resolved_pct": round(auto_resolved / total_closed * 100, 1),
        "human_intervened_pct": round(human_intervened / total_closed * 100, 1),
    }

    # 3. LLM accuracy: approved-as-is vs edited vs rejected
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE action = 'APPROVED') AS approved_as_is,
            COUNT(*) FILTER (WHERE action = 'EDITED') AS edited,
            COUNT(*) FILTER (WHERE action = 'REJECTED') AS rejected,
            COUNT(*) AS total_high_risk
        FROM human_actions;
        """
    )
    acc_row = cur.fetchone()
    llm_accuracy = {
        "approved_as_is": acc_row[0] or 0,
        "edited_before_approve": acc_row[1] or 0,
        "rejected": acc_row[2] or 0,
        "total_high_risk": acc_row[3] or 0,
    }

    # 4. Top recurring alert types (candidates to promote to LOW tier)
    cur.execute(
        """
        SELECT alert_name, cluster, COUNT(*) AS occurrences
        FROM incidents_v2
        WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY alert_name, cluster
        ORDER BY occurrences DESC
        LIMIT 10;
        """
    )
    recurring = [
        {"alert_name": r[0], "cluster": r[1], "occurrences_30d": r[2]}
        for r in cur.fetchall()
    ]

    # 5. Flapping Alerts (Nuisance)
    cur.execute(
        """
        SELECT a.alertname, a.cluster_id, SUM(i.flapping_count) as total_flapping, MAX(COALESCE(r.reopen_count, 0)) as reopen_count
        FROM incidents i
        JOIN alert_occurrences a ON i.alert_fingerprint = a.fingerprint
        LEFT JOIN recurrence_intelligence r ON r.fingerprint = a.fingerprint
        GROUP BY a.alertname, a.cluster_id
        HAVING SUM(i.flapping_count) > 0 OR MAX(COALESCE(r.reopen_count, 0)) > 0
        ORDER BY (SUM(i.flapping_count) + MAX(COALESCE(r.reopen_count, 0))) DESC
        LIMIT 10;
        """
    )
    flapping = [
        {"alert_name": r[0], "cluster": r[1], "flapping_count": int(r[2]), "reopen_count": int(r[3])}
        for r in cur.fetchall()
    ]

    # 6. SRE Sentiment Trend
    cur.execute(
        """
        SELECT TO_CHAR(sys_updated_on, 'YYYY-MM-DD') as date, AVG(sentiment_score), COUNT(*) 
        FROM incidents 
        WHERE state IN ('Resolved', 'Closed')
        GROUP BY TO_CHAR(sys_updated_on, 'YYYY-MM-DD')
        ORDER BY date ASC;
        """
    )
    sentiment_trend = [
        {"date": r[0], "average_score": float(r[1]), "total_resolutions": int(r[2])}
        for r in cur.fetchall()
    ]

    # 7. Red Hat Case Summary
    cur.execute(
        """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'Open') AS open_cases,
            COUNT(*) FILTER (WHERE severity IN ('Severity 1 (Urgent)', 'Severity 2 (High)'))::FLOAT / NULLIF(COUNT(*), 0) AS critical_pct,
            AVG(EXTRACT(EPOCH FROM (closed_on - created_on)))/86400.0 AS avg_mttr_days
        FROM redhat_cases;
        """
    )
    rh_row = cur.fetchone()
    rh_summary = {
        "open_cases": rh_row[0] or 0,
        "critical_escalation_pct": round((rh_row[1] or 0) * 100, 1),
        "avg_vendor_mttr_days": round(rh_row[2] or 0, 1)
    }

    # 8. Component Incidents (Problematic Components)
    cur.execute(
        """
        SELECT a.operator_component, COUNT(i.sys_id)
        FROM incidents i
        JOIN alert_occurrences a ON i.alert_fingerprint = a.fingerprint
        GROUP BY a.operator_component
        ORDER BY COUNT(i.sys_id) DESC
        LIMIT 10;
        """
    )
    components = [
        {"component": r[0], "incident_count": int(r[1])}
        for r in cur.fetchall()
    ]

    # 9. Fleet Risk (CVE)
    cur.execute("SELECT cluster_id, openshift_version FROM clusters")
    clusters_info = cur.fetchall()
    total_risk = 0
    critical_cves_active = 0
    for c_id, ver in clusters_info:
        cur.execute("SELECT severity FROM rhokp_cve_knowledge WHERE affected_versions @> %s", (f'"{ver}"',))
        cves = cur.fetchall()
        score = sum({"Critical": 10, "Important": 5, "Moderate": 2, "Low": 1}.get(c[0], 1) for c in cves)
        total_risk += min(100, int((score / 30) * 100))
        critical_cves_active += sum(1 for c in cves if c[0] == "Critical")
        
    fleet_risk = {
        "average_risk_pct": int(total_risk / len(clusters_info)) if clusters_info else 0,
        "critical_cves_active": critical_cves_active
    }

    # 10. Environment Distribution
    cur.execute(
        """
        SELECT c.environment, COUNT(i.sys_id)
        FROM incidents i
        JOIN clusters c ON i.cluster_id = c.cluster_id
        GROUP BY c.environment;
        """
    )
    env_dist = [
        {"environment": r[0] or "unknown", "incident_count": int(r[1])}
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return {
        "mttr_by_cluster": mttr_data,
        "resolution_stats": resolution_stats,
        "llm_accuracy": llm_accuracy,
        "top_recurring_alerts": recurring,
        "flapping_alerts": flapping,
        "sentiment_trend": sentiment_trend,
        "redhat_cases_summary": rh_summary,
        "component_incidents": components,
        "fleet_risk": fleet_risk,
        "environment_distribution": env_dist
    }
