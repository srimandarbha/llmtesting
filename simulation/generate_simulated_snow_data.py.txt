import os
import sys
import hashlib
import random
import json
from datetime import datetime, timedelta
import psycopg2
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer

# Silence Hugging Face warnings
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

DATABASE_TARGET = {
    "dbname": "rhokp",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

# Lexicon for rule-based sentiment analysis
POSITIVE_WORDS = ["fixed", "resolved", "stabilized", "restored", "normal", "healthy", "successful", "completed", "great", "excellent", "workaround", "optimal", "recovered"]
NEGATIVE_WORDS = ["error", "fail", "broken", "critical", "outage", "down", "severe", "incident", "issue", "crash", "degraded", "timeout", "saturation", "leak", "exhaustion"]

def analyze_sentiment(text):
    """
    Performs deterministic rule-based sentiment analysis.
    Returns (label, score) where score is NUMERIC(5, 4) in the range [0.0000, 1.0000]
    """
    if not text:
        return "neutral", 0.5000
    
    text_lower = text.lower()
    pos_count = sum(text_lower.count(word) for word in POSITIVE_WORDS)
    neg_count = sum(text_lower.count(word) for word in NEGATIVE_WORDS)
    
    # Compute score centered at 0.5
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

def create_schemas(conn):
    """Creates the tables and indexes according to the approved architecture DDL"""
    cur = conn.cursor()
    print("Enabling pgvector extension if not exists...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    print("Creating table: clusters...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            cluster_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description VARCHAR(200),
            openshift_version VARCHAR(20) NOT NULL,
            environment VARCHAR(20) NOT NULL CHECK (environment IN ('production', 'staging', 'development', 'dr'))
        );
        ALTER TABLE clusters ADD COLUMN IF NOT EXISTS description VARCHAR(200);
        CREATE INDEX IF NOT EXISTS idx_clusters_env ON clusters(environment);
    """)
    
    print("Creating table: alert_occurrences...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alert_occurrences (
            fingerprint VARCHAR(64) PRIMARY KEY,
            alertname VARCHAR(100) NOT NULL,
            namespace VARCHAR(100) NOT NULL,
            operator_component VARCHAR(100) NOT NULL,
            cluster_id VARCHAR(50) NOT NULL REFERENCES clusters(cluster_id) ON DELETE CASCADE,
            severity VARCHAR(20) NOT NULL,
            occurrence_count INT DEFAULT 1,
            active BOOLEAN DEFAULT TRUE,
            first_seen TIMESTAMP NOT NULL,
            last_seen TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alert_occurrences(alertname, cluster_id, active);
    """)
    
    print("Creating table: redhat_cases...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS redhat_cases (
            case_id VARCHAR(50) PRIMARY KEY,
            title TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            created_on TIMESTAMP NOT NULL,
            closed_on TIMESTAMP,
            resolution TEXT
        );
    """)
    
    print("Creating table: incidents...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            sys_id VARCHAR(32) PRIMARY KEY,
            number VARCHAR(20) UNIQUE NOT NULL,
            state VARCHAR(30) NOT NULL,
            sys_created_on TIMESTAMP NOT NULL,
            sys_updated_on TIMESTAMP NOT NULL,
            short_description TEXT NOT NULL,
            cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE SET NULL,
            alert_fingerprint VARCHAR(64) REFERENCES alert_occurrences(fingerprint) ON DELETE SET NULL,
            flapping_count INT DEFAULT 0,
            redhat_case_id VARCHAR(50) REFERENCES redhat_cases(case_id) ON DELETE SET NULL,
            sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
            sentiment_score NUMERIC(5, 4),
            raw_payload JSONB
        );
        CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents(state);
        CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint ON incidents(alert_fingerprint);
    """)
    
    print("Creating table: incident_worknotes...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incident_worknotes (
            id SERIAL PRIMARY KEY,
            sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
            worknote_text TEXT NOT NULL,
            created_on TIMESTAMP NOT NULL,
            sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
            sentiment_score NUMERIC(5, 4)
        );
        CREATE INDEX IF NOT EXISTS idx_worknotes_sys_id ON incident_worknotes(sys_id, created_on DESC);
    """)
    
    print("Creating table: incident_snapshots...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incident_snapshots (
            snapshot_id SERIAL PRIMARY KEY,
            sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
            state VARCHAR(30) NOT NULL,
            sys_updated_on TIMESTAMP NOT NULL,
            changed_by VARCHAR(100) NOT NULL,
            worknotes_added TEXT,
            sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
            sentiment_score NUMERIC(5, 4),
            CONSTRAINT unique_sys_id_updated UNIQUE (sys_id, sys_updated_on)
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON incident_snapshots(sys_id, sys_updated_on DESC);
    """)
    
    print("Creating table: recurrence_intelligence...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recurrence_intelligence (
            fingerprint VARCHAR(64) PRIMARY KEY REFERENCES alert_occurrences(fingerprint) ON DELETE CASCADE,
            alertname VARCHAR(100) NOT NULL,
            operator_component VARCHAR(100) NOT NULL,
            cluster_id VARCHAR(50) REFERENCES clusters(cluster_id) ON DELETE CASCADE,
            total_occurrences INT DEFAULT 0,
            total_incidents INT DEFAULT 0,
            reopen_count INT DEFAULT 0,
            mttr_seconds BIGINT DEFAULT 0,
            resolution_quality_score NUMERIC(5, 2),
            last_reopened_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL
        );
    """)
    
    print("Creating table: operational_knowledge_embeddings...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operational_knowledge_embeddings (
            id SERIAL PRIMARY KEY,
            source_id VARCHAR(100) NOT NULL,
            source_table VARCHAR(50) NOT NULL,
            text_chunk TEXT NOT NULL,
            embedding vector(384) NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vector_hnsw ON operational_knowledge_embeddings USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);
    """)
    
    conn.commit()
    cur.close()
    print("Tables and indexes successfully established!")

def clean_database(conn):
    """Truncates all tables for a clean simulation run"""
    print("Cleaning existing database data...")
    cur = conn.cursor()
    cur.execute("""
        TRUNCATE TABLE 
            operational_knowledge_embeddings, 
            recurrence_intelligence, 
            incident_snapshots, 
            incident_worknotes, 
            incidents, 
            redhat_cases, 
            alert_occurrences, 
            clusters 
        RESTART IDENTITY CASCADE;
    """)
    conn.commit()
    cur.close()
    print("Database cleaned.")

def generate_mock_data(conn):
    """Generates the simulated dataset of clusters, alerts, cases, incidents, snapshots, worknotes, and recurrence aggregates"""
    cur = conn.cursor()
    
    # 1. Clusters (5 clusters)
    clusters_data = [
        ("nzclu101", "nzclu101", "Production New Zealand", "4.14.12", "production"),
        ("emclu202", "emclu202", "Production Emirates", "4.14.12", "production"),
        ("auclo303", "auclo303", "Staging Australia", "4.15.2", "staging"),
        ("inclu404", "inclu404", "Development India", "4.16.0-rc2", "development"),
        ("nzclu102", "nzclu102", "Disaster Recovery New Zealand", "4.14.12", "dr")
    ]
    
    print("Inserting clusters...")
    cur.executemany("""
        INSERT INTO clusters (cluster_id, name, description, openshift_version, environment)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (cluster_id) DO NOTHING;
    """, clusters_data)
    
    # 2. Alert Occurrences (Deterministic Fingerprints)
    # Define a base list of alert profiles
    alert_profiles = [
        ("CollectorNodeDown", "cluster-logging-operator", "logging-operator", "warning"),
        ("KubeAPIDown", "openshift-kube-apiserver", "kube-apiserver-operator", "critical"),
        ("CoreDNSErrorsHigh", "openshift-dns", "cluster-dns-operator", "warning"),
        ("KubeVirtNoAvailableNodesToRunVMs", "openshift-cnv", "kubevirt-hyperconverged-operator", "critical"),
        ("TargetDown", "openshift-monitoring", "prometheus-operator", "warning"),
        ("DiskClusterFailing", "openshift-storage", "ocs-operator", "critical"),
        ("NetworkInterfaceFlapping", "openshift-multus", "multus-operator", "warning"),
        ("APIRequestLatencyHigh", "openshift-kube-apiserver", "kube-apiserver-operator", "warning"),
        ("EtcdMembersDown", "openshift-etcd", "etcd-operator", "critical"),
        ("ingress-operator-degraded", "openshift-ingress-operator", "ingress-operator", "critical")
    ]
    
    alert_occurrences = []
    base_time = datetime.now() - timedelta(days=12)
    
    for cluster_id, _, _, _, _ in clusters_data:
        # Assign 4-6 random alert profiles to each cluster
        selected_profiles = random.sample(alert_profiles, k=random.randint(4, 6))
        for alertname, namespace, operator_component, severity in selected_profiles:
            fingerprint = generate_fingerprint(alertname, namespace, operator_component, cluster_id)
            occurrence_count = random.randint(3, 45)
            first_seen = base_time + timedelta(hours=random.randint(0, 48))
            last_seen = datetime.now() - timedelta(minutes=random.randint(5, 120))
            
            # Decide if active based on environment and profile
            active = random.choice([True, False]) if cluster_id != "inclu404" else True
            
            alert_occurrences.append((
                fingerprint, alertname, namespace, operator_component, cluster_id,
                severity, occurrence_count, active, first_seen, last_seen
            ))
            
    print(f"Inserting {len(alert_occurrences)} alert occurrences...")
    cur.executemany("""
        INSERT INTO alert_occurrences (fingerprint, alertname, namespace, operator_component, cluster_id, severity, occurrence_count, active, first_seen, last_seen)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            occurrence_count = EXCLUDED.occurrence_count,
            active = EXCLUDED.active,
            last_seen = EXCLUDED.last_seen;
    """, alert_occurrences)
    
    # 3. Red Hat Support Cases (8 cases)
    redhat_cases_data = [
        ("RH-53029103", "API server timeout on high etcd db size", "Closed", "Severity 1 (Urgent)", base_time, base_time + timedelta(days=1), "Upgraded ETCD database compression intervals and executed manual compaction."),
        ("RH-12948192", "CoreDNS packet drops under severe pod scaling stress", "Closed", "Severity 2 (High)", base_time + timedelta(days=2), base_time + timedelta(days=3), "Adjusted DNS upstream timeout values in CoreDNS configmap Corefile."),
        ("RH-88392183", "KubeVirt hyperconverged operator scheduling failure due to missing node labels", "Closed", "Severity 1 (Urgent)", base_time + timedelta(days=1), base_time + timedelta(days=1, hours=8), "Applied kubevirt node selector overrides to re-allocate scheduling domains."),
        ("RH-99201928", "Prometheus scraper targets crashing due to memory limits", "Open", "Severity 2 (High)", datetime.now() - timedelta(days=2), None, None),
        ("RH-22340182", "OCS StorageCluster Ceph pool degraded IO", "Closed", "Severity 1 (Urgent)", base_time + timedelta(days=4), base_time + timedelta(days=5), "Replaced faulty OSD disk on node-03 and initiated Ceph recovery process."),
        ("RH-33458291", "Multus network attachment definition routing loop", "Closed", "Severity 3 (Medium)", base_time + timedelta(days=3), base_time + timedelta(days=4), "Updated Multus CNI network schema to avoid default bridge route conflicts."),
        ("RH-77482918", "ETCD leader election storm on disk slow operations", "Closed", "Severity 1 (Urgent)", base_time + timedelta(days=6), base_time + timedelta(days=6, hours=12), "Migrated ETCD storage classes to premium SSD disks with guaranteed write IOPS."),
        ("RH-66528192", "Ingress Operator failing HTTP health checks on cluster router pods", "Open", "Severity 2 (High)", datetime.now() - timedelta(hours=18), None, None)
    ]
    
    print("Inserting Red Hat cases...")
    cur.executemany("""
        INSERT INTO redhat_cases (case_id, title, status, severity, created_on, closed_on, resolution)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (case_id) DO UPDATE SET
            status = EXCLUDED.status,
            closed_on = EXCLUDED.closed_on,
            resolution = EXCLUDED.resolution;
    """, redhat_cases_data)
    
    # 4. Generate 55 ServiceNow Incidents
    print("Generating simulated ServiceNow incidents...")
    incidents_to_insert = []
    worknotes_to_insert = []
    snapshots_to_insert = []
    
    # Pre-defined worknotes scripts for SRE updates
    w_neutral_investigate = [
        "SRE investigating alert. Scraping cluster logs and Prometheus telemetry.",
        "Checked node system logs. CPU load is elevated but memory consumption is within limits.",
        "Waiting for telemetry data from cluster operator component.",
        "Analyzing network routing tables and namespace configurations.",
        "Investigating etcd leader history and storage partition status."
    ]
    
    w_negative_degraded = [
        "Severe error: Node resources saturated. Core services throwing timeouts.",
        "Degraded state detected. Database connection pool is exhausted, rejecting API requests.",
        "Outage alert: Multiple pods crashed in namespace. Storage is inaccessible.",
        "Disk latency is extremely high, causing severe read/write lag on the storage nodes.",
        "Network package drop rate is over 15%, causing critical heartbeat failures."
    ]
    
    w_positive_workaround = [
        "Workaround applied: Restarted degraded operators to clear thread pool deadlock.",
        "Fixed issue by scaling the replica count to 3. Network routing has stabilized.",
        "Restored node health by deleting dead containers. Resources returned to healthy levels.",
        "Compacted etcd database, successfully reclaiming 2GB space. Cluster latency is back to normal.",
        "Adjusted routing rules in Multus config. All interfaces are healthy and operating normally."
    ]
    
    w_closing_notes = [
        "Confirmed alert has cleared and all metrics are normal. Closing the incident ticket.",
        "Resolution verified. System remains stable for 1 hour. Ticket resolved successfully.",
        "Workaround confirmed permanent. Alert inactive. Resolving ServiceNow ticket.",
        "Ceph recovery finished. Health status changed back to OK. Ticket closed.",
        "Ingress controller restored. Router pods passing health checks. Ticket resolved."
    ]
    
    # Track metrics for recurrence pre-aggregation
    fingerprint_recurrence_stats = {}
    
    for i in range(1, 56):
        sys_id = f"sysid{i:020d}"
        number = f"INC{i:07d}"
        
        # Link to a random alert occurrence
        alert_occ = random.choice(alert_occurrences)
        fingerprint = alert_occ[0]
        alertname = alert_occ[1]
        namespace = alert_occ[2]
        operator_component = alert_occ[3]
        cluster_id = alert_occ[4]
        
        # Determine incident state: Open (New, Work in Progress, Reopened), Resolved, Closed
        # Let's distribute states realistically
        if i <= 10:
            state = "New"
        elif i <= 25:
            state = "Work in Progress"
        elif i <= 30:
            state = "Reopened"
        elif i <= 45:
            state = "Resolved"
        else:
            state = "Closed"
            
        # Determine flapping count (high flapping count on some warning alerts)
        flapping_count = random.randint(3, 12) if alertname in ("CoreDNSErrorsHigh", "NetworkInterfaceFlapping") else random.randint(0, 2)
        
        # Red Hat case link if critical or high incident
        rh_case_id = None
        if alert_occ[5] == "critical" and random.random() < 0.6:
            # Pick a case matching severity/status if possible
            matching_cases = [c[0] for c in redhat_cases_data if (state in ("Resolved", "Closed") and c[2] == "Closed") or (state not in ("Resolved", "Closed") and c[2] == "Open")]
            if matching_cases:
                rh_case_id = random.choice(matching_cases)
        
        # Ticket creation timestamp
        created_time = base_time + timedelta(days=random.randint(1, 8), hours=random.randint(0, 23))
        
        # Ticket update timestamp
        if state in ("New", "Work in Progress", "Reopened"):
            updated_time = datetime.now() - timedelta(minutes=random.randint(10, 300))
        else:
            # Resolved/Closed tickets
            updated_time = created_time + timedelta(hours=random.randint(1, 48))
            
        short_desc = f"Alert '{alertname}' firing in namespace '{namespace}' on cluster '{cluster_id}'"
        
        # Create worknotes and transitions
        notes = []
        transitions = []
        
        # 1st state transition: New
        transitions.append({
            "state": "New",
            "time": created_time,
            "worknotes": f"Incident created automatically via cluster alert ingestion. Alert Fingerprint: {fingerprint}"
        })
        
        # If state progressed past New
        if state != "New":
            # Add Work in Progress
            wip_time = created_time + timedelta(minutes=random.randint(15, 60))
            notes.append({
                "text": random.choice(w_neutral_investigate),
                "time": wip_time
            })
            transitions.append({
                "state": "Work in Progress",
                "time": wip_time,
                "worknotes": notes[-1]["text"]
            })
            
            # Maybe add a negative degraded note
            if random.random() < 0.7:
                deg_time = wip_time + timedelta(minutes=random.randint(30, 120))
                notes.append({
                    "text": random.choice(w_negative_degraded),
                    "time": deg_time
                })
                # (State remains WIP but worknotes added)
            
            # Reopened state simulation
            if state == "Reopened":
                # First Resolved
                res_time = wip_time + timedelta(hours=random.randint(2, 6))
                notes.append({
                    "text": random.choice(w_positive_workaround),
                    "time": res_time
                })
                transitions.append({
                    "state": "Resolved",
                    "time": res_time,
                    "worknotes": notes[-1]["text"]
                })
                
                # Then Reopened
                reopen_time = res_time + timedelta(hours=random.randint(1, 12))
                notes.append({
                    "text": "Incident reopened: Alert re-fired shortly after closure. Flapping suspected.",
                    "time": reopen_time
                })
                transitions.append({
                    "state": "Reopened",
                    "time": reopen_time,
                    "worknotes": notes[-1]["text"]
                })
                
            # If resolved or closed
            elif state in ("Resolved", "Closed"):
                res_time = wip_time + timedelta(hours=random.randint(2, 12))
                res_comment = random.choice(w_positive_workaround)
                notes.append({
                    "text": res_comment,
                    "time": res_time
                })
                transitions.append({
                    "state": "Resolved",
                    "time": res_time,
                    "worknotes": res_comment
                })
                
                if state == "Closed":
                    cls_time = res_time + timedelta(hours=random.randint(12, 24))
                    cls_comment = random.choice(w_closing_notes)
                    notes.append({
                        "text": cls_comment,
                        "time": cls_time
                    })
                    transitions.append({
                        "state": "Closed",
                        "time": cls_time,
                        "worknotes": cls_comment
                    })

        # Calculate final sentiment label and score based on the LAST worknote/closing comment
        last_note_text = notes[-1]["text"] if notes else short_desc
        sent_lbl, sent_scr = analyze_sentiment(last_note_text)
        
        # Determine hostname based on cluster location pattern
        loc = cluster_id[:2] if len(cluster_id) >= 2 else "nz"
        hostname = f"{loc}o{random.randint(10000, 99999)}"
        
        # Build Raw JSON Payload
        raw_payload = {
            "sys_id": sys_id,
            "number": number,
            "state": state,
            "sys_created_on": created_time.strftime("%Y-%m-%d %H:%M:%S"),
            "sys_updated_on": updated_time.strftime("%Y-%m-%d %H:%M:%S"),
            "short_description": short_desc,
            "u_cluster_id": cluster_id,
            "u_hostname": hostname,
            "u_alert_name": alertname,
            "u_namespace": namespace,
            "u_operator": operator_component,
            "u_severity": alert_occ[5],
            "u_redhat_case": rh_case_id,
            "close_notes": last_note_text if state in ("Resolved", "Closed") else "",
            "worknotes": [n["text"] for n in notes]
        }
        
        # Append to main records list
        incidents_to_insert.append((
            sys_id, number, state, created_time, updated_time, short_desc,
            cluster_id, fingerprint, flapping_count, rh_case_id,
            sent_lbl, sent_scr, json.dumps(raw_payload)
        ))
        
        # Compile worknotes for batch insert
        for n in notes:
            n_lbl, n_scr = analyze_sentiment(n["text"])
            worknotes_to_insert.append((
                sys_id, n["text"], n["time"], n_lbl, n_scr
            ))
            
        # Compile snapshots for batch insert (deduplicating by unique sys_id & updated_on)
        seen_snapshots = set()
        for snap in transitions:
            snap_time_str = snap["time"].strftime("%Y-%m-%d %H:%M:%S")
            snap_key = (sys_id, snap_time_str)
            if snap_key not in seen_snapshots:
                seen_snapshots.add(snap_key)
                s_lbl, s_scr = analyze_sentiment(snap["worknotes"])
                snapshots_to_insert.append((
                    sys_id, snap["state"], snap["time"], "SRE Automated Integrator",
                    snap["worknotes"], s_lbl, s_scr
                ))
                
        # Aggregate recurrence metrics tracking per alert fingerprint
        if fingerprint not in fingerprint_recurrence_stats:
            fingerprint_recurrence_stats[fingerprint] = {
                "alertname": alertname,
                "operator_component": operator_component,
                "cluster_id": cluster_id,
                "total_occurrences": alert_occ[6], # from alert_occurrences
                "total_incidents": 0,
                "reopen_count": 0,
                "mttr_durations": [],
                "last_reopened_at": None,
                "resolutions": []
            }
            
        stats = fingerprint_recurrence_stats[fingerprint]
        stats["total_incidents"] += 1
        
        if state == "Reopened":
            stats["reopen_count"] += 1
            if stats["last_reopened_at"] is None or updated_time > stats["last_reopened_at"]:
                stats["last_reopened_at"] = updated_time
                
        if state in ("Resolved", "Closed"):
            duration = (updated_time - created_time).total_seconds()
            stats["mttr_durations"].append(duration)
            stats["resolutions"].append((sent_scr, state == "Reopened"))

    # Insert incidents
    print("Inserting ServiceNow incidents...")
    cur.executemany("""
        INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sys_id) DO UPDATE SET
            state = EXCLUDED.state,
            sys_updated_on = EXCLUDED.sys_updated_on,
            flapping_count = incidents.flapping_count + EXCLUDED.flapping_count,
            redhat_case_id = EXCLUDED.redhat_case_id,
            sentiment_label = EXCLUDED.sentiment_label,
            sentiment_score = EXCLUDED.sentiment_score,
            raw_payload = EXCLUDED.raw_payload;
    """, incidents_to_insert)
    
    # Insert worknotes
    print("Inserting incident worknotes...")
    cur.executemany("""
        INSERT INTO incident_worknotes (sys_id, worknote_text, created_on, sentiment_label, sentiment_score)
        VALUES (%s, %s, %s, %s, %s);
    """, worknotes_to_insert)
    
    # Insert snapshots
    print("Inserting incident snapshots...")
    cur.executemany("""
        INSERT INTO incident_snapshots (sys_id, state, sys_updated_on, changed_by, worknotes_added, sentiment_label, sentiment_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (sys_id, sys_updated_on) DO NOTHING;
    """, snapshots_to_insert)
    
    # Calculate and insert Recurrence Intelligence Aggregates
    print("Calculating and inserting recurrence aggregates...")
    recurrence_data = []
    for fp, stats in fingerprint_recurrence_stats.items():
        avg_mttr = int(sum(stats["mttr_durations"]) / len(stats["mttr_durations"])) if stats["mttr_durations"] else 0
        
        # Calculate resolution quality score: starts at 100
        # Deduct 30 per reopen
        # Add (sentiment score - 0.5) * 40
        quality_score = 100.0
        quality_score -= stats["reopen_count"] * 30.0
        
        if stats["resolutions"]:
            avg_res_sent = sum(r[0] for r in stats["resolutions"]) / len(stats["resolutions"])
            quality_score += (avg_res_sent - 0.5) * 40.0
            
        quality_score = max(0.0, min(100.0, quality_score))
        
        recurrence_data.append((
            fp, stats["alertname"], stats["operator_component"], stats["cluster_id"],
            stats["total_occurrences"], stats["total_incidents"], stats["reopen_count"],
            avg_mttr, round(quality_score, 2), stats["last_reopened_at"], datetime.now()
        ))
        
    cur.executemany("""
        INSERT INTO recurrence_intelligence (fingerprint, alertname, operator_component, cluster_id, total_occurrences, total_incidents, reopen_count, mttr_seconds, resolution_quality_score, last_reopened_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fingerprint) DO UPDATE SET
            total_occurrences = EXCLUDED.total_occurrences,
            total_incidents = EXCLUDED.total_incidents,
            reopen_count = EXCLUDED.reopen_count,
            mttr_seconds = EXCLUDED.mttr_seconds,
            resolution_quality_score = EXCLUDED.resolution_quality_score,
            last_reopened_at = EXCLUDED.last_reopened_at,
            updated_at = EXCLUDED.updated_at;
    """, recurrence_data)
    
    conn.commit()
    cur.close()
    print(f"Data seeding completed! Generated:")
    print(f" - {len(clusters_data)} Clusters")
    print(f" - {len(alert_occurrences)} Alert Occurrences")
    print(f" - {len(redhat_cases_data)} Red Hat Cases")
    print(f" - {len(incidents_to_insert)} ServiceNow Incidents")
    print(f" - {len(worknotes_to_insert)} Incident Worknotes")
    print(f" - {len(snapshots_to_insert)} Incident Snapshots")
    print(f" - {len(recurrence_data)} Recurrence Aggregates")

def generate_vector_embeddings(conn):
    """Generates sentence embeddings for SRE Playbooks and incident resolutions using all-MiniLM-L6-v2"""
    print("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    cur = conn.cursor()
    
    # 1. Fetch resolved/closed incidents that have resolutions to embed
    cur.execute("""
        SELECT sys_id, number, short_description, sentiment_label 
        FROM incidents 
        WHERE state IN ('Resolved', 'Closed');
    """)
    resolved_incidents = cur.fetchall()
    
    embeddings_to_insert = []
    print(f"Generating embeddings for {len(resolved_incidents)} incident post-mortems/resolutions...")
    
    for sys_id, number, short_desc, sentiment in resolved_incidents:
        # Fetch the resolution comment (last worknote of state Resolved/Closed)
        cur.execute("""
            SELECT worknote_text FROM incident_worknotes 
            WHERE sys_id = %s 
            ORDER BY created_on DESC LIMIT 1;
        """, (sys_id,))
        res_note = cur.fetchone()
        res_text = res_note[0] if res_note else "Incident resolved."
        
        text_chunk = (
            f"Post-Mortem for ServiceNow Incident {number} | "
            f"Description: {short_desc} | "
            f"Resolution Notes: {res_text} | "
            f"Sentiment: {sentiment.upper()}"
        )
        
        # Generate dense vector coordinates
        embedding = embed_model.encode(text_chunk).tolist()
        
        embeddings_to_insert.append((
            sys_id, "incidents", text_chunk, embedding
        ))
        
    # 2. Add some standard SRE Playbook sections to embed for RAG similarity matches
    playbooks = [
        ("playbook-apiserver-timeout", "SRE Playbook: KubeAPIDown & RequestLatencyHigh. Core symptoms include API timeouts. Remediation: Check etcd DB size. If database size exceeds 2GB, trigger compaction. Compacting etcd database releases database space and brings latency back to normal levels. If load is extreme, increase master nodes resource allocations.", "playbooks"),
        ("playbook-dns-errors", "SRE Playbook: CoreDNSErrorsHigh. Core symptoms include packet drops. Remediation: Verify DNS configuration Corefile settings and check for packet losses. Increase CoreDNS pod replicas and adjust upstream DNS timeouts to avoid query starvation under heavy scale stress.", "playbooks"),
        ("playbook-kubevirt-nodes", "SRE Playbook: KubeVirtNoAvailableNodesToRunVMs. Core symptoms include VM scheduling failure. Remediation: Check node labeling and taints. Apply the required hyperconverged virtualization labels (e.g. kubevirt.io/schedulable=true) to eligible worker nodes to re-allocate scheduling domains.", "playbooks"),
        ("playbook-disk-failing", "SRE Playbook: DiskClusterFailing & Ceph Degraded. Core symptoms include high disk write latency and degraded Ceph pools. Remediation: Locate the faulty OSD disk identifier from ceph health logs. Replace the failed disk immediately. Once the new disk is attached, trigger ceph recovery process.", "playbooks"),
        ("playbook-network-flapping", "SRE Playbook: NetworkInterfaceFlapping. Core symptoms include interface loops and Multus failures. Remediation: Inspect Multus NetworkAttachmentDefinition routing rules. Avoid default bridge configurations that create loop conditions. Re-apply validated static routing maps.", "playbooks")
    ]
    
    print("Generating embeddings for standard SRE playbooks...")
    for pb_id, pb_text, table_src in playbooks:
        embedding = embed_model.encode(pb_text).tolist()
        embeddings_to_insert.append((
            pb_id, table_src, pb_text, embedding
        ))
        
    print(f"Inserting {len(embeddings_to_insert)} records into operational_knowledge_embeddings...")
    cur.executemany("""
        INSERT INTO operational_knowledge_embeddings (source_id, source_table, text_chunk, embedding)
        VALUES (%s, %s, %s, %s);
    """, embeddings_to_insert)
    
    conn.commit()
    cur.close()
    print("Vector embeddings successfully saved and HNSW indexed!")

def main():
    conn = None
    try:
        print(f"Connecting to database: {DATABASE_TARGET['dbname']} on {DATABASE_TARGET['host']}:{DATABASE_TARGET['port']}...")
        conn = psycopg2.connect(**DATABASE_TARGET)
        
        # 1. Initialize DB tables, constraints and vectors
        create_schemas(conn)
        
        # 2. Clear tables to support clean replay
        clean_database(conn)
        
        # 3. Insert mock data
        generate_mock_data(conn)
        
        # 4. Generate embeddings
        generate_vector_embeddings(conn)
        
        print("\nAll database simulation tasks completed successfully! Database is ready.")
    except Exception as e:
        print(f"Error executing database simulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
