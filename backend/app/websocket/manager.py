"""WebSocket connection manager.

One multiplexed connection per client carries every live channel — KPIs,
charts, telemetry, alerts and device status — rather than a socket per feature.
Messages are tagged with a ``type`` and the client routes them.

Broadcast is fire-and-forget with per-client isolation: a slow or dead client
is dropped rather than being allowed to stall the Digital Twin tick.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.utils.time import utc_now

logger = get_logger(__name__)


class MessageType(StrEnum):
    """Channels multiplexed over the single ``/ws/live`` connection."""

    HELLO = "hello"
    TICK = "tick"
    TELEMETRY = "telemetry"
    ALERT = "alert"
    INTELLIGENCE = "intelligence"
    ENGINE_STATUS = "engine_status"
    PONG = "pong"


def build_message(message_type: MessageType, payload: Any) -> dict[str, Any]:
    """Wrap a payload in the standard live-message envelope."""
    return {
        "type": message_type.value,
        "timestamp": utc_now().isoformat(),
        "payload": payload,
    }


@dataclass
class ConnectionStats:
    """Counters for diagnostics and the health endpoint."""

    connected: int = 0
    total_accepted: int = 0
    total_dropped: int = 0
    messages_sent: int = 0
    send_failures: int = 0
    by_type: dict[str, int] = field(default_factory=dict)


class ConnectionManager:
    """Tracks live clients and fans messages out to them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.stats = ConnectionStats()
        #: Most recent message of each type, replayed to new clients so a
        #: freshly opened dashboard is populated immediately rather than
        #: waiting for the next tick.
        self._last: dict[str, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a client and replay the latest state to it."""
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
            self.stats.connected = len(self._clients)
            self.stats.total_accepted += 1

        await self._send(websocket, build_message(MessageType.HELLO, {"connected": True}))
        for cached in list(self._last.values()):
            await self._send(websocket, cached)

        logger.info("WebSocket client connected", extra={"clients": self.stats.connected})

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a client. Safe to call more than once."""
        async with self._lock:
            if websocket in self._clients:
                self._clients.discard(websocket)
                self.stats.connected = len(self._clients)
                self.stats.total_dropped += 1
                logger.info(
                    "WebSocket client disconnected", extra={"clients": self.stats.connected}
                )

    async def _send(self, websocket: WebSocket, message: dict[str, Any]) -> bool:
        """Send to one client, reporting whether it succeeded."""
        if websocket.client_state is not WebSocketState.CONNECTED:
            return False
        try:
            await websocket.send_text(json.dumps(message, default=str))
            self.stats.messages_sent += 1
            return True
        except Exception:
            self.stats.send_failures += 1
            return False

    async def broadcast(self, message_type: MessageType, payload: Any) -> int:
        """Fan a message out to every connected client.

        Returns the number of clients that received it. Failed clients are
        removed so a dropped browser tab cannot accumulate as a leak.
        """
        message = build_message(message_type, payload)
        self._last[message_type.value] = message
        self.stats.by_type[message_type.value] = (
            self.stats.by_type.get(message_type.value, 0) + 1
        )

        async with self._lock:
            targets = list(self._clients)

        if not targets:
            return 0

        results = await asyncio.gather(
            *(self._send(client, message) for client in targets), return_exceptions=True
        )

        stale = [
            client
            for client, result in zip(targets, results, strict=True)
            if result is not True
        ]
        for client in stale:
            await self.disconnect(client)

        return len(targets) - len(stale)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def status(self) -> dict[str, Any]:
        """Manager diagnostics."""
        return {
            "connected": self.stats.connected,
            "total_accepted": self.stats.total_accepted,
            "total_dropped": self.stats.total_dropped,
            "messages_sent": self.stats.messages_sent,
            "send_failures": self.stats.send_failures,
            "by_type": dict(self.stats.by_type),
        }


#: Process-wide manager. The Telemetry Layer and Intelligence loop both publish
#: through this instance.
connection_manager = ConnectionManager()
