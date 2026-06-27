"""
WebSocket live layer.

A small connection manager that tracks open browser connections and broadcasts
live-quote payloads pushed by the scheduler's poll job. This is the "watch it on
a second screen during market hours" feature.
"""

from __future__ import annotations

import asyncio
from typing import List, Set

from fastapi import WebSocket

from app.state import state
from app.utils import logger


class ConnectionManager:
    """Tracks connected WebSocket clients and broadcasts messages to them."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new connection and send it the current quote snapshot."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info(f"WebSocket connected ({len(self._connections)} clients)")
        # Send whatever we already have so the client isn't blank until next poll.
        quotes = state.get_quotes()
        if quotes:
            await self._safe_send(websocket, {
                "type": "quotes",
                "quotes": quotes,
                "ts": state.last_quote_update,
            })

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a connection from the pool."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info(f"WebSocket disconnected ({len(self._connections)} clients)")

    async def broadcast(self, payload: dict) -> None:
        """
        Send a payload to all connected clients, dropping dead ones.

        Args:
            payload: A JSON-serializable dict.
        """
        async with self._lock:
            targets: List[WebSocket] = list(self._connections)

        dead: List[WebSocket] = []
        for ws in targets:
            ok = await self._safe_send(ws, payload)
            if not ok:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    @staticmethod
    async def _safe_send(websocket: WebSocket, payload: dict) -> bool:
        """Send a payload, returning False if the socket is broken."""
        try:
            await websocket.send_json(payload)
            return True
        except Exception:  # noqa: BLE001 — broken socket, just drop it
            return False


# Single shared manager used by both the route and the scheduler broadcaster.
manager = ConnectionManager()
