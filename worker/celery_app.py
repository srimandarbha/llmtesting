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
from celery.signals import worker_process_init

from agents.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "sre_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["worker.tasks"],
)


@worker_process_init.connect
def preload_embedding_model(**kwargs):
    """
    Pre-load the SentenceTransformer model at Celery worker process startup.
    This avoids a thread-safety race condition when multiple task threads try
    to initialize the global _embed_model in langchain_tools.py simultaneously.
    """
    from agents.langchain_tools import _get_embed_model
    import logging
    logging.getLogger(__name__).info("Pre-loading embedding model at worker startup...")
    _get_embed_model()
    logging.getLogger(__name__).info("Embedding model ready.")


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
)

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "generate-shift-summary-morning": {
        "task": "worker.tasks.generate_auto_shift_summary",
        "schedule": crontab(hour=0, minute=30),
    },
    "generate-shift-summary-afternoon": {
        "task": "worker.tasks.generate_auto_shift_summary",
        "schedule": crontab(hour=8, minute=30),
    },
    "generate-shift-summary-night": {
        "task": "worker.tasks.generate_auto_shift_summary",
        "schedule": crontab(hour=16, minute=30),
    },
}
