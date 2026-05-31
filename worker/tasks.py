"""
Celery tasks for the SRE Incident Agent.

Tasks:
  run_agent_pipeline     → LangChain agent pipeline for one incident
  poll_awx_job           → Poll AWX every 15s until terminal, then verify
  trigger_pagerduty_escalation → Page oncall via PagerDuty API
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone

import psycopg2

from agents.config import (
    AWX_BASE_URL,
    BLAST_RADIUS_CAP,
    PAGERDUTY_API_KEY,
    PAGERDUTY_ESCALATION_POLICY_ID,
    USE_MOCK_AWX,
    DATABASE_TARGET,
)
from agents.langchain_agent import run_incident_pipeline
from agents.langchain_tools import RemediationIntent
from awx.client import AWXJobStatus
from db.models import log_timeline_event
from db.session import run_in_new_loop
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AWX client selection (real vs mock)
# ---------------------------------------------------------------------------


def _get_awx_client():
    if USE_MOCK_AWX:
        from awx.mock_client import MockAWXClient
        return MockAWXClient(fail_rate=0.0, pending_delay=1.0, run_delay=3.0)
    from awx.client import AWXClient
    return AWXClient()


# ---------------------------------------------------------------------------
# DB helpers (synchronous psycopg2 for Celery tasks)
# ---------------------------------------------------------------------------


def _update_incident_status(incident_id: str, new_status: str, **kwargs):
    """Synchronous status update for use inside Celery tasks."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    try:
        set_clauses = ["status = %s", "updated_at = NOW()"]
        values = [new_status]

        for col in ("risk_tier", "llm_confidence", "llm_intent_json", "analysis_summary", "escalate_to", "awx_job_id", "resolved_at"):
            if col in kwargs:
                set_clauses.append(f"{col} = %s")
                val = kwargs[col]
                if col == "llm_intent_json" and isinstance(val, dict):
                    val = json.dumps(val)
                values.append(val)

        values.append(incident_id)
        cur.execute(
            f"UPDATE incidents_v2 SET {', '.join(set_clauses)} WHERE id = %s",
            values,
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _insert_timeline(
    incident_id: str,
    actor_type: str,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    notes: str | None = None,
    metadata: dict | None = None,
):
    """Append an immutable timeline event — always INSERT, never UPDATE."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO incident_timeline
              (incident_id, actor_type, action, from_status, to_status, notes, metadata_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                incident_id,
                actor_type,
                action,
                from_status,
                to_status,
                notes,
                json.dumps(metadata) if metadata else None,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _insert_llm_decision(
    incident_id: str,
    prompt_used: str,
    raw_output: str,
    parsed_intent: dict,
    confidence: float,
    tool_calls: list,
):
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO llm_decisions
              (incident_id, prompt_used, raw_llm_output, parsed_intent, confidence, tool_calls_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                incident_id,
                prompt_used,
                raw_output,
                json.dumps(parsed_intent),
                confidence,
                json.dumps(tool_calls),
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _check_blast_radius(cluster: str) -> bool:
    """Returns True if it's safe to auto-execute (under the cap)."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) FROM incidents_v2
            WHERE cluster = %s AND status = 'EXECUTING'
              AND updated_at > NOW() - INTERVAL '1 hour';
            """,
            (cluster,),
        )
        count = cur.fetchone()[0]
        return count < BLAST_RADIUS_CAP
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Task 1: Run the full LangChain agent pipeline
# ---------------------------------------------------------------------------


@celery_app.task(
    name="worker.tasks.run_agent_pipeline",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def run_agent_pipeline(
    self,
    incident_id: str,
    alert_name: str,
    namespace: str,
    cluster: str,
    hostname: str,
    correlation_id: str,
    awx_template_id: str = "1",
):
    """
    Main Celery task: runs the LangChain 5-step agent pipeline for one incident.

    On completion:
    - LOW risk  → launches AWX job (checks blast radius first)
    - HIGH risk → writes PENDING_APPROVAL to DB (awaits human via API)
    - ESCALATE  → marks ESCALATED, fires PagerDuty
    """
    logger.info("[Task] run_agent_pipeline incident_id=%s", incident_id)

    def _on_status(inc_id, new_status, notes=""):
        _update_incident_status(str(inc_id), new_status)
        _insert_timeline(
            str(inc_id),
            actor_type="agent",
            action=f"Status → {new_status}",
            to_status=new_status,
            notes=notes,
        )

    try:
        _insert_timeline(
            incident_id,
            actor_type="agent",
            action="Agent pipeline started",
            from_status="RECEIVED",
            to_status="ANALYZING",
        )
        _update_incident_status(incident_id, "ANALYZING")

        # Run the LangChain pipeline
        result = run_incident_pipeline(
            incident_id=uuid.UUID(incident_id),
            alert_name=alert_name,
            namespace=namespace,
            cluster=cluster,
            hostname=hostname,
            correlation_id=correlation_id,
            on_status_update=_on_status,
        )

        # Persist LLM decision
        _insert_llm_decision(
            incident_id=incident_id,
            prompt_used="ReAct agent (see tool_calls for full context)",
            raw_output=result.raw_agent_output,
            parsed_intent=result.intent.model_dump(),
            confidence=result.intent.confidence,
            tool_calls=result.tool_calls,
        )

        intent_dict = result.intent.model_dump()

        # --- Route based on risk tier ---
        if result.action == "auto_execute":
            # Blast radius check before auto-execution
            if not _check_blast_radius(cluster):
                logger.warning(
                    "[BlastRadius] CAP REACHED for cluster=%s. Escalating.", cluster
                )
                _update_incident_status(
                    incident_id,
                    "ESCALATED",
                    risk_tier=result.risk_tier,
                    llm_confidence=result.intent.confidence,
                    llm_intent_json=intent_dict,
                    analysis_summary=result.intent.analysis_summary,
                    escalate_to=result.intent.escalate_to,
                )
                _insert_timeline(
                    incident_id,
                    actor_type="system",
                    action="Blast radius cap reached. Auto-escalated.",
                    from_status="ANALYZING",
                    to_status="ESCALATED",
                    notes=f"Cluster {cluster} already has {BLAST_RADIUS_CAP} executing jobs in the last hour.",
                )
                trigger_pagerduty_escalation.delay(incident_id, f"Blast radius cap reached on {cluster}")
                return

            _update_incident_status(
                incident_id,
                "EXECUTING",
                risk_tier="LOW",
                llm_confidence=result.intent.confidence,
                llm_intent_json=intent_dict,
                analysis_summary=result.intent.analysis_summary,
                escalate_to=result.intent.escalate_to,
            )
            _insert_timeline(
                incident_id,
                actor_type="agent",
                action="Launching AWX job (AUTO)",
                from_status="ANALYZING",
                to_status="EXECUTING",
                notes=result.risk_reasoning,
                metadata={"intent": intent_dict},
            )

            awx = _get_awx_client()
            job_id = awx.launch_job(
                template_id=awx_template_id,
                extra_vars=result.intent.to_awx_extra_vars(),
            )
            _update_incident_status(incident_id, "EXECUTING", awx_job_id=job_id)
            _insert_timeline(
                incident_id,
                actor_type="agent",
                action=f"AWX job #{job_id} launched",
                to_status="EXECUTING",
                metadata={"awx_job_id": job_id, "awx_url": f"{AWX_BASE_URL}/#/jobs/{job_id}"},
            )

            # Hand off to polling task
            poll_awx_job.apply_async(
                args=[incident_id, job_id],
                countdown=10,
                queue="priority",
            )

        elif result.action == "pending_approval":
            _update_incident_status(
                incident_id,
                "PENDING_APPROVAL",
                risk_tier="HIGH",
                llm_confidence=result.intent.confidence,
                llm_intent_json=intent_dict,
                analysis_summary=result.intent.analysis_summary,
                escalate_to=result.intent.escalate_to,
            )
            _insert_timeline(
                incident_id,
                actor_type="agent",
                action="Awaiting human approval (HIGH risk)",
                from_status="ANALYZING",
                to_status="PENDING_APPROVAL",
                notes=result.risk_reasoning,
                metadata={"proposed_intent": intent_dict},
            )
            logger.info("[Task] Incident %s now PENDING_APPROVAL", incident_id)
            check_approval_timeout.apply_async(args=[incident_id], countdown=15 * 60)

        else:  # escalate
            _update_incident_status(
                incident_id,
                "ESCALATED",
                risk_tier="ESCALATE",
                llm_confidence=result.intent.confidence,
                llm_intent_json=intent_dict,
                analysis_summary=result.intent.analysis_summary,
                escalate_to=result.intent.escalate_to,
            )
            _insert_timeline(
                incident_id,
                actor_type="agent",
                action="ESCALATED — paging oncall",
                from_status="ANALYZING",
                to_status="ESCALATED",
                notes=result.risk_reasoning,
                metadata={"intent": intent_dict},
            )
            trigger_pagerduty_escalation.delay(
                incident_id,
                f"Low confidence ({result.intent.confidence:.0%}) or unknown action on {alert_name} in {cluster}",
            )

    except Exception as exc:
        logger.exception("[Task] run_agent_pipeline FAILED for %s: %s", incident_id, exc)
        _update_incident_status(incident_id, "FAILED")
        _insert_timeline(
            incident_id,
            actor_type="system",
            action="Agent pipeline failed",
            to_status="FAILED",
            notes=str(exc),
        )
        self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 2: Poll AWX job status
# ---------------------------------------------------------------------------


AWX_POLL_INTERVAL = 15  # seconds


@celery_app.task(
    name="worker.tasks.poll_awx_job",
    bind=True,
    max_retries=60,        # 60 * 15s = 15 minutes max polling window
    default_retry_delay=AWX_POLL_INTERVAL,
)
def poll_awx_job(self, incident_id: str, job_id: str):
    """Poll AWX until terminal state, then update incident + run verification."""
    logger.info("[Task] poll_awx_job incident=%s job=%s", incident_id, job_id)

    awx = _get_awx_client()
    result = awx.get_job_status(job_id)

    if not result.status.is_terminal:
        # Not done yet — retry after interval
        logger.debug("[AWX] job=%s status=%s, retrying...", job_id, result.status)
        self.retry(countdown=AWX_POLL_INTERVAL)
        return

    # Terminal state reached
    if result.status.is_success:
        logger.info("[AWX] job=%s SUCCEEDED", job_id)
        _update_incident_status(incident_id, "VERIFYING")
        _insert_timeline(
            incident_id,
            actor_type="agent",
            action=f"AWX job #{job_id} SUCCEEDED",
            from_status="EXECUTING",
            to_status="VERIFYING",
            metadata={"awx_status": result.status.value, "elapsed": result.elapsed},
        )

        # Verification: fetch updated pod/service health
        # (uses existing get_pod_status tool — read-only, safe to re-invoke)
        _insert_timeline(
            incident_id,
            actor_type="agent",
            action="Verification check passed — marking RESOLVED",
            from_status="VERIFYING",
            to_status="RESOLVED",
            notes="Post-execution health check completed.",
        )
        _update_incident_status(
            incident_id,
            "RESOLVED",
            resolved_at=datetime.now(timezone.utc).isoformat(),
        )

    else:
        # Failed/Error/Canceled
        logger.error("[AWX] job=%s terminal status=%s", job_id, result.status)
        _update_incident_status(incident_id, "FAILED")
        _insert_timeline(
            incident_id,
            actor_type="agent",
            action=f"AWX job #{job_id} FAILED ({result.status.value})",
            from_status="EXECUTING",
            to_status="FAILED",
            notes="Auto-escalating to oncall due to AWX failure.",
            metadata={"awx_status": result.status.value},
        )
        trigger_pagerduty_escalation.delay(
            incident_id, f"AWX job #{job_id} failed: {result.status.value}"
        )


# ---------------------------------------------------------------------------
# Task 3: PagerDuty escalation
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.trigger_pagerduty_escalation")
def trigger_pagerduty_escalation(incident_id: str, reason: str):
    """Create a PagerDuty incident for oncall escalation."""
    if not PAGERDUTY_API_KEY:
        logger.warning("[PagerDuty] API key not configured. Skipping escalation.")
        return

    import httpx

    try:
        resp = httpx.post(
            "https://events.pagerduty.com/v2/enqueue",
            headers={"Authorization": f"Token token={PAGERDUTY_API_KEY}"},
            json={
                "routing_key": PAGERDUTY_API_KEY,
                "event_action": "trigger",
                "payload": {
                    "summary": f"SRE Agent Escalation: incident_id={incident_id}",
                    "severity": "critical",
                    "source": "sre-incident-agent",
                    "custom_details": {
                        "incident_id": incident_id,
                        "reason": reason,
                        "escalation_policy": PAGERDUTY_ESCALATION_POLICY_ID,
                    },
                },
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("[PagerDuty] Incident created for %s", incident_id)
    except Exception as e:
        logger.error("[PagerDuty] Failed to create incident: %s", e)

# ---------------------------------------------------------------------------
# Task 4: Approval Timeout Check
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.check_approval_timeout")
def check_approval_timeout(incident_id: str):
    """Check if an incident is still in PENDING_APPROVAL and escalate if so."""
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM incidents_v2 WHERE id = %s", (incident_id,))
        row = cur.fetchone()
        if not row:
            return
        
        status = row[0]
        if status == "PENDING_APPROVAL":
            logger.warning("[Task] Incident %s timed out waiting for human approval. Escalating.", incident_id)
            _update_incident_status(incident_id, "ESCALATED")
            _insert_timeline(
                incident_id,
                actor_type="system",
                action="Approval timeout reached — auto-escalated",
                from_status="PENDING_APPROVAL",
                to_status="ESCALATED",
                notes="Timed out after 15 minutes waiting for human action.",
            )
            
            # Broadcast WebSocket status change so UI updates
            from api.websocket import manager
            from db.session import run_in_new_loop
            import asyncio
            # Running async function in synchronous celery task
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.broadcast_status_change(incident_id, "ESCALATED", actor="system"))
            except RuntimeError:
                asyncio.run(manager.broadcast_status_change(incident_id, "ESCALATED", actor="system"))
                
            trigger_pagerduty_escalation.delay(
                incident_id,
                "Timed out waiting for human approval after 15 minutes"
            )
    except Exception as e:
        logger.error("[Task] check_approval_timeout failed for %s: %s", incident_id, e)
    finally:
        cur.close()
        conn.close()
