"""Alert ingestion router — POST /alerts/ingest"""

from __future__ import annotations

import json
import uuid

import psycopg2
from fastapi import APIRouter, HTTPException, status

from agents.config import DATABASE_TARGET, DEDUP_WINDOW_MINUTES
from api.schemas import AlertIngestRequest, AlertIngestResponse
from worker.tasks import run_agent_pipeline

router = APIRouter(prefix="/alerts", tags=["Alert Ingestion"])


@router.post(
    "/ingest",
    response_model=AlertIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a normalized alert event and start the agent pipeline",
)
async def ingest_alert(payload: AlertIngestRequest):
    """
    Accepts a normalized alert from Kafka/webhook and creates a new incident.

    - Deduplication: Checks if the exact same alert on the same cluster 
      and namespace has already fired in the last `DEDUP_WINDOW_MINUTES` minutes.
      If yes, we skip creating a new incident to avoid flooding the system.
    - On success: creates the incident record and enqueues the Celery pipeline task.
    """
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        # Deduplication check
        cur.execute(
            """
            SELECT id, status FROM incidents_v2
            WHERE alert_name = %s AND cluster = %s AND namespace = %s
              AND created_at > NOW() - (INTERVAL '1 minute' * %s)
              AND status NOT IN ('REJECTED', 'ESCALATED', 'FAILED', 'RESOLVED')
            ORDER BY created_at DESC LIMIT 1;
            """,
            (payload.alert_name, payload.cluster, payload.namespace, DEDUP_WINDOW_MINUTES),
        )
        existing = cur.fetchone()
        if existing:
            existing_id, existing_status = existing
            return AlertIngestResponse(
                incident_id=uuid.UUID(str(existing_id)),
                status=existing_status,
                message=f"Duplicate alert deduplicated. Existing incident: {existing_id}",
            )

        # Create new incident
        incident_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO incidents_v2
              (id, correlation_id, cluster, namespace, alert_name, hostname, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'RECEIVED')
            """,
            (
                incident_id,
                payload.correlation_id,
                payload.cluster,
                payload.namespace,
                payload.alert_name,
                payload.hostname,
            ),
        )

        # Write initial timeline event
        cur.execute(
            """
            INSERT INTO incident_timeline
              (incident_id, actor_type, action, from_status, to_status, notes)
            VALUES (%s, 'system', 'Alert received and incident created', NULL, 'RECEIVED',
                    %s)
            """,
            (incident_id, f"correlation_id={payload.correlation_id}"),
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create incident: {e}")
    finally:
        cur.close()
        conn.close()

    # Enqueue LangChain agent pipeline (async, non-blocking)
    run_agent_pipeline.apply_async(
        args=[
            incident_id,
            payload.alert_name,
            payload.namespace,
            payload.cluster,
            payload.hostname,
            payload.correlation_id,
            payload.awx_template_id,
        ],
        queue="default",
    )

    return AlertIngestResponse(
        incident_id=uuid.UUID(incident_id),
        status="RECEIVED",
        message="Incident created and agent pipeline enqueued.",
    )
