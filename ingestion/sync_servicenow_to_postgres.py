import os
import sys
import argparse
import hashlib
import json
from datetime import datetime, timedelta
import requests
import psycopg2
from sentence_transformers import SentenceTransformer

# Silence Hugging Face warnings
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

DATABASE_TARGET = {
    "dbname": os.environ.get("DB_NAME", "rhokp"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432")
}

# State mappings for ServiceNow integer state codes to standard SRE strings
STATE_MAP = {
    "1": "New",
    "2": "Work in Progress",
    "3": "On Hold",
    "6": "Resolved",
    "7": "Closed",
    "8": "Reopened"
}

# Lexicon for rule-based sentiment analysis
POSITIVE_WORDS = ["fixed", "resolved", "stabilized", "restored", "normal", "healthy", "successful", "completed", "great", "excellent", "workaround", "optimal", "recovered"]
NEGATIVE_WORDS = ["error", "fail", "broken", "critical", "outage", "down", "severe", "incident", "issue", "crash", "degraded", "timeout", "saturation", "leak", "exhaustion"]

def analyze_sentiment(text):
    """Performs deterministic rule-based sentiment analysis"""
    if not text:
        return "neutral", 0.5000
    text_lower = text.lower()
    pos_count = sum(text_lower.count(word) for word in POSITIVE_WORDS)
    neg_count = sum(text_lower.count(word) for word in NEGATIVE_WORDS)
    score = 0.5 + (pos_count * 0.12) - (neg_count * 0.12)
    score = max(0.0, min(1.0, score))
    
    if score > 0.58:
        label = "positive"
    elif score < 0.42:
        label = "negative"
    else:
        label = "neutral"
    return label, round(score, 4)

def generate_fingerprint(alertname, namespace, operator_component, cluster_id):
    """Generates a secure SHA-256 fingerprint for alert deduplication"""
    raw_str = f"{alertname}{namespace}{operator_component}{cluster_id}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def get_last_sync_time(conn):
    """Fetches the latest sys_updated_on timestamp from the incidents table"""
    cur = conn.cursor()
    cur.execute("SELECT MAX(sys_updated_on) FROM incidents;")
    last_sync = cur.fetchone()[0]
    cur.close()
    return last_sync

def parse_sys_updated_on(date_str):
    """Parses date string from ServiceNow format into datetime object"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now()

class ServiceNowSyncEngine:
    def __init__(self, db_config, embed_model_name='all-MiniLM-L6-v2'):
        self.db_config = db_config
        self.embed_model_name = embed_model_name
        self._embed_model = None

    @property
    def embed_model(self):
        if self._embed_model is None:
            print(f"Loading SentenceTransformer model ({self.embed_model_name})...")
            self._embed_model = SentenceTransformer(self.embed_model_name)
        return self._embed_model

    def fetch_live_incidents(self, endpoint, username, password, assignment_group, states, last_sync_time):
        """Pulls updated incident tickets from ServiceNow Table API"""
        query_parts = []
        
        # 1. Add assignment group filter
        if assignment_group:
            query_parts.append(f"assignment_group.name={assignment_group}")
            
        # 2. Add state/status filters
        if states:
            # Map state name inputs to SNOW integer values if necessary
            state_codes = []
            inv_map = {v.lower(): k for k, v in STATE_MAP.items()}
            for st in states:
                st_cleaned = st.strip().lower()
                if st_cleaned in inv_map:
                    state_codes.append(inv_map[st_cleaned])
                elif st_cleaned.isdigit():
                    state_codes.append(st_cleaned)
            if state_codes:
                query_parts.append(f"stateIN{','.join(state_codes)}")
                
        # 3. Add delta sync filter based on last sync timestamp
        if last_sync_time:
            # ServiceNow accepts 'YYYY-MM-DD HH:MM:SS' strings in query filters
            last_sync_str = last_sync_time.strftime("%Y-%m-%d %H:%M:%S")
            query_parts.append(f"sys_updated_on>{last_sync_str}")
            
        sysparm_query = "^".join(query_parts)
        
        print(f"Constructed ServiceNow Query: {sysparm_query}")
        
        params = {
            "sysparm_query": sysparm_query,
            "sysparm_limit": 100
        }
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            endpoint,
            auth=(username, password),
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("result", [])

    def fetch_mock_incidents(self, conn, assignment_group, states, last_sync_time):
        """Simulates ServiceNow responses with mock incremental data for local validation"""
        print("[Mock Mode] Generating mock incremental ServiceNow records...")
        
        # Default sync time to 12 hours ago if empty
        ref_time = last_sync_time if last_sync_time else (datetime.now() - timedelta(hours=12))
        print(f"[Mock Mode] Filtering for updates since: {ref_time}")
        
        cur = conn.cursor()
        # Fetch an existing incident to simulate an update or a reopen
        cur.execute("SELECT sys_id, number, cluster_id, alert_fingerprint, flapping_count FROM incidents LIMIT 1;")
        existing_inc = cur.fetchone()
        cur.close()
        
        mock_records = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Scenario A: Simulate a new incoming alert incident (if ref_time is in the past)
        if datetime.now() - ref_time > timedelta(seconds=1):
            mock_records.append({
                "sys_id": "sysid_mock_new_0000000001",
                "number": "INC0099991",
                "state": "1",  # New
                "sys_created_on": now_str,
                "sys_updated_on": now_str,
                "short_description": "Alert 'CoreDNSErrorsHigh' firing in namespace 'openshift-dns' on cluster 'prod-us-east-1'",
                "u_cluster_id": "prod-us-east-1",
                "u_alert_name": "CoreDNSErrorsHigh",
                "u_namespace": "openshift-dns",
                "u_operator": "cluster-dns-operator",
                "u_severity": "warning",
                "u_redhat_case": None,
                "worknotes": "Incident auto-created via mock sync.",
                "comments": "SRE investigating: DNS resolution failing on edge pods."
            })
            
        # Scenario B: Simulate updating an existing incident state (e.g. to Closed or Reopened)
        if existing_inc:
            ex_sys_id, ex_number, ex_cluster, ex_fp, ex_flapping = existing_inc
            mock_records.append({
                "sys_id": ex_sys_id,
                "number": ex_number,
                "state": "7",  # Closed
                "sys_created_on": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                "sys_updated_on": now_str,
                "short_description": f"Alert update on cluster '{ex_cluster}'",
                "u_cluster_id": ex_cluster,
                "u_alert_name": "KubeVirtNoAvailableNodesToRunVMs",
                "u_namespace": "openshift-cnv",
                "u_operator": "kubevirt-hyperconverged-operator",
                "u_severity": "critical",
                "u_redhat_case": "RH-88392183",
                "worknotes": "Workaround validated. Hyperconverged operator stabilized.",
                "comments": "Resolution: Confirmed alert has cleared and all metrics are normal. Closing the incident ticket."
            })
            
        return mock_records

    def parse_incident_fields(self, record):
        """Extracts and normalizes ServiceNow API payload values with fallback logic"""
        sys_id = record.get("sys_id")
        number = record.get("number")
        
        # Translate SNOW state code to standard text label
        state_code = str(record.get("state"))
        state = STATE_MAP.get(state_code, "Work in Progress")
        
        sys_created_on = parse_sys_updated_on(record.get("sys_created_on"))
        sys_updated_on = parse_sys_updated_on(record.get("sys_updated_on"))
        short_description = record.get("short_description", "No description provided")
        
        cluster_id = record.get("u_cluster_id") or record.get("cluster_id") or "prod-us-east-1"
        redhat_case_id = record.get("u_redhat_case") or record.get("redhat_case_id")
        
        alertname = record.get("u_alert_name") or record.get("alert_name")
        namespace = record.get("u_namespace") or record.get("namespace") or "openshift-monitoring"
        operator_component = record.get("u_operator") or record.get("operator_component") or "prometheus"
        severity = record.get("u_severity") or record.get("severity") or "warning"
        
        # Fallback parser: Try extracting details from short description if custom parameters are missing
        if not alertname and "firing in namespace" in short_description.lower():
            try:
                import re
                match = re.search(r"alert '([^']+)' firing in namespace '([^']+)' on cluster '([^']+)'", short_description.lower())
                if match:
                    alertname = match.group(1)
                    namespace = match.group(2)
                    cluster_id = match.group(3)
            except Exception:
                pass
                
        if not alertname:
            alertname = "UnknownAlert"
            
        fingerprint = generate_fingerprint(alertname, namespace, operator_component, cluster_id)
        
        # Extract comments / worknotes text
        worknotes = record.get("comments") or record.get("worknotes") or record.get("work_notes") or ""
        
        return {
            "sys_id": sys_id,
            "number": number,
            "state": state,
            "sys_created_on": sys_created_on,
            "sys_updated_on": sys_updated_on,
            "short_description": short_description,
            "cluster_id": cluster_id,
            "redhat_case_id": redhat_case_id,
            "alertname": alertname,
            "namespace": namespace,
            "operator_component": operator_component,
            "severity": severity,
            "fingerprint": fingerprint,
            "worknotes": worknotes
        }

    def sync_records(self, records):
        """Processes the parsed records into PostgreSQL, running upserts and vectorizing resolutions"""
        if not records:
            print("No records to synchronize.")
            return
            
        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()
        
        processed_fingerprints = set()
        resolved_incidents = []
        
        try:
            for record_raw in records:
                parsed = self.parse_incident_fields(record_raw)
                sys_id = parsed["sys_id"]
                fingerprint = parsed["fingerprint"]
                processed_fingerprints.add(fingerprint)
                
                print(f"Syncing Incident {parsed['number']} ({parsed['state']}) - Fingerprint: {fingerprint[:10]}...")
                
                # 1. Ensure Cluster is present in DB
                cur.execute("""
                    INSERT INTO clusters (cluster_id, name, openshift_version, environment)
                    VALUES (%s, %s, '4.14.0', 'production')
                    ON CONFLICT (cluster_id) DO NOTHING;
                """, (parsed["cluster_id"], f"Cluster {parsed['cluster_id']}"))
                
                # 2. Upsert Alert Occurrence
                # Increments occurrence count on upsert conflict
                cur.execute("""
                    INSERT INTO alert_occurrences (fingerprint, alertname, namespace, operator_component, cluster_id, severity, occurrence_count, active, first_seen, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
                    ON CONFLICT (fingerprint) DO UPDATE SET
                        occurrence_count = alert_occurrences.occurrence_count + 1,
                        active = EXCLUDED.active,
                        last_seen = EXCLUDED.last_seen;
                """, (
                    fingerprint, parsed["alertname"], parsed["namespace"], parsed["operator_component"],
                    parsed["cluster_id"], parsed["severity"], parsed["state"] not in ("Resolved", "Closed"),
                    parsed["sys_created_on"], parsed["sys_updated_on"]
                ))
                
                # 3. Analyze worknotes sentiment
                sent_lbl, sent_scr = analyze_sentiment(parsed["worknotes"])
                
                # 4. Upsert Incident State
                cur.execute("""
                    INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s)
                    ON CONFLICT (sys_id) DO UPDATE SET
                        state = EXCLUDED.state,
                        sys_updated_on = EXCLUDED.sys_updated_on,
                        redhat_case_id = EXCLUDED.redhat_case_id,
                        sentiment_label = EXCLUDED.sentiment_label,
                        sentiment_score = EXCLUDED.sentiment_score,
                        raw_payload = EXCLUDED.raw_payload;
                """, (
                    sys_id, parsed["number"], parsed["state"], parsed["sys_created_on"], parsed["sys_updated_on"],
                    parsed["short_description"], parsed["cluster_id"], fingerprint, parsed["redhat_case_id"],
                    sent_lbl, sent_scr, json.dumps(record_raw)
                ))
                
                # 5. Insert Worknotes timeline record
                if parsed["worknotes"]:
                    cur.execute("""
                        INSERT INTO incident_worknotes (sys_id, worknote_text, created_on, sentiment_label, sentiment_score)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (sys_id, parsed["worknotes"], parsed["sys_updated_on"], sent_lbl, sent_scr))
                    
                # 6. Append state transition snapshot
                cur.execute("""
                    INSERT INTO incident_snapshots (sys_id, state, sys_updated_on, changed_by, worknotes_added, sentiment_label, sentiment_score)
                    VALUES (%s, %s, %s, 'SRE Sync Engine', %s, %s, %s)
                    ON CONFLICT (sys_id, sys_updated_on) DO NOTHING;
                """, (sys_id, parsed["state"], parsed["sys_updated_on"], parsed["worknotes"], sent_lbl, sent_scr))
                
                # Track closed/resolved incidents for RAG vectorization
                if parsed["state"] in ("Resolved", "Closed"):
                    resolved_incidents.append((sys_id, parsed["number"], parsed["short_description"], parsed["worknotes"], sent_lbl))
            
            # 7. Recalculate Recurrence Aggregates for modified alert fingerprints
            for fp in processed_fingerprints:
                print(f"Recalculating aggregates for fingerprint: {fp[:10]}...")
                cur.execute("""
                    SELECT alertname, operator_component, cluster_id, severity, occurrence_count
                    FROM alert_occurrences WHERE fingerprint = %s;
                """, (fp,))
                alert_info = cur.fetchone()
                if not alert_info:
                    continue
                alertname, operator, cluster, severity, occurrence_count = alert_info
                
                # Calculate counts from incidents table
                cur.execute("""
                    SELECT COUNT(*), 
                           COUNT(CASE WHEN state = 'Reopened' THEN 1 END),
                           MAX(CASE WHEN state = 'Reopened' THEN sys_updated_on END)
                    FROM incidents WHERE alert_fingerprint = %s;
                """, (fp,))
                inc_counts = cur.fetchone()
                total_incidents = inc_counts[0] or 0
                reopen_count = inc_counts[1] or 0
                last_reopened = inc_counts[2]
                
                # Calculate average MTTR (seconds)
                cur.execute("""
                    SELECT AVG(EXTRACT(EPOCH FROM (sys_updated_on - sys_created_on))) 
                    FROM incidents 
                    WHERE alert_fingerprint = %s AND state IN ('Resolved', 'Closed');
                """, (fp,))
                avg_mttr = cur.fetchone()[0]
                avg_mttr_sec = int(avg_mttr) if avg_mttr is not None else 0
                
                # Calculate resolution quality score
                # Base is 100, -30 per reopen, +10 for positive sentiment, -10 for negative
                cur.execute("""
                    SELECT AVG(sentiment_score) FROM incidents 
                    WHERE alert_fingerprint = %s AND state IN ('Resolved', 'Closed');
                """, (fp,))
                avg_sentiment = cur.fetchone()[0]
                avg_sent_val = float(avg_sentiment) if avg_sentiment is not None else 0.5
                
                quality_score = 100.0 - (reopen_count * 30.0) + ((avg_sent_val - 0.5) * 40.0)
                quality_score = max(0.0, min(100.0, quality_score))
                
                # Update recurrence intelligence
                cur.execute("""
                    INSERT INTO recurrence_intelligence (fingerprint, alertname, operator_component, cluster_id, total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (fingerprint) DO UPDATE SET
                        total_occurrences = EXCLUDED.total_occurrences,
                        total_incidents = EXCLUDED.total_incidents,
                        reopen_count = EXCLUDED.reopen_count,
                        mttr_seconds = EXCLUDED.mttr_seconds,
                        resolution_quality_score = EXCLUDED.resolution_quality_score,
                        last_reopened_at = EXCLUDED.last_reopened_at,
                        updated_at = NOW();
                """, (fp, alertname, operator, cluster, occurrence_count, total_incidents, reopen_count, avg_mttr_sec, round(quality_score, 2), last_reopened))
                
            conn.commit()
            print("Database updates committed successfully.")
            
        except Exception as db_err:
            conn.rollback()
            print(f"Database ingestion error: {db_err}")
            raise db_err
        finally:
            cur.close()
            conn.close()
            
        # 8. Generate and save Vector Embeddings for resolved/closed incidents (Runs outside database txn block)
        if resolved_incidents:
            try:
                embeddings_to_insert = []
                for sys_id, number, short_desc, res_text, sentiment in resolved_incidents:
                    text_chunk = (
                        f"Post-Mortem for ServiceNow Incident {number} | "
                        f"Description: {short_desc} | "
                        f"Resolution Notes: {res_text} | "
                        f"Sentiment: {sentiment.upper()}"
                    )
                    # Create vector representation
                    embedding = self.embed_model.encode(text_chunk).tolist()
                    embeddings_to_insert.append((sys_id, "incidents", text_chunk, embedding, self.embed_model_name, "1.0"))
                    
                conn = psycopg2.connect(**self.db_config)
                cur = conn.cursor()
                cur.executemany("""
                    INSERT INTO operational_knowledge_embeddings (source_id, source_table, text_chunk, embedding, model_name, model_version)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, embeddings_to_insert)
                conn.commit()

                cur.close()
                conn.close()
                print(f"Generated and saved {len(embeddings_to_insert)} resolution vector embeddings.")
            except Exception as emb_err:
                print(f"[Warning] Failed to generate/save vector embeddings: {emb_err}")

def main():
    parser = argparse.ArgumentParser(description="Live ServiceNow Incident Delta Synchronizer")
    parser.add_argument("--endpoint", type=str, default="https://mock-instance.service-now.com/api/now/table/incident", help="ServiceNow Incident Table API endpoint")
    parser.add_argument("--username", type=str, default="admin", help="ServiceNow username")
    parser.add_argument("--password", type=str, default="admin", help="ServiceNow password")
    parser.add_argument("--assignment-group", type=str, default="ocv-sre-support", help="Sync incidents assigned to this group name")
    parser.add_argument("--states", type=str, default="New,Work in Progress,Resolved,Closed,Reopened", help="Comma-separated status names to pull")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode using simulated data delta updates")
    
    args = parser.parse_args()
    
    print("ServiceNow Incident Delta Ingestion Engine")
    print("==========================================")
    
    try:
        conn = psycopg2.connect(**DATABASE_TARGET)
        last_sync = get_last_sync_time(conn)
        conn.close()
        
        if last_sync:
            print(f"Incremental sync: Last stored incident update was at: {last_sync}")
        else:
            print("Full sync: No incidents found in database. Syncing from default baseline (past 30 days)...")
            
        engine = ServiceNowSyncEngine(db_config=DATABASE_TARGET)
        
        # Pull records
        if args.mock:
            conn = psycopg2.connect(**DATABASE_TARGET)
            records = engine.fetch_mock_incidents(
                conn=conn,
                assignment_group=args.assignment_group,
                states=args.states.split(","),
                last_sync_time=last_sync
            )
            conn.close()
        else:
            records = engine.fetch_live_incidents(
                endpoint=args.endpoint,
                username=args.username,
                password=args.password,
                assignment_group=args.assignment_group,
                states=args.states.split(","),
                last_sync_time=last_sync
            )
            
        print(f"Retrieved {len(records)} updated ServiceNow incident records.")
        
        # Process and sync into PostgreSQL
        engine.sync_records(records)
        print("\nSync workflow completed successfully.")
        
    except Exception as e:
        print(f"\nExecution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
