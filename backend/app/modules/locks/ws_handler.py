"""M12 — Lock WebSocket handler (T020).

Endpoint: /api/v1/ws/locks?token=<access_token>

Accepts client messages:
- lock.heartbeat: renew lock TTL

Sends server events:
- lock.acquired: resource locked by a user
- lock.released: lock released (manual/ttl/heartbeat_lost)
- lock.lost: lock forcibly removed from current holder
"""
from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from app.api.deps import get_current_user_ws
from app.core.ws import connection_manager
from app.modules.locks.service import LockService

logger = structlog.get_logger("locks.ws")

router = APIRouter()


@router.websocket("/ws/locks")
async def ws_locks(
    websocket: WebSocket,
    token: str = Query(default=""),
):
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        user_id = await get_current_user_ws(websocket, token=token)
    except WebSocketDisconnect:
        return

    device_id = websocket.query_params.get("device_id", "ws-unknown")
    svc = LockService()

    await connection_manager.connect(user_id, device_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "code": "ws.invalid_json",
                            "message": "Invalid JSON",
                        }
                    )
                )
                continue

            msg_type = msg.get("type", "")

            if msg_type == "lock.heartbeat":
                lock_id = msg.get("lock_id", "")
                resource_type = msg.get("resource_type", "")
                resource_id = msg.get("resource_id", "")
                try:
                    await svc.heartbeat(lock_id=lock_id, user_id=user_id)
                except Exception as exc:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "code": getattr(exc, "code", "lock.invalid_heartbeat"),
                                "message": str(exc.message_override)
                                if hasattr(exc, "message_override")
                                else str(exc),
                            }
                        )
                    )
            else:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "code": "ws.unknown_message_type",
                            "message": f"Unknown message type: {msg_type}",
                        }
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(user_id, device_id)
        # Schedule stale check after 30s grace period
        asyncio.create_task(_schedule_stale_check(user_id, device_id))


async def _schedule_stale_check(user_id: str, device_id: str) -> None:
    """After 30s grace period, check for stale locks from this device."""
    await asyncio.sleep(30)
    svc = LockService()
    try:
        await svc.auto_release_stale()
    except Exception:
        logger.warning(
            "lock.stale_check_failed",
            user_id=user_id,
            device_id=device_id,
        )
