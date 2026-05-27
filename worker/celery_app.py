"""
Celery application configuration.

Broker: PostgreSQL (via SQLAlchemy transport)
Result backend: PostgreSQL (via SQLAlchemy)

Workers:
  - default queue: standard agent tasks
  - priority queue: AWX polling tasks (lower latency)
"""

# pyrefly: ignore [missing-import]
from celery import Celery

from agents.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "sre_incident_agent",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["worker.tasks"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Queues
    task_routes={
        "worker.tasks.run_agent_pipeline": {"queue": "default"},
        "worker.tasks.poll_awx_job": {"queue": "priority"},
        "worker.tasks.trigger_pagerduty_escalation": {"queue": "default"},
    },
    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    # Retries
    task_max_retries=3,
    # Result expiry (24h)
    result_expires=86400,
    # Worker
    worker_prefetch_multiplier=1,  # one task at a time per worker (safer for agent workloads)
    worker_max_tasks_per_child=100,
    # SQLAlchemy transport: short polling interval for responsive local dev
    broker_transport_options={
        "polling_interval": 1,  # seconds between broker polls
    },
)
