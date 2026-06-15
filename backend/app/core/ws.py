"""WebSocket connection manager — per-user connection pool."""
from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger("ws")


class ConnectionManager:
    """Manages per-user WS connections keyed by device_id.

    A single user may have multiple devices connected simultaneously.
    """

    def __init__(self) -> None:
        # {user_id: {device_id: WebSocket}}
        self._connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, user_id: str, device_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(user_id, {})[device_id] = ws
        logger.info("ws.connect", user_id=user_id, device_id=device_id)

    async def disconnect(self, user_id: str, device_id: str) -> None:
        user_conns = self._connections.get(user_id, {})
        user_conns.pop(device_id, None)
        if not user_conns:
            self._connections.pop(user_id, None)
        logger.info("ws.disconnect", user_id=user_id, device_id=device_id)

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        user_conns = self._connections.get(user_id, {})
        payload = json.dumps(message, ensure_ascii=False)
        for device_id, ws in list(user_conns.items()):
            try:
                await ws.send_text(payload)
            except Exception:
                logger.warning("ws.send_failed", user_id=user_id, device_id=device_id)
                await self.disconnect(user_id, device_id)

    async def broadcast_to_resource(
        self, resource_id: str, message: dict[str, Any]
    ) -> None:
        """Push a message to ALL connected users (for resource-level broadcasts).

        Frontends filter by resource_id in JS to decide whether to react.
        """
        payload = json.dumps(message, ensure_ascii=False)
        for user_id, devices in list(self._connections.items()):
            for device_id, ws in list(devices.items()):
                try:
                    await ws.send_text(payload)
                except Exception:
                    logger.warning(
                        "ws.broadcast_failed", user_id=user_id, device_id=device_id
                    )
                    await self.disconnect(user_id, device_id)

    def get_online_users(self) -> list[str]:
        return list(self._connections.keys())

    def is_online(self, user_id: str) -> bool:
        return user_id in self._connections


# Singleton
connection_manager = ConnectionManager()
