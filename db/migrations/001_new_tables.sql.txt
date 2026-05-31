-- =============================================================================
-- Migration 001: New tables for LangChain + Incident Tracking UI
-- Existing tables (incidents, alert_occurrences, clusters, etc.) are UNTOUCHED.
-- Run with: psql -U $DB_USER -d $DB_NAME -f 001_new_tables.sql
-- =============================================================================

-- Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- incidents_v2: Core incident record (replaces ad-hoc SNOW integration)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidents_v2 (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id   TEXT UNIQUE,
    cluster          TEXT NOT NULL,
    namespace        TEXT NOT NULL,
    alert_name       TEXT NOT NULL,
    hostname         TEXT,
    status           TEXT NOT NULL DEFAULT 'RECEIVED'
                         CHECK (status IN (
                             'RECEIVED','ANALYZING','PENDING_APPROVAL',
                             'EXECUTING','VERIFYING','RESOLVED',
                             'REJECTED','ESCALATED','FAILED'
                         )),
    risk_tier        TEXT CHECK (risk_tier IN ('LOW','HIGH','ESCALATE')),
    llm_confidence   NUMERIC(5,4),
    llm_intent_json  JSONB,
    analysis_summary TEXT,
    escalate_to      TEXT,
    awx_job_id       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incidents_v2_status
    ON incidents_v2(status);
CREATE INDEX IF NOT EXISTS idx_incidents_v2_cluster_alert
    ON incidents_v2(cluster, alert_name);
CREATE INDEX IF NOT EXISTS idx_incidents_v2_created_at
    ON incidents_v2(created_at DESC);

-- ---------------------------------------------------------------------------
-- incident_timeline: Append-only audit log — NEVER UPDATE ROWS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incident_timeline (
    id            BIGSERIAL PRIMARY KEY,
    incident_id   UUID NOT NULL REFERENCES incidents_v2(id) ON DELETE CASCADE,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_type    TEXT NOT NULL CHECK (actor_type IN ('agent','human','system')),
    actor_id      TEXT,
    action        TEXT NOT NULL,
    from_status   TEXT,
    to_status     TEXT,
    notes         TEXT,
    metadata_json JSONB
);

CREATE INDEX IF NOT EXISTS idx_timeline_incident_id
    ON incident_timeline(incident_id, timestamp ASC);

-- ---------------------------------------------------------------------------
-- human_actions: Explicit record of every human decision
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS human_actions (
    id                   BIGSERIAL PRIMARY KEY,
    incident_id          UUID NOT NULL REFERENCES incidents_v2(id) ON DELETE CASCADE,
    user_id              TEXT NOT NULL,
    action               TEXT NOT NULL CHECK (action IN ('APPROVED','REJECTED','EDITED','ESCALATED')),
    original_intent_json JSONB,
    final_intent_json    JSONB,
    reason               TEXT NOT NULL,
    timestamp            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_human_actions_incident
    ON human_actions(incident_id, timestamp DESC);

-- ---------------------------------------------------------------------------
-- llm_decisions: Full LLM reasoning stored for every agent run
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_decisions (
    id             BIGSERIAL PRIMARY KEY,
    incident_id    UUID NOT NULL REFERENCES incidents_v2(id) ON DELETE CASCADE,
    prompt_used    TEXT,
    raw_llm_output TEXT,
    parsed_intent  JSONB,
    confidence     NUMERIC(5,4),
    tool_calls_json JSONB,
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_decisions_incident
    ON llm_decisions(incident_id, timestamp DESC);

-- ---------------------------------------------------------------------------
-- Function: auto-update incidents_v2.updated_at on any row change
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_incidents_v2_updated_at ON incidents_v2;
CREATE TRIGGER trg_incidents_v2_updated_at
    BEFORE UPDATE ON incidents_v2
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
