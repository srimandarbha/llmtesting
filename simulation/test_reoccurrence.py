import psycopg2
import hashlib
import json
import subprocess
from datetime import datetime, timedelta

DATABASE_TARGET = {
    "dbname": "rhokp",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

def generate_fingerprint(alertname, namespace, operator_component, cluster_id):
    raw_str = f"{alertname}{namespace}{operator_component}{cluster_id}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def main():
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    
    # Define test parameters
    cluster_id = "staging-us-east-1"
    alertname = "CoreDNSErrorsHigh"
    namespace = "openshift-dns"
    operator_component = "cluster-dns-operator"
    
    # 1. Generate fingerprint
    fingerprint = generate_fingerprint(alertname, namespace, operator_component, cluster_id)
    print(f"Test Fingerprint: {fingerprint}")
    
    # Ensure cluster exists
    cur.execute("""
        INSERT INTO clusters (cluster_id, name, openshift_version, environment)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (cluster_id) DO NOTHING;
    """, (cluster_id, "Staging US East", "4.15.2", "staging"))
    
    # Ensure alert occurrence exists
    cur.execute("""
        INSERT INTO alert_occurrences (fingerprint, alertname, namespace, operator_component, cluster_id, severity, occurrence_count, active, first_seen, last_seen)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET active = TRUE;
    """, (fingerprint, alertname, namespace, operator_component, cluster_id, "warning", 10, True, datetime.now() - timedelta(days=10), datetime.now()))
    
    # 2. Insert 6 incidents in the last 7 days (e.g. 1 day ago to 6 days ago)
    # We clear any existing incidents for this fingerprint first to have a clean test state
    cur.execute("DELETE FROM incidents WHERE alert_fingerprint = %s;", (fingerprint,))
    
    for i in range(1, 7):
        sys_id = f"testinc0000000000000000000000{i}"
        number = f"TINC000000{i}"
        created_time = datetime.now() - timedelta(days=i, hours=2)
        short_desc = f"Alert '{alertname}' firing in namespace '{namespace}' on cluster '{cluster_id}'"
        
        # Insert incident
        cur.execute("""
            INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (sys_id, number, "Resolved", created_time, created_time + timedelta(hours=1), short_desc, cluster_id, fingerprint, 0, None, "positive", 0.85, json.dumps({})))
        
    # Ensure recurrence intelligence stats are inserted/updated
    cur.execute("""
        INSERT INTO recurrence_intelligence (fingerprint, alertname, operator_component, cluster_id, total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            total_occurrences = EXCLUDED.total_occurrences,
            total_incidents = EXCLUDED.total_incidents,
            reopen_count = EXCLUDED.reopen_count,
            resolution_quality_score = EXCLUDED.resolution_quality_score;
    """, (fingerprint, alertname, operator_component, cluster_id, 10, 6, 0, 3600, 95.00, None, datetime.now()))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("Database seeded with 6 incidents in the last 7 days.")
    
    # 3. Execute the blackboard orchestrator with the event JSON
    event_data = {
        "cluster": cluster_id,
        "hostname": "dns-node-01.staging-us-east-1.openshift.com",
        "correlation_id": "test-correlation-reoccur",
        "namespace": namespace,
        "startAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "alertname": alertname
    }
    
    event_json_str = json.dumps(event_data)
    
    print("Executing blackboard orchestrator...")
    result = subprocess.run([
        r"c:\Users\SRIMANDARBHA\.agent\Scripts\python.exe",
        "agents/blackboard_orchestrator.py",
        "--event-json", event_json_str
    ], capture_output=True, text=True, cwd=r"c:\Users\SRIMANDARBHA\Downloads\rag_testing")
    
    print("--- STDOUT ---")
    print(result.stdout)
    print("--- STDERR ---")
    print(result.stderr)

if __name__ == "__main__":
    main()
