"""
Incidents router — CRUD + Human-in-the-Loop approval endpoints.

Endpoints:
  GET  /incidents                    → paginated list
  GET  /incidents/{id}               → full detail with timeline
  POST /incidents/{id}/approve       → approve and launch AWX
  POST /incidents/{id}/reject        → reject and page oncall
  POST /incidents/{id}/edit          → edit intent then approve
  POST /incidents/{id}/escalate      → manually escalate to oncall
"""

from __future__ import annotations

import json
import uuid

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query, status

from agents.config import DATABASE_TARGET
from agents.langchain_tools import RemediationIntent
from api.dependencies import get_current_user
from api.schemas import (
    ApproveRequest,
    EditAndApproveRequest,
    EscalateRequest,
    HumanActionResponse,
    IncidentListOut,
    IncidentOut,
    RejectRequest,
)
from api.websocket import manager
from worker.tasks import poll_awx_job, trigger_pagerduty_escalation

router = APIRouter(prefix="/incidents", tags=["Incidents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_incident(cur, incident_id: str) -> dict:
    cur.execute(
        "SELECT id, correlation_id, cluster, namespace, alert_name, hostname, "
        "status, risk_tier, llm_confidence, llm_intent_json, awx_job_id, "
        "created_at, updated_at, resolved_at "
        "FROM incidents_v2 WHERE id = %s",
        (incident_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    cols = [
        "id", "correlation_id", "cluster", "namespace", "alert_name", "hostname",
        "status", "risk_tier", "llm_confidence", "llm_intent_json", "awx_job_id",
        "created_at", "updated_at", "resolved_at",
    ]
    return dict(zip(cols, row))


def _require_status(incident: dict, required: str):
    if incident["status"] != required:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident is in status '{incident['status']}', expected '{required}'",
        )


def _insert_human_action(
    cur,
    incident_id: str,
    user_id: str,
    action: str,
    original_intent: dict | None,
    final_intent: dict | None,
    reason: str,
):
    cur.execute(
        """
        INSERT INTO human_actions
          (incident_id, user_id, action, original_intent_json, final_intent_json, reason)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            incident_id,
            user_id,
            action,
            json.dumps(original_intent) if original_intent else None,
            json.dumps(final_intent) if final_intent else None,
            reason,
        ),
    )


def _insert_timeline(
    cur,
    incident_id: str,
    actor_type: str,
    action: str,
    from_status: str | None,
    to_status: str | None,
    actor_id: str | None = None,
    notes: str | None = None,
    metadata: dict | None = None,
):
    cur.execute(
        """
        INSERT INTO incident_timeline
          (incident_id, actor_type, actor_id, action, from_status, to_status, notes, metadata_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            incident_id,
            actor_type,
            actor_id,
            action,
            from_status,
            to_status,
            notes,
            json.dumps(metadata) if metadata else None,
        ),
    )


# ---------------------------------------------------------------------------
# GET /incidents
# ---------------------------------------------------------------------------


@router.get("", response_model=IncidentListOut)
async def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    cluster: str | None = None,
):
    """Return paginated list of incidents, optionally filtered by status and cluster."""
    offset = (page - 1) * page_size
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    where_clauses = []
    params = []
    if status_filter:
        where_clauses.append("status = %s")
        params.append(status_filter)
    if cluster:
        where_clauses.append("cluster = %s")
        params.append(cluster)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    cur.execute(f"SELECT COUNT(*) FROM incidents_v2 {where_sql}", params)
    total = cur.fetchone()[0]

    cur.execute(
        f"SELECT id, correlation_id, cluster, namespace, alert_name, hostname, "
        f"status, risk_tier, llm_confidence, llm_intent_json, awx_job_id, "
        f"created_at, updated_at, resolved_at "
        f"FROM incidents_v2 {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        params + [page_size, offset],
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    cols = [
        "id", "correlation_id", "cluster", "namespace", "alert_name", "hostname",
        "status", "risk_tier", "llm_confidence", "llm_intent_json", "awx_job_id",
        "created_at", "updated_at", "resolved_at",
    ]
    items = [dict(zip(cols, r)) for r in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ---------------------------------------------------------------------------
# GET /incidents/{id}
# ---------------------------------------------------------------------------


@router.get("/{incident_id}", response_model=IncidentOut)
async def get_incident(incident_id: uuid.UUID):
    """Return full incident detail including timeline, human actions, and LLM decisions."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    incident = _fetch_incident(cur, str(incident_id))

    # Timeline
    cur.execute(
        "SELECT id, timestamp, actor_type, actor_id, action, from_status, to_status, notes, metadata_json "
        "FROM incident_timeline WHERE incident_id = %s ORDER BY timestamp ASC",
        (str(incident_id),),
    )
    tl_cols = ["id", "timestamp", "actor_type", "actor_id", "action", "from_status", "to_status", "notes", "metadata_json"]
    incident["timeline"] = [dict(zip(tl_cols, r)) for r in cur.fetchall()]

    # Human actions
    cur.execute(
        "SELECT id, user_id, action, original_intent_json, final_intent_json, reason, timestamp "
        "FROM human_actions WHERE incident_id = %s ORDER BY timestamp ASC",
        (str(incident_id),),
    )
    ha_cols = ["id", "user_id", "action", "original_intent_json", "final_intent_json", "reason", "timestamp"]
    incident["human_actions"] = [dict(zip(ha_cols, r)) for r in cur.fetchall()]

    # LLM decisions
    cur.execute(
        "SELECT id, prompt_used, raw_llm_output, parsed_intent, confidence, tool_calls_json, timestamp "
        "FROM llm_decisions WHERE incident_id = %s ORDER BY timestamp DESC LIMIT 5",
        (str(incident_id),),
    )
    ld_cols = ["id", "prompt_used", "raw_llm_output", "parsed_intent", "confidence", "tool_calls_json", "timestamp"]
    incident["llm_decisions"] = [dict(zip(ld_cols, r)) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return incident


# ---------------------------------------------------------------------------
# POST /incidents/{id}/approve
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/approve", response_model=HumanActionResponse)
async def approve_incident(
    incident_id: uuid.UUID,
    body: ApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Human approves a HIGH-risk action. Launches AWX job immediately.

    Requirements:
    - Incident must be in PENDING_APPROVAL status.
    - Reason must be non-empty (min 5 chars).
    - User must be authenticated (JWT).
    """
    user_id = current_user["user_id"]
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        _require_status(incident, "PENDING_APPROVAL")

        original_intent = incident.get("llm_intent_json") or {}

        # Launch AWX job with the ORIGINAL validated intent
        from agents.config import USE_MOCK_AWX
        if USE_MOCK_AWX:
            from simulation.mock_client import MockAWXClient
            awx = MockAWXClient()
        else:
            from awx.client import AWXClient
            awx = AWXClient()

        intent = RemediationIntent(**original_intent)
        job_id = awx.launch_job(template_id="1", extra_vars=intent.to_awx_extra_vars())

        # Update incident
        cur.execute(
            "UPDATE incidents_v2 SET status='EXECUTING', awx_job_id=%s, updated_at=NOW() WHERE id=%s",
            (job_id, str(incident_id)),
        )

        # Record human action
        _insert_human_action(cur, str(incident_id), user_id, "APPROVED", original_intent, original_intent, body.reason)

        # Append timeline event
        _insert_timeline(
            cur, str(incident_id), "human", "Human APPROVED — AWX job launched",
            "PENDING_APPROVAL", "EXECUTING", actor_id=user_id,
            notes=body.reason, metadata={"awx_job_id": job_id},
        )

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    # Broadcast WebSocket event
    await manager.broadcast_status_change(
        str(incident_id), "EXECUTING", actor=user_id, notes=body.reason
    )

    # Kick off AWX poll task
    poll_awx_job.apply_async(args=[str(incident_id), job_id], countdown=10, queue="priority")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="EXECUTING",
        message=f"AWX job #{job_id} launched after human approval by {user_id}",
    )


# ---------------------------------------------------------------------------
# POST /incidents/{id}/reject
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/reject", response_model=HumanActionResponse)
async def reject_incident(
    incident_id: uuid.UUID,
    body: RejectRequest,
    current_user: dict = Depends(get_current_user),
):
    """Human rejects the proposed action. Pages oncall."""
    user_id = current_user["user_id"]
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        _require_status(incident, "PENDING_APPROVAL")

        cur.execute(
            "UPDATE incidents_v2 SET status='REJECTED', updated_at=NOW() WHERE id=%s",
            (str(incident_id),),
        )
        _insert_human_action(
            cur, str(incident_id), user_id, "REJECTED",
            incident.get("llm_intent_json"), None, body.reason
        )
        _insert_timeline(
            cur, str(incident_id), "human", "Human REJECTED proposed action",
            "PENDING_APPROVAL", "REJECTED", actor_id=user_id, notes=body.reason,
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    await manager.broadcast_status_change(str(incident_id), "REJECTED", actor=user_id)
    trigger_pagerduty_escalation.delay(str(incident_id), f"Rejected by {user_id}: {body.reason}")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="REJECTED",
        message=f"Incident rejected by {user_id}. Oncall notified.",
    )


# ---------------------------------------------------------------------------
# POST /incidents/{id}/edit
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/edit", response_model=HumanActionResponse)
async def edit_and_approve_incident(
    incident_id: uuid.UUID,
    body: EditAndApproveRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Human edits the proposed intent (e.g. changes target or action) then approves.
    The modified_intent is re-validated against RemediationIntent Pydantic schema
    before AWX is called — never raw JSON from the UI.
    """
    user_id = current_user["user_id"]

    # Validate modified intent against Pydantic schema BEFORE any DB writes
    try:
        intent = RemediationIntent(**body.modified_intent)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Modified intent failed validation: {e}",
        )

    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        _require_status(incident, "PENDING_APPROVAL")
        original_intent = incident.get("llm_intent_json") or {}

        from agents.config import USE_MOCK_AWX
        if USE_MOCK_AWX:
            from simulation.mock_client import MockAWXClient
            awx = MockAWXClient()
        else:
            from awx.client import AWXClient
            awx = AWXClient()

        job_id = awx.launch_job(template_id="1", extra_vars=intent.to_awx_extra_vars())

        cur.execute(
            "UPDATE incidents_v2 SET status='EXECUTING', awx_job_id=%s, "
            "llm_intent_json=%s, updated_at=NOW() WHERE id=%s",
            (job_id, json.dumps(intent.model_dump()), str(incident_id)),
        )
        _insert_human_action(
            cur, str(incident_id), user_id, "EDITED",
            original_intent, intent.model_dump(), body.reason,
        )
        _insert_timeline(
            cur, str(incident_id), "human",
            "Human EDITED intent and APPROVED — AWX job launched",
            "PENDING_APPROVAL", "EXECUTING", actor_id=user_id,
            notes=body.reason,
            metadata={"original_intent": original_intent, "final_intent": intent.model_dump(), "awx_job_id": job_id},
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    await manager.broadcast_status_change(str(incident_id), "EXECUTING", actor=user_id)
    poll_awx_job.apply_async(args=[str(incident_id), job_id], countdown=10, queue="priority")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="EXECUTING",
        message=f"Edited intent approved by {user_id}. AWX job #{job_id} launched.",
    )


# ---------------------------------------------------------------------------
# POST /incidents/{id}/escalate
# ---------------------------------------------------------------------------


@router.post("/{incident_id}/escalate", response_model=HumanActionResponse)
async def escalate_incident(
    incident_id: uuid.UUID,
    body: EscalateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Human manually escalates to oncall from any active status."""
    user_id = current_user["user_id"]
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()

    try:
        incident = _fetch_incident(cur, str(incident_id))
        if incident["status"] in ("RESOLVED", "REJECTED", "ESCALATED"):
            raise HTTPException(
                status_code=409, detail=f"Cannot escalate incident in status {incident['status']}"
            )

        cur.execute(
            "UPDATE incidents_v2 SET status='ESCALATED', updated_at=NOW() WHERE id=%s",
            (str(incident_id),),
        )
        _insert_human_action(
            cur, str(incident_id), user_id, "ESCALATED",
            incident.get("llm_intent_json"), None, body.reason,
        )
        _insert_timeline(
            cur, str(incident_id), "human", "Human manually ESCALATED to oncall",
            incident["status"], "ESCALATED", actor_id=user_id, notes=body.reason,
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    await manager.broadcast_status_change(str(incident_id), "ESCALATED", actor=user_id)
    trigger_pagerduty_escalation.delay(str(incident_id), f"Manually escalated by {user_id}: {body.reason}")

    return HumanActionResponse(
        incident_id=incident_id,
        new_status="ESCALATED",
        message=f"Escalated by {user_id}. Oncall paged.",
    )
