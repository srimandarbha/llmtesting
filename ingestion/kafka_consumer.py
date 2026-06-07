"""
Kafka consumer for SRE alert ingestion.

Production-hardened with:
- Pydantic validation of incoming payloads (rejects unknown schemas)
- Poison pill handling: failed messages are committed and written to DLQ topic
- Fixed SQL INTERVAL parameterization (no string interpolation)
- Structured logging bound with correlation_id
"""

from __future__ import annotations

import json
import logging
import os
import uuid

import psycopg2
from kafka import KafkaConsumer, KafkaProducer
from pydantic import BaseModel, ValidationError

from agents.config import DATABASE_TARGET, DEDUP_WINDOW_MINUTES
from worker.tasks import run_agent_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
)
logger = logging.getLogger("kafka_consumer")

# ---------------------------------------------------------------------------
# Strict payload schema — must match AlertManager webhook format
# ---------------------------------------------------------------------------


class AlertPayload(BaseModel):
    """Validated schema for incoming Kafka alert messages."""
    alert_name: str
    cluster: str
    namespace: str
    hostname: str = ""
    correlation_id: str = ""
    awx_template_id: str = "1"

    def model_post_init(self, __context) -> None:
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Core alert processing
# ---------------------------------------------------------------------------


def process_alert(payload: AlertPayload) -> None:
    """Create incident and enqueue Celery pipeline. Raises on DB failure."""
    log = logger.getChild(payload.correlation_id)

    try:
        conn = psycopg2.connect(**DATABASE_TARGET)
        cur = conn.cursor()
    except Exception as e:
        log.error("Database connection failed: %s", e)
        raise  # Re-raise so the caller can write to DLQ

    try:
        # Deduplication — correctly parameterized INTERVAL
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
            log.info("Duplicate deduplicated. Existing incident: %s", existing[0])
            return

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
        cur.execute(
            """
            INSERT INTO incident_timeline
              (incident_id, actor_type, action, from_status, to_status, notes)
            VALUES (%s, 'system', 'Alert received from Kafka', NULL, 'RECEIVED', %s)
            """,
            (incident_id, f"correlation_id={payload.correlation_id}"),
        )
        conn.commit()

        log.info("Incident %s created. Enqueueing pipeline.", incident_id)
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

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Dead Letter Queue writer
# ---------------------------------------------------------------------------


def _write_to_dlq(producer: KafkaProducer, dlq_topic: str, raw_bytes: bytes, reason: str) -> None:
    """Write a failed message to the DLQ topic with failure metadata."""
    try:
        dlq_payload = json.dumps({
            "reason": reason,
            "original_message": raw_bytes.decode("utf-8", errors="replace"),
        }).encode("utf-8")
        producer.send(dlq_topic, dlq_payload)
        producer.flush()
        logger.error("Message written to DLQ '%s'. Reason: %s", dlq_topic, reason)
    except Exception as e:
        logger.critical("FAILED to write to DLQ '%s': %s", dlq_topic, e)


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------


def run_consumer() -> None:
    kafka_broker = os.environ.get("KAFKA_BROKER_URL", "localhost:9092")
    kafka_topic = os.environ.get("KAFKA_TOPIC", "sre_alerts")
    dlq_topic = os.environ.get("KAFKA_DLQ_TOPIC", "sre_alerts_dlq")
    group_id = os.environ.get("KAFKA_GROUP_ID", "sre-agent-group")

    logger.info("Starting consumer. broker=%s topic=%s dlq=%s", kafka_broker, kafka_topic, dlq_topic)

    consumer = KafkaConsumer(
        kafka_topic,
        bootstrap_servers=kafka_broker,
        group_id=group_id,
        auto_offset_reset="latest",
        enable_auto_commit=False,   # Manual commit after processing
        value_deserializer=None,    # Raw bytes — we handle deserialization ourselves
    )

    producer = KafkaProducer(bootstrap_servers=kafka_broker)

    for message in consumer:
        raw_bytes = message.value
        try:
            # Step 1: Deserialize
            try:
                raw_dict = json.loads(raw_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                _write_to_dlq(producer, dlq_topic, raw_bytes, f"JSON decode failed: {e}")
                consumer.commit()
                continue

            # Step 2: Validate schema
            try:
                payload = AlertPayload.model_validate(raw_dict)
            except ValidationError as e:
                _write_to_dlq(producer, dlq_topic, raw_bytes, f"Schema validation failed: {e}")
                consumer.commit()
                continue

            # Step 3: Process — wrap in try/except to prevent crash loops
            try:
                process_alert(payload)
            except Exception as e:
                logger.error(
                    "process_alert failed for correlation_id=%s: %s",
                    raw_dict.get("correlation_id", "unknown"), e,
                )
                _write_to_dlq(producer, dlq_topic, raw_bytes, f"process_alert failed: {e}")

        finally:
            # Always commit offset — even on failure — to avoid poison pill crash loops
            consumer.commit()


if __name__ == "__main__":
    run_consumer()
