-- ============================================================
-- Migration: shift_handovers v2 — Rich structured fields
-- Safe to run on existing data; all new columns have defaults.
-- ============================================================

-- Ensure the table exists first (idempotent baseline)
CREATE TABLE IF NOT EXISTS shift_handovers (
    id         UUID PRIMARY KEY,
    author     VARCHAR NOT NULL,
    message    TEXT    NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- 1. Shift Identifier — outgoing engineer / shift name
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS shift_identifier VARCHAR DEFAULT '' NOT NULL;

-- 2. Cluster — target cluster (e.g. nzclu101) or 'ALL'
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS cluster VARCHAR DEFAULT 'ALL' NOT NULL;

-- 3. Handover Type
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'handover_type_enum') THEN
        CREATE TYPE handover_type_enum AS ENUM (
            'handover',
            'maintenance',
            'upgrade',
            'operator_upgrade',
            'incident_followup',
            'change_freeze',
            'escalation'
        );
    END IF;
END$$;

ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS handover_type handover_type_enum DEFAULT 'handover' NOT NULL;

-- 4. Priority
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'handover_priority_enum') THEN
        CREATE TYPE handover_priority_enum AS ENUM ('low', 'medium', 'high', 'critical');
    END IF;
END$$;

ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS priority handover_priority_enum DEFAULT 'medium' NOT NULL;

-- 5. Action Required — does next shift need to take action?
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS action_required BOOLEAN DEFAULT FALSE NOT NULL;

-- 6. Related Incidents — comma-separated incident UUIDs
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS related_incidents TEXT DEFAULT '' NOT NULL;

-- 7. Maintenance Windows
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS start_time TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS end_time TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 8. Resolution Logic
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS resolution_notes TEXT NULL;

-- 9. Upgrades
ALTER TABLE shift_handovers
    ADD COLUMN IF NOT EXISTS upgraded_version TEXT NULL,
    ADD COLUMN IF NOT EXISTS operator_name TEXT NULL;

-- Backfill shift_identifier from existing author column where empty
UPDATE shift_handovers
    SET shift_identifier = author
    WHERE shift_identifier = '';

-- Index on cluster and type for fast filtering
CREATE INDEX IF NOT EXISTS idx_shift_handovers_cluster       ON shift_handovers (cluster);
CREATE INDEX IF NOT EXISTS idx_shift_handovers_handover_type ON shift_handovers (handover_type);
CREATE INDEX IF NOT EXISTS idx_shift_handovers_priority      ON shift_handovers (priority);
CREATE INDEX IF NOT EXISTS idx_shift_handovers_created_at    ON shift_handovers (created_at DESC);
