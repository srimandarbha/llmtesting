import psycopg2
import hashlib
from agents.base_agent import BaseSreAgent

class TelemetryAggregatorAgent(BaseSreAgent):
    """
    Agent 1: Telemetry Aggregator (0% LLM)
    Uses Kafka event JSON metadata to query database tables for cluster info, active Red Hat cases,
    and alert reoccurrence counts over the past 7 days.
    """
    def __init__(self):
        super().__init__("Telemetry Aggregator")

    def execute(self, state, db_config):
        print(f"\n[{self.name}] Connecting to PostgreSQL to aggregate alert telemetry...")
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Ingest Kafka payload fields from shared state
        cluster_id = state.get("cluster_id")
        namespace = state.get("namespace")
        alertname = state.get("alertname")
        
        # 1. Resolve alert fingerprint from DB
        cur.execute("""
            SELECT fingerprint, severity FROM alert_occurrences 
            WHERE alertname = %s AND namespace = %s AND cluster_id = %s;
        """, (alertname, namespace, cluster_id))
        row = cur.fetchone()
        
        if row:
            fingerprint = row[0]
            severity = row[1]
        else:
            # Fallback generation
            raw_str = f"{alertname}{namespace}prometheus{cluster_id}"
            fingerprint = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
            severity = "warning"
            
        state["alert_fingerprint"] = fingerprint
        state["severity"] = severity

        # 2. Fetch cluster metadata
        cur.execute("""
            SELECT name, description, openshift_version, environment 
            FROM clusters WHERE cluster_id = %s;
        """, (cluster_id,))
        cluster_info = cur.fetchone()
        cluster_name = cluster_info[0] if cluster_info else "Unknown"
        cluster_description = cluster_info[1] if cluster_info else "Unknown"
        openshift_version = cluster_info[2] if cluster_info else "4.14.0"
        environment = cluster_info[3] if cluster_info else "production"

        # 3. Query reoccurrence count in the last 7 days
        cur.execute("""
            SELECT COUNT(*) FROM incidents 
            WHERE alert_fingerprint = %s AND sys_created_on > NOW() - INTERVAL '7 days';
        """, (fingerprint,))
        occurrences_last_7_days = cur.fetchone()[0] or 0

        # 4. Query recurrence aggregates
        cur.execute("""
            SELECT total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at
            FROM recurrence_intelligence WHERE fingerprint = %s;
        """, (fingerprint,))
        rec_info = cur.fetchone()
        
        total_occurrences = rec_info[0] if rec_info else 1
        total_incidents = rec_info[1] if rec_info else 1
        reopen_count = rec_info[2] if rec_info else 0
        mttr_seconds = rec_info[3] if rec_info else 0
        resolution_quality_score = float(rec_info[4]) if rec_info and rec_info[4] is not None else 100.0
        last_reopened_at = str(rec_info[5]) if rec_info and rec_info[5] else None

        # 5. Fetch associated Red Hat case details
        cur.execute("""
            SELECT c.case_id, c.title, c.status, c.resolution
            FROM redhat_cases c
            JOIN incidents i ON i.redhat_case_id = c.case_id
            WHERE i.alert_fingerprint = %s;
        """, (fingerprint,))
        cases = cur.fetchall()
        
        rh_cases = []
        for case in cases:
            rh_cases.append({
                "case_id": case[0],
                "title": case[1],
                "status": case[2],
                "resolution": case[3]
            })

        # 6. Fetch SNOW Sync Staleness and Work Notes
        snow_db_staleness_seconds = 300 # Default fallback
        recent_human_activity = False
        
        try:
            cur.execute("""
                SELECT EXTRACT(EPOCH FROM (NOW() - last_sync_time)) 
                FROM snow_sync_status LIMIT 1;
            """)
            sync_row = cur.fetchone()
            if sync_row and sync_row[0] is not None:
                snow_db_staleness_seconds = int(sync_row[0])
                
            # Check for recent human work notes in the staleness window
            cur.execute("""
                SELECT COUNT(*) FROM incident_work_notes
                WHERE alert_fingerprint = %s AND created_by != 'system' 
                AND created_at >= NOW() - INTERVAL '%s seconds';
            """, (fingerprint, snow_db_staleness_seconds + 600))
            human_notes_row = cur.fetchone()
            if human_notes_row and human_notes_row[0] > 0:
                recent_human_activity = True
        except Exception as e:
            print(f"[{self.name}] Warning: Could not fetch SNOW staleness metrics: {e}")

        # 7. Fetch Local Agent Action Log (High-Speed Circuit Breaker)
        agent_remediations_last_24h = 0
        last_agent_action_time = None
        
        try:
            # Check how many times agent fixed this in last 24h
            cur.execute("""
                SELECT COUNT(*) FROM agent_action_log
                WHERE alert_fingerprint = %s AND status = 'SUCCESS'
                AND created_at >= NOW() - INTERVAL '24 hours';
            """, (fingerprint,))
            count_row = cur.fetchone()
            if count_row:
                agent_remediations_last_24h = count_row[0]
                
            # Check most recent action
            cur.execute("""
                SELECT created_at FROM agent_action_log
                WHERE alert_fingerprint = %s 
                ORDER BY created_at DESC LIMIT 1;
            """, (fingerprint,))
            last_action_row = cur.fetchone()
            if last_action_row:
                last_agent_action_time = last_action_row[0] # Datetime object
        except Exception as e:
            print(f"[{self.name}] Warning: Could not fetch local agent action log: {e}")

        cur.close()
        conn.close()

        # Update Blackboard State
        state["operational_history"] = {
            "cluster_name": cluster_name,
            "cluster_description": cluster_description,
            "cluster_environment": environment,
            "openshift_version": openshift_version,
            "occurrences_last_7_days": occurrences_last_7_days,
            "total_alert_occurrences": total_occurrences,
            "total_incidents_for_alert": total_incidents,
            "reopen_count": reopen_count,
            "average_mttr_seconds": mttr_seconds,
            "resolution_quality_score": resolution_quality_score,
            "last_reopened_at": last_reopened_at,
            "associated_redhat_cases": rh_cases,
            "snow_db_staleness_seconds": snow_db_staleness_seconds,
            "recent_human_activity": recent_human_activity,
            "agent_remediations_last_24h": agent_remediations_last_24h,
            "last_agent_action_time": last_agent_action_time
        }
        
        print(f"[{self.name}] Telemetry loaded. Weekly Frequency: {occurrences_last_7_days} incidents. Quality: {resolution_quality_score}%.")
        return state
