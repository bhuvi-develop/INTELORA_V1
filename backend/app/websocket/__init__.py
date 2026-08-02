"""Real-time transport — one multiplexed connection for the whole dashboard."""

from app.websocket.manager import (
    ConnectionManager,
    MessageType,
    build_message,
    connection_manager,
)
from app.websocket.router import router as websocket_router

__all__ = [
    "ConnectionManager",
    "MessageType",
    "build_message",
    "connection_manager",
    "websocket_router",
]
