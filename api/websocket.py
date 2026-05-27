"""
WebSocket connection manager for real-time incident status updates.

Supports:
- Per-incident subscription channels
- Broadcast on every state change
- Live presence tracking (who is viewing an incident)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections subscribed to specific incident IDs.
    Thread-safe for use with FastAPI's async event loop.
    """

    def __init__(self):
        # incident_id (str) → list of connected WebSockets
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        # incident_id → set of user display names currently viewing
        self._presence: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, incident_id: str, websocket: WebSocket, user_name: str = "anonymous"):
        await websocket.accept()
        async with self._lock:
            self._connections[incident_id].append(websocket)
            self._presence[incident_id].add(user_name)
        logger.info("[WS] %s connected to incident %s", user_name, incident_id)
        # Notify others of new viewer
        await self.broadcast(
            incident_id,
            {"type": "presence", "viewers": list(self._presence[incident_id])},
            exclude=websocket,
        )

    async def disconnect(self, incident_id: str, websocket: WebSocket, user_name: str = "anonymous"):
        async with self._lock:
            try:
                self._connections[incident_id].remove(websocket)
            except ValueError:
                pass
            self._presence[incident_id].discard(user_name)
            if not self._connections[incident_id]:
                del self._connections[incident_id]
                self._presence.pop(incident_id, None)
        logger.info("[WS] %s disconnected from incident %s", user_name, incident_id)

    async def broadcast(
        self,
        incident_id: str,
        message: dict[str, Any],
        exclude: WebSocket | None = None,
    ):
        """Send message to all subscribers of an incident (except excluded socket)."""
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []

        async with self._lock:
            sockets = list(self._connections.get(incident_id, []))

        for ws in sockets:
            if ws is exclude:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self._connections[incident_id].remove(ws)
                    except ValueError:
                        pass

    async def broadcast_status_change(
        self,
        incident_id: str,
        new_status: str,
        actor: str = "agent",
        notes: str = "",
        metadata: dict | None = None,
    ):
        """Convenience method for status transition broadcasts."""
        await self.broadcast(
            incident_id,
            {
                "type": "status_change",
                "incident_id": incident_id,
                "new_status": new_status,
                "actor": actor,
                "notes": notes,
                "metadata": metadata or {},
            },
        )

    def get_viewers(self, incident_id: str) -> list[str]:
        return list(self._presence.get(incident_id, set()))

    def get_connection_count(self, incident_id: str) -> int:
        return len(self._connections.get(incident_id, []))


# Singleton instance used across the app
manager = ConnectionManager()
