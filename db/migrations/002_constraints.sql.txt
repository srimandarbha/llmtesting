-- =============================================================================
-- Migration 002: Performance indexes
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Blast-radius query helper: counts executing incidents per cluster
-- (used in Celery task before launching AWX job)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_incidents_v2_executing_cluster
    ON incidents_v2 (cluster, status, updated_at)
    WHERE status = 'EXECUTING';

-- ---------------------------------------------------------------------------
-- Celery SQLAlchemy transport tables
-- These are created automatically by Celery on first connection,
-- but defining them here ensures proper permissions.
-- ---------------------------------------------------------------------------
-- Celery will auto-create: celery_taskmeta, celery_tasksetmeta, kombu_queue, kombu_message
