"""
FastAPI application entry point.

Features:
- CORS for local React dev server
- Lifespan events for DB connection setup/teardown
- All routers mounted
- WebSocket endpoint for real-time incident updates
- Health check endpoint
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.routers.alerts import router as alerts_router
from api.routers.analytics import router as analytics_router
from api.routers.incidents import router as incidents_router
from api.routers.cve_advisor import router as cve_advisor_router
from api.websocket import manager
from db.pg_notify import listen_for_pg_notifications
from db.session import close_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SRE Incident Agent API starting up...")
    # Start the PostgreSQL NOTIFY listener — bridges Celery → WebSocket
    import asyncio
    pg_listener_task = asyncio.create_task(listen_for_pg_notifications(manager))
    yield
    logger.info("SRE Incident Agent API shutting down...")
    pg_listener_task.cancel()
    await close_engine()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SRE Incident Agent API",
    description=(
        "LangChain-powered incident remediation system with Human-in-the-Loop approval. "
        "All automated Ansible actions execute via AWX REST API."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS (allow React dev server)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://localhost:3000",   # CRA default
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(alerts_router)
app.include_router(incidents_router)
app.include_router(analytics_router)
app.include_router(cve_advisor_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["System"])
async def health_check():
    """Returns API liveness status."""
    return {"status": "ok", "service": "sre-incident-agent"}


# ---------------------------------------------------------------------------
# Live incident counts (used by Dashboard cards)
# ---------------------------------------------------------------------------


@app.get("/dashboard/counts", tags=["Dashboard"])
async def dashboard_counts():
    """Return live counts for the four Dashboard stat cards."""
    from agents.config import DATABASE_TARGET
    conn = psycopg2.connect(**DATABASE_TARGET)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE status IN ('ANALYZING','EXECUTING','VERIFYING','PENDING_APPROVAL')) AS active,
          COUNT(*) FILTER (WHERE status = 'PENDING_APPROVAL') AS pending_approval,
          COUNT(*) FILTER (WHERE status = 'RESOLVED' AND resolved_at::date = CURRENT_DATE) AS resolved_today,
          COUNT(*) FILTER (WHERE status = 'FAILED') AS failed
        FROM incidents_v2;
        """
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "active": row[0],
        "pending_approval": row[1],
        "resolved_today": row[2],
        "failed": row[3],
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/incidents/{incident_id}")
async def websocket_incident(
    websocket: WebSocket,
    incident_id: str,
    user_name: str = Query(default="anonymous"),
):
    """
    Subscribe to real-time updates for a specific incident.

    Messages sent to client:
    - {"type": "status_change", "incident_id": ..., "new_status": ..., ...}
    - {"type": "presence", "viewers": [...]}

    Connect with: ws://localhost:8000/ws/incidents/{id}?user_name=john.doe
    """
    await manager.connect(incident_id, websocket, user_name)
    try:
        while True:
            # Keep connection alive; handle client pings
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(incident_id, websocket, user_name)
        await manager.broadcast(
            incident_id,
            {"type": "presence", "viewers": manager.get_viewers(incident_id)},
        )
