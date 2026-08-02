"""The live WebSocket endpoint.

A single route at ``/ws/live``. The connection is read-only from the client's
perspective apart from a keepalive ping: INTELORA observes and reports, and
commands are never accepted over the live channel.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.websocket.manager import MessageType, build_message, connection_manager

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/live")
async def live_stream(websocket: WebSocket) -> None:
    """Stream live platform state to one client.

    On connect the client receives the most recent message of every type, so a
    dashboard opened mid-stream renders immediately instead of waiting for the
    next tick.
    """
    await connection_manager.connect(websocket)
    try:
        while True:
            # The receive call is what detects a closed socket. Anything the
            # client sends other than "ping" is ignored by design.
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_json(build_message(MessageType.PONG, {"ok": True}))
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket stream error")
        await connection_manager.disconnect(websocket)
