"""
Celery tasks for the SRE Incident Agent.

Tasks:
  run_agent_pipeline       -> LangChain agent pipeline for one incident
  poll_awx_job             -> Poll AWX every 15s until terminal, then verify
  verify_remediation       -> Real Kubernetes health check post-AWX success
  trigger_pagerduty_escalation -> Page oncall via PagerDuty API
  check_approval_timeout   -> Auto-escalate stale PENDING_APPROVAL incidents

P1 improvements applied:
  - Connection pool (SimpleConnectionPool) — no per-call TCP connections
  - structlog with incident_id/correlation_id bound to every log line
  - Real post-execution health verification (verify_remediation task)
  - notify_status_change() for Celery -> FastAPI WebSocket bridge
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import structlog
from psycopg2 import pool as pg_pool

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
from db.pg_notify import notify_status_change
from worker.celery_app import celery_app

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Connection pool — shared per worker process, eliminates per-call connects
# ---------------------------------------------------------------------------

_pool: pg_pool.SimpleConnectionPool | None = None


def _get_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.SimpleConnectionPool(minconn=2, maxconn=10, **DATABASE_TARGET)
    return _pool


@contextmanager
def _db_conn():
    """Borrow a connection from the pool, auto-commit or rollback on exit."""
    conn = _get_pool().getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


# ---------------------------------------------------------------------------
# AWX client selection (real vs mock)
# ---------------------------------------------------------------------------


def _get_awx_client():
    if USE_MOCK_AWX:
        from simulation.mock_client import MockAWXClient
        return MockAWXClient(fail_rate=0.0, pending_delay=1.0, run_delay=3.0)
    from awx.client import AWXClient
    return AWXClient()


# ---------------------------------------------------------------------------
# DB helpers — all use the shared pool, never open raw connections
# ---------------------------------------------------------------------------


def _update_incident_status(incident_id: str, new_status: str, **kwargs):
    with _db_conn() as conn:
        cur = conn.cursor()
        set_clauses = ["status = %s", "updated_at = NOW()"]
        values = [new_status]
        for col in ("risk_tier", "llm_confidence", "llm_intent_json", "analysis_summary",
                    "escalate_to", "awx_job_id", "resolved_at"):
            if col in kwargs:
                set_clauses.append(f"{col} = %s")
                val = kwargs[col]
                if col == "llm_intent_json" and isinstance(val, dict):
                    val = json.dumps(val)
                values.append(val)
        values.append(incident_id)
        cur.execute(f"UPDATE incidents_v2 SET {', '.join(set_clauses)} WHERE id = %s", values)
        cur.close()


def _insert_timeline(incident_id: str, actor_type: str, action: str,
                     from_status: str | None = None, to_status: str | None = None,
                     notes: str | None = None, metadata: dict | None = None):
    """Append an immutable timeline event — always INSERT, never UPDATE."""
    with _db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO incident_timeline
              (incident_id, actor_type, action, from_status, to_status, notes, metadata_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (incident_id, actor_type, action, from_status, to_status, notes,
             json.dumps(metadata) if metadata else None),
        )
        cur.close()


def _insert_llm_decision(incident_id: str, prompt_used: str, raw_output: str,
                         parsed_intent: dict, confidence: float, tool_calls: list):
    with _db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO llm_decisions
              (incident_id, prompt_used, raw_llm_output, parsed_intent, confidence, tool_calls_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (incident_id, prompt_used, raw_output,
             json.dumps(parsed_intent), confidence, json.dumps(tool_calls)),
        )
        cur.close()


def _check_blast_radius(cluster: str) -> bool:
    """Returns True if it's safe to auto-execute (under the cap)."""
    with _db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM incidents_v2
            WHERE cluster = %s AND status = 'EXECUTING'
              AND updated_at > NOW() - INTERVAL '1 hour';
            """,
            (cluster,),
        )
        count = cur.fetchone()[0]
        cur.close()
        return count < BLAST_RADIUS_CAP


# ---------------------------------------------------------------------------
# Task 1: Run the full LangChain agent pipeline
# ---------------------------------------------------------------------------


@celery_app.task(
    name="worker.tasks.run_agent_pipeline",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_agent_pipeline(self, incident_id: str, alert_name: str, namespace: str,
                       cluster: str, hostname: str, correlation_id: str,
                       awx_template_id: str = "1"):
    """
    Main Celery task: runs the LangChain 5-step agent pipeline for one incident.
    - LOW risk  -> launches AWX job (checks blast radius first)
    - HIGH risk -> writes PENDING_APPROVAL to DB (awaits human via API)
    - ESCALATE  -> marks ESCALATED, fires PagerDuty
    """
    log = logger.bind(incident_id=incident_id, correlation_id=correlation_id,
                      alert_name=alert_name, cluster=cluster)
    log.info("Starting agent pipeline")

    def _on_status(inc_id, new_status, notes=""):
        _update_incident_status(str(inc_id), new_status)
        _insert_timeline(str(inc_id), actor_type="agent", action=f"Status -> {new_status}",
                         to_status=new_status, notes=notes)
        notify_status_change(str(inc_id), new_status, actor="agent")

    try:
        _insert_timeline(incident_id, actor_type="agent", action="Agent pipeline started",
                         from_status="RECEIVED", to_status="ANALYZING")
        _update_incident_status(incident_id, "ANALYZING")

        result = run_incident_pipeline(
            incident_id=uuid.UUID(incident_id),
            alert_name=alert_name,
            namespace=namespace,
            cluster=cluster,
            hostname=hostname,
            correlation_id=correlation_id,
            on_status_update=_on_status,
        )

        _insert_llm_decision(
            incident_id=incident_id,
            prompt_used="ReAct agent (see tool_calls for full context)",
            raw_output=result.raw_agent_output,
            parsed_intent=result.intent.model_dump(),
            confidence=result.intent.confidence,
            tool_calls=result.tool_calls,
        )

        intent_dict = result.intent.model_dump()

        if result.action == "auto_execute":
            if not _check_blast_radius(cluster):
                log.warning("Blast radius cap reached. Escalating.")
                _update_incident_status(incident_id, "ESCALATED",
                                        risk_tier=result.risk_tier,
                                        llm_confidence=result.intent.confidence,
                                        llm_intent_json=intent_dict,
                                        analysis_summary=result.intent.analysis_summary,
                                        escalate_to=result.intent.escalate_to)
                _insert_timeline(incident_id, actor_type="system",
                                 action="Blast radius cap reached. Auto-escalated.",
                                 from_status="ANALYZING", to_status="ESCALATED",
                                 notes=f"Cluster {cluster} has {BLAST_RADIUS_CAP} executing jobs.")
                notify_status_change(incident_id, "ESCALATED", actor="system")
                trigger_pagerduty_escalation.delay(incident_id, f"Blast radius cap on {cluster}")
                return

            _update_incident_status(incident_id, "EXECUTING", risk_tier="LOW",
                                    llm_confidence=result.intent.confidence,
                                    llm_intent_json=intent_dict,
                                    analysis_summary=result.intent.analysis_summary,
                                    escalate_to=result.intent.escalate_to)
            _insert_timeline(incident_id, actor_type="agent", action="Launching AWX job (AUTO)",
                             from_status="ANALYZING", to_status="EXECUTING",
                             notes=result.risk_reasoning, metadata={"intent": intent_dict})

            awx = _get_awx_client()
            job_id = awx.launch_job(template_id=awx_template_id,
                                    extra_vars=result.intent.to_awx_extra_vars())
            _update_incident_status(incident_id, "EXECUTING", awx_job_id=job_id)
            _insert_timeline(incident_id, actor_type="agent",
                             action=f"AWX job #{job_id} launched", to_status="EXECUTING",
                             metadata={"awx_job_id": job_id,
                                       "awx_url": f"{AWX_BASE_URL}/#/jobs/{job_id}"})
            notify_status_change(incident_id, "EXECUTING", actor="agent")
            poll_awx_job.apply_async(args=[incident_id, job_id], countdown=10, queue="priority")

        elif result.action == "pending_approval":
            _update_incident_status(incident_id, "PENDING_APPROVAL", risk_tier="HIGH",
                                    llm_confidence=result.intent.confidence,
                                    llm_intent_json=intent_dict,
                                    analysis_summary=result.intent.analysis_summary,
                                    escalate_to=result.intent.escalate_to)
            _insert_timeline(incident_id, actor_type="agent",
                             action="Awaiting human approval (HIGH risk)",
                             from_status="ANALYZING", to_status="PENDING_APPROVAL",
                             notes=result.risk_reasoning,
                             metadata={"proposed_intent": intent_dict})
            notify_status_change(incident_id, "PENDING_APPROVAL", actor="agent")
            log.info("Incident now PENDING_APPROVAL")
            check_approval_timeout.apply_async(args=[incident_id], countdown=15 * 60)

        else:  # escalate
            _update_incident_status(incident_id, "ESCALATED", risk_tier="ESCALATE",
                                    llm_confidence=result.intent.confidence,
                                    llm_intent_json=intent_dict,
                                    analysis_summary=result.intent.analysis_summary,
                                    escalate_to=result.intent.escalate_to)
            _insert_timeline(incident_id, actor_type="agent",
                             action="ESCALATED — paging oncall",
                             from_status="ANALYZING", to_status="ESCALATED",
                             notes=result.risk_reasoning, metadata={"intent": intent_dict})
            notify_status_change(incident_id, "ESCALATED", actor="agent")
            trigger_pagerduty_escalation.delay(
                incident_id,
                f"Low confidence ({result.intent.confidence:.0%}) or unknown action on "
                f"{alert_name} in {cluster}",
            )

    except Exception as exc:
        log.exception("Agent pipeline FAILED", error=str(exc))
        _update_incident_status(incident_id, "FAILED")
        _insert_timeline(incident_id, actor_type="system", action="Agent pipeline failed",
                         to_status="FAILED", notes=str(exc))
        self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 2: Poll AWX job status
# ---------------------------------------------------------------------------

AWX_POLL_INTERVAL = 15  # seconds


@celery_app.task(
    name="worker.tasks.poll_awx_job",
    bind=True,
    max_retries=60,
    default_retry_delay=AWX_POLL_INTERVAL,
)
def poll_awx_job(self, incident_id: str, job_id: str):
    """Poll AWX until terminal state, then dispatch verification task."""
    log = logger.bind(incident_id=incident_id, job_id=job_id)
    log.info("Polling AWX job status")

    awx = _get_awx_client()
    result = awx.get_job_status(job_id)

    if not result.status.is_terminal:
        log.debug("AWX job still running, retrying", status=str(result.status))
        self.retry(countdown=AWX_POLL_INTERVAL)
        return

    if result.status.is_success:
        log.info("AWX job SUCCEEDED")
        _update_incident_status(incident_id, "VERIFYING")
        _insert_timeline(incident_id, actor_type="agent",
                         action=f"AWX job #{job_id} SUCCEEDED — starting health verification",
                         from_status="EXECUTING", to_status="VERIFYING",
                         metadata={"awx_status": result.status.value, "elapsed": result.elapsed})
        notify_status_change(incident_id, "VERIFYING", actor="agent")
        # 60s cooldown for remediation to converge, then real health check
        verify_remediation.apply_async(args=[incident_id], countdown=60, queue="priority")
    else:
        log.error("AWX job reached terminal failure", status=result.status.value)
        _update_incident_status(incident_id, "FAILED")
        _insert_timeline(incident_id, actor_type="agent",
                         action=f"AWX job #{job_id} FAILED ({result.status.value})",
                         from_status="EXECUTING", to_status="FAILED",
                         notes="Auto-escalating to oncall due to AWX failure.",
                         metadata={"awx_status": result.status.value})
        notify_status_change(incident_id, "FAILED", actor="agent")
        trigger_pagerduty_escalation.delay(
            incident_id, f"AWX job #{job_id} failed: {result.status.value}"
        )


# ---------------------------------------------------------------------------
# Task 3: Post-execution health verification (REAL check, not hardcoded)
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.verify_remediation", bind=True, max_retries=3,
                 default_retry_delay=30)
def verify_remediation(self, incident_id: str):
    """
    Real post-execution health check before marking RESOLVED.
    Reads the incident's stored intent to know which pod/namespace to verify.
    Escalates with PagerDuty if the pod is still unhealthy after the convergence window.
    """
    log = logger.bind(incident_id=incident_id)
    log.info("Running post-execution verification")

    try:
        with _db_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT namespace, llm_intent_json FROM incidents_v2 WHERE id = %s",
                (incident_id,),
            )
            row = cur.fetchone()
            cur.close()

        if not row:
            log.error("Incident not found for verification")
            return

        namespace, intent_json = row
        intent = json.loads(intent_json) if intent_json else {}
        pod_name = intent.get("target", "")

        from agents.langchain_tools import get_pod_status
        check_result = json.loads(
            get_pod_status.invoke(json.dumps({"namespace": namespace, "pod_name": pod_name}))
        )

        phase = check_result.get("phase", "Unknown")
        has_error = bool(check_result.get("error"))

        if has_error or phase not in ("Running", "Succeeded"):
            log.warning("Verification FAILED — pod not healthy", phase=phase, pod=pod_name)
            _insert_timeline(incident_id, actor_type="agent",
                             action="Verification FAILED — pod unhealthy after remediation",
                             from_status="VERIFYING", to_status="ESCALATED",
                             notes=f"Pod '{pod_name}' phase={phase}. Escalating for human review.",
                             metadata={"check_result": check_result})
            _update_incident_status(incident_id, "ESCALATED")
            notify_status_change(incident_id, "ESCALATED", actor="agent")
            trigger_pagerduty_escalation.delay(
                incident_id,
                f"Verification failed: pod '{pod_name}' is {phase} after remediation",
            )
        else:
            log.info("Verification PASSED — pod healthy", phase=phase, pod=pod_name)
            _insert_timeline(incident_id, actor_type="agent",
                             action="Verification PASSED — marking RESOLVED",
                             from_status="VERIFYING", to_status="RESOLVED",
                             notes=f"Pod '{pod_name}' phase={phase}. Health check passed.",
                             metadata={"check_result": check_result})
            _update_incident_status(
                incident_id, "RESOLVED",
                resolved_at=datetime.now(timezone.utc).isoformat(),
            )
            notify_status_change(incident_id, "RESOLVED", actor="agent")

    except Exception as exc:
        log.error("verify_remediation failed", error=str(exc))
        self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 4: PagerDuty escalation
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.trigger_pagerduty_escalation")
def trigger_pagerduty_escalation(incident_id: str, reason: str):
    """Create a PagerDuty incident for oncall escalation."""
    log = logger.bind(incident_id=incident_id)
    if not PAGERDUTY_API_KEY:
        log.warning("PagerDuty API key not configured. Skipping escalation.")
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
        log.info("PagerDuty incident created")
    except Exception as e:
        log.error("PagerDuty escalation failed", error=str(e))


# ---------------------------------------------------------------------------
# Task 5: Approval timeout check
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.check_approval_timeout")
def check_approval_timeout(incident_id: str):
    """Check if an incident is still in PENDING_APPROVAL and escalate if so."""
    log = logger.bind(incident_id=incident_id)
    try:
        with _db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM incidents_v2 WHERE id = %s", (incident_id,))
            row = cur.fetchone()
            cur.close()

        if not row:
            return

        if row[0] == "PENDING_APPROVAL":
            log.warning("Incident timed out waiting for human approval. Escalating.")
            _update_incident_status(incident_id, "ESCALATED")
            _insert_timeline(incident_id, actor_type="system",
                             action="Approval timeout reached — auto-escalated",
                             from_status="PENDING_APPROVAL", to_status="ESCALATED",
                             notes="Timed out after 15 minutes waiting for human action.")
            notify_status_change(incident_id, "ESCALATED", actor="system")
            trigger_pagerduty_escalation.delay(
                incident_id, "Timed out waiting for human approval after 15 minutes"
            )
    except Exception as e:
        log.error("check_approval_timeout failed", error=str(e))
