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

    cur.close()
    conn.close()

    return {
        "mttr_by_cluster": mttr_data,
        "resolution_stats": resolution_stats,
        "llm_accuracy": llm_accuracy,
        "top_recurring_alerts": recurring,
    }
