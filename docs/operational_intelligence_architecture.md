# AI-Powered OpenShift SRE Incident Intelligence Platform: Architectural Design

This document details the complete production-grade architecture, data schemas, ingestion logic, and agent query strategy for the ServiceNow alert-incident correlation and operational recurrence analysis engine.

---

## 1. Architecture Flow Diagram

```text
[Alertmanager alerts] ──> [ Kafka Broker ] 
                                │
                                ▼
                       [Normalization Engine] (fingerprint hash)
                                │
                                ▼
  [ServiceNow Pulls (30m)] ──> [Ingestion Pipeline] ──> [pgvector (HNSW) Embeddings]
                                │               │
                       (Upsert State)       (Append History)
                                │               │
                                ▼               ▼
                      [Operational Relational Database]
                           (PostgreSQL + pgvector)
                                │
                                ▼
                      [SRE Recommendation Agent] 
                   (Tool Calls via low-latency SQL)
```

---

## 2. Database Technology Selection & Critique

### The Winner: PostgreSQL (with `pgvector` & `JSONB`)
To store SRE operational telemetry and run low-latency AI queries, **PostgreSQL** is the only correct selection.

* **Unified Relational & Vector Space**: Allows joining transactional metrics (e.g. cluster version, incident status, reopen history) directly with HNSW vector similarity search in a **single query**. No data duplication across databases.
* **JSONB Capabilities**: Native binary JSON storage with GIN indexes allows us to preserve raw API payloads while indexing critical keys, avoiding slow table-scans.
* **Deduplication Constraints**: Strict unique indexes and transactional `UPSERT` guarantee zero duplicate entries under high concurrency.
* **HNSW Indexing**: Native pgvector implementation supports highly optimized distance metrics (`<->` cosine/L2) inside a proven, ACID-compliant database.

### Critique of Alternatives

* **MongoDB (Document DB)**: Naive choice. While good for schema-less storage, it fails catastrophically at relational joins required to compute historical recurrence across separate `alert_occurrences`, `incidents`, and `incident_snapshots` tables. Running multiple aggregation lookups under load introduces extreme latency.
* **Elasticsearch (Search Engine)**: Overkill and poor for operational state. It is not transactional, lacks strict foreign keys, has eventual consistency delays, and lacks robust relational constraint management. Running an upsert-heavy deduplication engine on Elasticsearch is highly inefficient.
* **Pinecone (Vector DB Only)**: Destroys the integrity of the design. You cannot perform operational joins (e.g. *“find similar incidents where status was closed AND reopen_count > 0 AND cluster_id = 'prod-1'”*). You are forced to maintain a separate relational DB, introducing double-writes and sync lag.
* **Cassandra (Wide-Column Store)**: Completely unsuitable. SRE telemetry analysis requires ad-hoc queries, aggregates (e.g., `MTTR` trends, flapping trends), and joins. Cassandra's query model is static and cannot support dynamic agent tool queries.

---

## 3. Deduplication and Fingerprinting Strategy

### What Constitutes a Duplicate?
A duplicate occurs when the same operational event (e.g. alert or incident state transition) is stored multiple times, causing artificial count inflation, corrupt MTTR calculation, and bad recurrence analysis.

### Why Alertname-Only Deduplication is Dangerous
Deduplicating by `alertname` alone means if two different clusters (or different namespaces on the same cluster) fire a `KubeAPIDown` alert at the same time, the system will merge them into a single incident. This masks critical production outages and results in invalid metrics.

### Secure Fingerprinting Model
We generate a deterministic `SHA-256` fingerprint for alert occurrences based on:
`SHA256(alertname + namespace + operator_component + cluster_id)`

This fingerprint uniquely identifies the operational alert instance.

* **Unique Constraints**: Table `alert_occurrences` enforces a `PRIMARY KEY` on this fingerprint.
* **UPSERT Strategy**: Ingestion uses `ON CONFLICT (fingerprint) DO UPDATE SET occurrence_count = occurrence_count + 1, last_seen = NOW()`.
* **Snapshot Uniqueness Model**: To avoid duplicate historical records, snapshots enforce a unique constraint on `(sys_id, sys_updated_on)`. If ServiceNow updates the same ticket twice within a polling window, only the latest state is kept.

---

## 4. Schema DDL Definition

```sql
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Clusters Table
CREATE TABLE IF NOT EXISTS clusters (
    cluster_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    openshift_version VARCHAR(20) NOT NULL,
    environment VARCHAR(20) NOT NULL CHECK (environment IN ('production', 'staging', 'development', 'dr'))
);
CREATE INDEX IF NOT EXISTS idx_clusters_env ON clusters(environment);

-- 2. Alert Occurrence Tracking (Deduplicated Stream)
CREATE TABLE IF NOT EXISTS alert_occurrences (
    fingerprint VARCHAR(64) PRIMARY KEY, -- SHA256 of identifier attributes
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

-- 3. Red Hat Cases
CREATE TABLE IF NOT EXISTS redhat_cases (
    case_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    created_on TIMESTAMP NOT NULL,
    closed_on TIMESTAMP,
    resolution TEXT
);

-- 4. Current ServiceNow Incident State
CREATE TABLE IF NOT EXISTS incidents (
    sys_id VARCHAR(32) PRIMARY KEY, -- ServiceNow sys_id UUID
    number VARCHAR(20) UNIQUE NOT NULL, -- INC0012345
    state VARCHAR(30) NOT NULL, -- New, Work in Progress, Resolved, Closed, Reopened
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

-- 5. Incident Worknotes Timeline
CREATE TABLE IF NOT EXISTS incident_worknotes (
    id SERIAL PRIMARY KEY,
    sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
    worknote_text TEXT NOT NULL,
    created_on TIMESTAMP NOT NULL,
    sentiment_label VARCHAR(10) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
    sentiment_score NUMERIC(5, 4)
);
CREATE INDEX IF NOT EXISTS idx_worknotes_sys_id ON incident_worknotes(sys_id, created_on DESC);

-- 6. Historical Ticket State Snapshots (Lifecycle Track)
CREATE TABLE IF NOT EXISTS incident_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    sys_id VARCHAR(32) NOT NULL REFERENCES incidents(sys_id) ON DELETE CASCADE,
    state VARCHAR(30) NOT NULL,
    sys_updated_on TIMESTAMP NOT NULL,
    changed_by VARCHAR(100) NOT NULL,
    worknotes_added TEXT,
    sentiment_label VARCHAR(10),
    sentiment_score NUMERIC(5, 4),
    CONSTRAINT unique_sys_id_updated UNIQUE (sys_id, sys_updated_on)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_lookup ON incident_snapshots(sys_id, sys_updated_on DESC);

-- 7. Recurrence Intelligence Aggregates (Long-term retention)
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

-- 8. Embeddings Table (Vector Storage for playbooks & post-mortems)
CREATE TABLE IF NOT EXISTS operational_knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(100) NOT NULL,
    source_table VARCHAR(50) NOT NULL,
    text_chunk TEXT NOT NULL,
    embedding vector(384) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vector_hnsw ON operational_knowledge_embeddings USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);
```

---

## 5. Schema Mechanics & Retention Policy

| Schema / Table | Update Behavior | Retention Strategy | Critique of Bad Approaches |
| :--- | :--- | :--- | :--- |
| **`alert_occurrences`** | `UPSERT` on fingerprint match. | Short-term (e.g. 14 days) for active count resets. | *Bad: Deleting active alert records means recurrence calculation starts from zero, losing flapping trends.* |
| **`incidents`** | `UPSERT` on `sys_id`. | Long-term (Indefinitely) as operational metadata. | *Bad: Storing only raw JSON makes searching/sorting slow and breaks SRE agent tool-calling APIs.* |
| **`incident_snapshots`** | Append only on transition detect. | Medium-term (e.g., 90 days) for SLA metrics. | *Bad: Storing a snapshot on every poll leads to massive storage bloat. Store only when state changes.* |
| **`recurrence_intelligence`** | Calculated update periodically. | Indefinite. | *Bad: Running recalculations on raw logs at search time is too slow. Maintain aggregated statistics.* |
| **`operational_knowledge_embeddings`** | Write once, delete on source delete. | Indefinite (Updated on post-mortem publication). | *Bad: Embedding raw JSON yields poor semantic similarity. Embed only cleaned playbooks/summaries.* |

---

## 6. JSON Normalization & Flat Fields Strategy

### Sample Raw ServiceNow Payload
```json
{
  "sys_id": "8a3a41b2c0a80164010b7a8a1132c3f8",
  "number": "INC0049281",
  "state": "Work in Progress",
  "sys_created_on": "2026-05-22 10:00:00",
  "sys_updated_on": "2026-05-22 10:30:00",
  "short_description": "CoreDNSErrorsHigh firing on cluster prod-us-east-1",
  "u_cluster_id": "prod-us-east-1",
  "u_alert_name": "CoreDNSErrorsHigh",
  "u_namespace": "openshift-dns",
  "u_operator": "cluster-dns-operator",
  "u_severity": "critical",
  "u_redhat_case": "53029103",
  "comments": "Worknote: Checked pod placement. Network looks saturated.",
  "close_notes": ""
}
```

### Extraction and Normalization

* **Flat fields extracted**: `sys_id`, `number`, `state`, `sys_created_on`, `sys_updated_on`, `short_description`, `cluster_id` (from `u_cluster_id`), `redhat_case_id` (from `u_redhat_case`).
* **JSONB fields**: The raw ServiceNow JSON response is kept intact inside `raw_payload` for compliance and schema evolution (to support mapping fields added in future ServiceNow releases).
* **Critique of full dynamic flattening**: Flattening all 300+ ServiceNow internal fields into SQL columns is a maintenance nightmare. Most fields (e.g., assignment groups, urgency dropdowns, sys_tags) are metadata junk that change often and disrupt indexing performance if stored as columns.

---

## 7. Ingestion Pipeline Mechanics

The ingestion script checks for updates using `sys_updated_on > LAST_POLL_TIME`.

```python
# Pseudo-code for Ingestion Pipeline
def ingest_pipeline():
    # 1. Fetch updated tickets from ServiceNow
    records = fetch_servicenow_delta(last_poll_time)
    
    for record in records:
        # 2. Extract and Normalize
        normalized = normalize_fields(record)
        
        # 3. Handle Alert Occurrence (Upsert)
        fingerprint = generate_fingerprint(normalized)
        upsert_alert(fingerprint, normalized)
        
        # 4. Handle Red Hat Case
        if normalized['redhat_case_id']:
            upsert_redhat_case(normalized['redhat_case_id'])
            
        # 5. Upsert Incident State
        sentiment = analyze_sentiment(normalized['worknotes'])
        upsert_incident(normalized, fingerprint, sentiment)
        
        # 6. Append Snapshot on State Transition
        if state_has_changed(normalized):
            append_snapshot(normalized, sentiment)
            
        # 7. Update Recurrence Analytics Table
        recalculate_recurrence_metrics(fingerprint)
```

### Ingestion SQL Upsert Example (Incident table)
```sql
INSERT INTO incidents (sys_id, number, state, sys_created_on, sys_updated_on, short_description, cluster_id, alert_fingerprint, flapping_count, redhat_case_id, sentiment_label, sentiment_score, raw_payload)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (sys_id)
DO UPDATE SET 
    state = EXCLUDED.state,
    sys_updated_on = EXCLUDED.sys_updated_on,
    flapping_count = incidents.flapping_count + EXCLUDED.flapping_count,
    redhat_case_id = EXCLUDED.redhat_case_id,
    sentiment_label = EXCLUDED.sentiment_label,
    sentiment_score = EXCLUDED.sentiment_score,
    raw_payload = EXCLUDED.raw_payload;
```

---

## 8. Agent Tool-Calling SQL Interfaces

### Q1: Has this alert occurred before, and how many times?
```sql
SELECT total_occurrences, total_incidents, reopen_count 
FROM recurrence_intelligence 
WHERE fingerprint = %s;
```
* **Tool Response JSON**:
  ```json
  {"fingerprint": "a2b9...", "total_occurrences": 12, "total_incidents": 4, "reopen_count": 2}
  ```

### Q2: Was the previous resolution temporary?
```sql
SELECT state, worknotes_added, sentiment_label 
FROM incident_snapshots 
WHERE sys_id = %s AND state = 'Resolved' 
ORDER BY sys_updated_on DESC LIMIT 1;
```
* **Tool Response JSON**:
  ```json
  {"state": "Resolved", "closing_comment": "Applied temporary workaround (deleted pod to trigger reschedule)", "sentiment": "neutral"}
  ```

### Q3: Is the cluster noisy or showing recurrence after closure?
```sql
SELECT count(*), environment 
FROM incidents i
JOIN clusters c ON i.cluster_id = c.cluster_id
WHERE i.state = 'Closed' AND i.cluster_id = %s 
  AND i.sys_updated_on > NOW() - INTERVAL '7 days';
```

---

## 9. Vector Search / RAG Strategy

* **What to Embed**: Cleaned Playbooks, SRE Post-Mortem Summaries, and Red Hat Case Resolution summaries.
* **What NOT to Embed**: Raw JSON structures, timestamps, or system configuration logs.
* **Why raw JSON embedding is poor design**: Embeddings capture semantic meaning. Raw JSON strings like `{"sys_id": "abc", "status": "closed"}` contain structural syntax and UUID strings that degrade vector quality and reduce search relevancy.

### Retrieval SQL Join (Relational + Semantic Search)
```sql
SELECT source_id, source_table, text_chunk, (embedding <-> %s::vector) AS distance
FROM operational_knowledge_embeddings
WHERE source_table = 'playbooks'
ORDER BY embedding <-> %s::vector
LIMIT 3;
```
