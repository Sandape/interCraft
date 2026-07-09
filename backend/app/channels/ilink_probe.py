"""iLink 4-step raw probe endpoints — REQ-052 manual verification.

These endpoints are intentionally minimal: they only translate the user's HTTP
call into an iLink Bot API call and return iLink's raw JSON response, so we
can debug session lifecycle issues without ORM/RLS/pool in the way.

Endpoints (all under /api/v1/agent/probe):
  1. POST /qrcode         → GET /ilink/bot/get_bot_qrcode?bot_type=3
  2. GET  /qrcode/status  → GET /ilink/bot/get_qrcode_status?qrcode=...
  3. POST /poll/start     → Start background long-poll task for a bot_token
  4. POST /poll/stop      → Cancel the long-poll task
  5. POST /send           → POST /ilink/bot/sendmessage

GET /poll/last  → Return messages received since last call (poll-store).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.channels.ilink_utils import make_headers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/probe", tags=["agent-probe"])

_BASE_URL = "https://ilinkai.weixin.qq.com"
_GETUPDATES_TIMEOUT = 45.0
_DEFAULT_TIMEOUT = 15.0
_CHANNEL_VERSION = "2.0.1"


# ── in-memory poll store (per process) ────────────────────────────
# token -> {"cursor": str, "msgs": [list], "task": asyncio.Task or None, "last_ret": Any}
_poll_store: Dict[str, Dict[str, Any]] = {}
# global inbox of every inbound message we received
_inbox: list[dict] = []


def _strip_token(token: str) -> str:
    """Stable short id for in-memory map keys (full token too long)."""
    return token[:32] if token else ""


# ── 1) get_bot_qrcode ──────────────────────────────────────────────
@router.post("/qrcode")
async def probe_qrcode() -> dict:
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as c:
        resp = await c.get(
            f"{_BASE_URL}/ilink/bot/get_bot_qrcode",
            params={"bot_type": 3},
            headers=make_headers(""),
        )
    return {
        "http_status": resp.status_code,
        "ilink_response": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
    }


# ── 2) get_qrcode_status ──────────────────────────────────────────
class QRStatusBody(BaseModel):
    qrcode: str


@router.post("/qrcode/status")
async def probe_qrcode_status(body: QRStatusBody) -> dict:
    headers = {
        **make_headers(""),
        "iLink-App-ClientVersion": "1",
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as c:
        resp = await c.get(
            f"{_BASE_URL}/ilink/bot/get_qrcode_status",
            params={"qrcode": body.qrcode},
            headers=headers,
        )
    raw = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
    return {
        "http_status": resp.status_code,
        "ilink_response": raw,
    }


# ── 3) start long-poll ────────────────────────────────────────────
class PollStartBody(BaseModel):
    bot_token: str
    base_url: str = _BASE_URL
    cursor: str = ""


@router.post("/poll/start")
async def probe_poll_start(body: PollStartBody) -> dict:
    key = _strip_token(body.bot_token)
    if not key:
        raise HTTPException(status_code=400, detail="bot_token required")

    # Stop existing task if any
    await _stop_poll(key)

    state: Dict[str, Any] = {
        "cursor": body.cursor,
        "msgs": [],
        "task": None,
        "last_resp": None,
        "started_at": time.time(),
        "stopped_at": None,
        "poll_count": 0,
    }
    _poll_store[key] = state
    state["task"] = asyncio.create_task(
        _poll_loop(key, body.bot_token, body.base_url, state),
        name=f"probe-poll-{key[:8]}",
    )
    return {
        "started": True,
        "key": key,
        "started_at": state["started_at"],
    }


# ── 4) stop long-poll ─────────────────────────────────────────────
class PollStopBody(BaseModel):
    bot_token: str


@router.post("/poll/stop")
async def probe_poll_stop(body: PollStopBody) -> dict:
    key = _strip_token(body.bot_token)
    stopped = await _stop_poll(key)
    return {"stopped": stopped, "key": key}


# ── 5) poll status / inbox ────────────────────────────────────────
@router.get("/poll/inbox")
async def probe_poll_inbox(bot_token: str) -> dict:
    key = _strip_token(bot_token)
    state = _poll_store.get(key)
    return {
        "key": key,
        "exists": state is not None,
        "cursor": state["cursor"] if state else None,
        "poll_count": state["poll_count"] if state else 0,
        "last_resp": state["last_resp"] if state else None,
        "started_at": state["started_at"] if state else None,
        "stopped_at": state["stopped_at"] if state else None,
    }


@router.get("/poll/messages")
async def probe_poll_messages(bot_token: str) -> dict:
    """Return AND clear all messages received by this bot_token's poll task."""
    key = _strip_token(bot_token)
    # Filter by bot_token prefix (all messages with this token)
    matched = [m for m in _inbox if m.get("_key") == key]
    for m in matched:
        _inbox.remove(m)
    return {
        "key": key,
        "count": len(matched),
        "messages": matched,
    }


# ── internal: long-poll loop ──────────────────────────────────────
async def _poll_loop(key: str, bot_token: str, base_url: str, state: Dict[str, Any]) -> None:
    base = (base_url or _BASE_URL).rstrip("/")
    cursor = state["cursor"] or ""
    backoff = 2.0
    try:
        while state.get("stopped_at") is None:
            state["poll_count"] += 1
            body = {
                "get_updates_buf": cursor,
                "base_info": {"channel_version": _CHANNEL_VERSION},
            }
            try:
                async with httpx.AsyncClient(timeout=_GETUPDATES_TIMEOUT) as c:
                    resp = await c.post(
                        f"{base}/ilink/bot/getupdates",
                        json=body,
                        headers=make_headers(bot_token),
                    )
                # iLink returns content-type=application/octet-stream but body is JSON;
                # always try to parse.
                try:
                    raw = resp.json()
                except Exception:
                    raw = {"_raw": resp.text[:300]}
            except Exception as exc:
                state["last_resp"] = {"error": f"client: {type(exc).__name__}: {str(exc)[:120]}"}
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                continue

            state["last_resp"] = {
                "http_status": resp.status_code,
                "content_type": resp.headers.get("content-type"),
                "keys": list(raw.keys()) if isinstance(raw, dict) else None,
                "ret": raw.get("ret") if isinstance(raw, dict) else None,
                "errcode": raw.get("errcode") if isinstance(raw, dict) else None,
                "errmsg": raw.get("errmsg") if isinstance(raw, dict) else None,
                "msg_count": len(raw.get("msgs") or []) if isinstance(raw, dict) else 0,
                "cursor": raw.get("get_updates_buf") if isinstance(raw, dict) else None,
                "sent_cursor": cursor[:30] if cursor else "EMPTY",
                "raw_size": len(resp.content),
            }

            if isinstance(raw, dict):
                new_cursor = raw.get("get_updates_buf") or ""
                if new_cursor:
                    cursor = new_cursor
                    state["cursor"] = cursor
                msgs = raw.get("msgs") or []
                for msg in msgs:
                    msg["_key"] = key
                    msg["_received_at"] = time.time()
                    _inbox.append(msg)

                # -14 means session timeout → stop the loop and clear cursor
                if raw.get("errcode") == -14 or raw.get("ret") == -14:
                    state["last_resp"]["_action"] = "session_timeout_detected_loop_exiting"
                    state["stopped_at"] = time.time()
                    cursor = ""
                    state["cursor"] = ""
                    break

            backoff = 2.0  # reset on success
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        state["last_resp"] = {"error": f"loop: {type(exc).__name__}: {str(exc)[:120]}"}
    finally:
        if state.get("stopped_at") is None:
            state["stopped_at"] = time.time()


async def _stop_poll(key: str) -> bool:
    state = _poll_store.get(key)
    if not state:
        return False
    state["stopped_at"] = time.time()
    task = state.get("task")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    return True


# ── 6) sendmessage ────────────────────────────────────────────────
class SendBody(BaseModel):
    bot_token: str
    to_user_id: str
    text: str
    context_token: str = ""
    base_url: str = _BASE_URL


@router.post("/send")
async def probe_send(body: SendBody) -> dict:
    import uuid as _uuid

    msg = {
        "from_user_id": "",
        "to_user_id": body.to_user_id,
        "client_id": str(_uuid.uuid4()),
        "message_type": 2,
        "message_state": 2,
        "item_list": [{"type": 1, "text_item": {"text": body.text}}],
    }
    if body.context_token:
        msg["context_token"] = body.context_token

    payload = {
        "msg": msg,
        "base_info": {"channel_version": _CHANNEL_VERSION},
    }

    base = (body.base_url or _BASE_URL).rstrip("/")
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as c:
        resp = await c.post(
            f"{base}/ilink/bot/sendmessage",
            json=payload,
            headers=make_headers(body.bot_token),
        )
    content_type = resp.headers.get("content-type", "")
    raw_bytes = resp.content
    raw_str = raw_bytes.decode("utf-8", errors="replace")
    try:
        parsed = resp.json()
    except Exception:
        parsed = None
    return {
        "http_status": resp.status_code,
        "content_type": content_type,
        "raw_body": raw_str[:1000],
        "parsed": parsed,
        "sent_payload": payload,
    }


# ── 7) bind_wechat + pool.add ────────────────────────────────────
class BindInjectBody(BaseModel):
    user_id: str
    wechat_uin: str
    bot_token: str


@router.post("/bind-inject")
async def probe_bind_inject(body: BindInjectBody) -> dict:
    """Directly invoke AgentService.bind_wechat + ilink_pool.add.

    Skips the iLink QR scan flow (which we can't trigger from a test).
    Use this to:
      1. Persist a confirmed bot_token to DB
      2. Spawn the per-user long-poll task in the live backend

    Combined with sending a WeChat message, this exercises the full
    inbound → AgentService → enqueue_outbound_message → outbound
    pipeline in the running backend.
    """
    from app.core.db import get_db_session
    from app.modules.agent.service import AgentService
    from app.channels.ilink_pool import get_connection_pool
    from app.channels.ilink_client import ILinkClient

    uid = UUID(body.user_id)
    # 1. Skip the iLink QR scan flow — directly call the same code path
    #    AgentService.bind_wechat would, but in one synchronous block.
    async for s in get_db_session(user_id=uid):
        svc = AgentService(s)
        await svc.unbind_wechat(uid)
        await s.commit()
        await svc.bind_wechat(uid, body.wechat_uin, body.bot_token)
        await s.commit()
        break

    # 2. Spawn the per-user long-poll task.
    await get_connection_pool().add(uid)
    return {
        "bound": True,
        "user_id": body.user_id,
        "active_tasks": get_connection_pool().active_count,
    }


@router.post("/full-bind")
async def probe_full_bind(body: BindInjectBody) -> dict:
    """End-to-end bind without the 30s iLink long-poll.

    Workflow:
      1. GET /ilink/bot/get_bot_qrcode → get fresh QR token
      2. Poll /ilink/bot/get_qrcode_status ONCE (NOT 30s long-poll) —
         if 'wait', retry up to 5 times with 1s sleep
      3. Once 'confirmed' → AgentService.bind_wechat + pool.add

    This avoids backend's /api/v1/agent/wechat/qrcode/status 30s hold
    (which causes 500s in iLink's rate-limited environment) and gets a
    real iLink bot_token in one HTTP call.
    """
    from app.core.db import get_db_session
    from app.modules.agent.service import AgentService
    from app.channels.ilink_pool import get_connection_pool
    from app.channels.ilink_client import ILinkClient

    # Step 1: get a fresh QR from iLink
    async with httpx.AsyncClient(timeout=15.0) as c:
        client = ILinkClient(bot_token="", base_url="https://ilinkai.weixin.qq.com")
        qr_resp = await c.get(
            f"https://ilinkai.weixin.qq.com/ilink/bot/get_bot_qrcode?bot_type=3",
            headers=client._make_headers() if hasattr(client, "_make_headers") else {},
        )
        qr_data = qr_resp.json()
        qrcode_token = qr_data["qrcode"]

    # Step 2: poll status with short retries
    bot_token = ""
    wechat_uin = body.wechat_uin
    for attempt in range(60):  # up to 60s
        async with httpx.AsyncClient(timeout=15.0) as c:
            try:
                r = await c.get(
                    "https://ilinkai.weixin.qq.com/ilink/bot/get_qrcode_status",
                    params={"qrcode": qrcode_token},
                    headers={"X-WECHAT-UIN": ""},
                )
                d = r.json()
            except Exception as e:
                await asyncio.sleep(1)
                continue
        if d.get("status") == "confirmed":
            bot_token = d.get("bot_token", "")
            wechat_uin = d.get("ilink_user_id", body.wechat_uin)
            break
        if d.get("status") == "expired":
            return {"bound": False, "reason": "qr_expired", "qrcode": qrcode_token}
        await asyncio.sleep(1)

    if not bot_token:
        return {"bound": False, "reason": "timed_out", "qrcode": qrcode_token}

    # Step 3: bind
    uid = UUID(body.user_id)
    async for s in get_db_session(user_id=uid):
        svc = AgentService(s)
        await svc.unbind_wechat(uid)
        await s.commit()
        await svc.bind_wechat(uid, wechat_uin, bot_token)
        await s.commit()
        break

    await get_connection_pool().add(uid)
    return {
        "bound": True,
        "user_id": body.user_id,
        "qrcode": qrcode_token,
        "bot_id": wechat_uin,
        "active_tasks": get_connection_pool().active_count,
    }


__all__ = ["router"]
