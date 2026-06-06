"""
PostgreSQL LISTEN/NOTIFY bridge for Celery → FastAPI WebSocket notifications.

WHY THIS EXISTS:
  Celery workers and the FastAPI process are separate OS processes.
  The FastAPI WebSocket manager lives in the API process memory.
  Celery cannot directly call manager.broadcast() — it has zero WebSocket connections.

HOW IT WORKS:
  1. Celery calls `notify_status_change(incident_id, new_status)`.
     This fires a PostgreSQL NOTIFY on channel 'incident_updates'.
  2. The FastAPI API process runs `listen_for_pg_notifications()` as a background task.
     It receives the NOTIFY payload and calls manager.broadcast() with live WS connections.

This is reliable, zero-dependency (uses the existing Postgres connection), and works
across any number of Celery worker processes.
"""

from __future__ import annotations

import asyncio
import json
import logging

import psycopg2
import psycopg2.extensions

from agents.config import DATABASE_TARGET

logger = logging.getLogger(__name__)

PG_CHANNEL = "incident_updates"


# ---------------------------------------------------------------------------
# Celery side: fire-and-forget NOTIFY (synchronous, safe in any process)
# ---------------------------------------------------------------------------


def notify_status_change(incident_id: str, new_status: str, actor: str = "agent") -> None:
    """
    Send a PostgreSQL NOTIFY from any process (Celery worker, API, etc.).
    The FastAPI listener will pick this up and push it to WebSocket clients.
    """
    payload = json.dumps({
        "incident_id": incident_id,
        "new_status": new_status,
        "actor": actor,
    })
    try:
        conn = psycopg2.connect(**DATABASE_TARGET)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"NOTIFY {PG_CHANNEL}, %s", (payload,))
        cur.close()
        conn.close()
        logger.debug("NOTIFY sent: incident_id=%s status=%s", incident_id, new_status)
    except Exception as e:
        logger.error("Failed to send NOTIFY for incident %s: %s", incident_id, e)


# ---------------------------------------------------------------------------
# FastAPI side: async listener that bridges PG NOTIFY → WebSocket broadcast
# ---------------------------------------------------------------------------


async def listen_for_pg_notifications(manager) -> None:
    """
    Long-running async task to be started in FastAPI lifespan.
    Listens on the PostgreSQL NOTIFY channel and forwards status changes
    to all subscribed WebSocket clients via the connection manager.

    Usage in api/main.py lifespan:
        asyncio.create_task(listen_for_pg_notifications(manager))
    """
    logger.info("Starting PostgreSQL NOTIFY listener on channel '%s'", PG_CHANNEL)

    # Use a dedicated synchronous connection in a thread executor
    # (psycopg2 is not async-native; we poll it in a thread)
    loop = asyncio.get_running_loop()

    def _blocking_listen():
        """Runs in a thread — polls for NOTIFY using conn.poll() (cross-platform, works on Windows)."""
        import time

        conn = psycopg2.connect(**DATABASE_TARGET)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"LISTEN {PG_CHANNEL}")
        logger.info("LISTEN registered on channel '%s'", PG_CHANNEL)

        while True:
            # poll() is cross-platform (works on Windows unlike select.select with psycopg2 FDs)
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                try:
                    data = json.loads(notify.payload)
                    # Schedule the async broadcast from the sync thread
                    asyncio.run_coroutine_threadsafe(
                        manager.broadcast(
                            data["incident_id"],
                            {
                                "type": "status_change",
                                "incident_id": data["incident_id"],
                                "new_status": data["new_status"],
                                "actor": data.get("actor", "system"),
                            },
                        ),
                        loop,
                    )
                    logger.info(
                        "Forwarded NOTIFY to WebSocket: incident_id=%s status=%s",
                        data.get("incident_id"), data.get("new_status"),
                    )
                except Exception as e:
                    logger.error("Failed to process NOTIFY payload: %s", e)
            # Sleep briefly to avoid busy-waiting (5s matches previous select timeout)
            time.sleep(1)

    await loop.run_in_executor(None, _blocking_listen)
