"""Agent API endpoints — REQ-052.

QR code binding, agent status, preferences, admin endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.channels.ilink_client import ILinkClient
from app.modules.agent.schemas import (
    AgentAdminItem,
    AgentAdminListResponse,
    AgentPreferencesResponse,
    AgentStatusResponse,
    BindingStatusResponse,
    PatchPreferencesRequest,
    QrcodeResponse,
    QrcodeStatusResponse,
    SendMessageRequest,
    SendMessageResponse,
    UnbindResponse,
)
from app.modules.agent.service import AgentService, WeChatAlreadyBoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ── In-memory QR code session store (TTL 300s) ─────────────────────
# Redis is read-only in this environment, so we use a simple dict with TTL.
_qrcode_store: dict[str, tuple[str, float, str]] = {}  # token -> (user_id, expires_at, scan_url)
_LITEAPP_QRCODE_BASE_URL = "https://liteapp.weixin.qq.com/q/7GiQu1"


def _clean_qrcode_store() -> None:
    now = time.monotonic()
    expired = [k for k, (_, exp, _) in _qrcode_store.items() if now > exp]
    for k in expired:
        del _qrcode_store[k]


def _store_qrcode(token: str, user_id: str, scan_url: str, ttl: int = 300) -> None:
    _clean_qrcode_store()
    _qrcode_store[token] = (user_id, time.monotonic() + ttl, scan_url)


def _get_qrcode_user(token: str) -> str | None:
    _clean_qrcode_store()
    entry = _qrcode_store.get(token)
    if entry is None:
        return None
    user_id, expires, _scan_url = entry
    if time.monotonic() > expires:
        del _qrcode_store[token]
        return None
    return user_id


def _delete_qrcode(token: str) -> None:
    _qrcode_store.pop(token, None)


def _get_qrcode_scan_url(token: str) -> str | None:
    _clean_qrcode_store()
    entry = _qrcode_store.get(token)
    if entry is None:
        return None
    _user_id, expires, scan_url = entry
    if time.monotonic() > expires:
        del _qrcode_store[token]
        return None
    return scan_url


def _ilink_qrcode_url(data: dict[str, Any]) -> str:
    """Resolve the direct iLink / WeChat scan URL returned by iLink."""
    direct_url = str(data.get("url") or data.get("qrcode_img_content") or "").strip()
    if direct_url.startswith(("https://", "http://")):
        return direct_url

    qrcode_token = str(data.get("qrcode") or "").strip()
    if not qrcode_token:
        raise HTTPException(status_code=502, detail="WeChat returned empty QR code data")
    return f"{_LITEAPP_QRCODE_BASE_URL}?qrcode={quote(qrcode_token, safe='')}&bot_type=3"


def _qrcode_image_endpoint(qrcode_token: str) -> str:
    return f"/api/v1/agent/wechat/qrcode/image?qrcode_token={quote(qrcode_token, safe='')}"


def _render_qr_png_bytes(payload: str) -> bytes:
    import io

    import qrcode
    from qrcode.image.pil import PilImage

    img = qrcode.make(payload, image_factory=PilImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Statuses that the QR-code response contract (QrcodeStatus Literal) accepts.
_VALID_QRCODE_STATUSES = {"wait", "scanned", "confirmed", "expired"}
# iLink can return tokens outside the contract (e.g. "scanning" mid-flow, or
# transient "cancel"/"timeout"). Aliases map them back to a valid enum value.
_QRCODE_STATUS_ALIASES = {"scanning": "scanned"}


def _normalize_qrcode_status(raw: Any) -> str:
    """Coerce an iLink status string to the QrcodeStatus contract enum.

    Unknown / out-of-enum values fall back to ``"wait"`` so the polling
    endpoint never 500s on a Pydantic response_model validation error.
    """
    value = _QRCODE_STATUS_ALIASES.get(str(raw or "").lower(), str(raw or "").lower())
    if value not in _VALID_QRCODE_STATUSES:
        return "wait"
    return value


@router.get("/ping")
async def ping():
    return {"ok": True, "route": "/api/v1/agent/ping"}


@router.get("/wechat/qrcode/page")
async def get_qrcode_page(
    token: str = Query(...),
):
    """Return an HTML page with QR code. Auth via query param for browser use."""
    # Manual dependency since Query() breaks Depends ordering
    from app.core.db import get_db_session as _get_db_session
    async for _session in _get_db_session():
        svc = AgentService(_session)
        break

    # Decode JWT from query param
    from app.core.security import decode_token
    import jwt as pyjwt
    try:
        payload = decode_token(token, expected_type="access")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = UUID(payload.sub)
    """Return an HTML page with the QR code for browser display."""
    from fastapi.responses import HTMLResponse

    await svc.ensure_agent_exists(user_id)

    client = ILinkClient()
    await client.start()
    try:
        data = await client.get_bot_qrcode()
        qrcode_token = data["qrcode"]
        qrcode_url = _ilink_qrcode_url(data)
        _store_qrcode(qrcode_token, str(user_id), qrcode_url, ttl=300)
    finally:
        await client.stop()

    token_short = qrcode_token[:16] if len(qrcode_token) > 16 else qrcode_token
    qrcode_image_url = _qrcode_image_endpoint(qrcode_token)
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>微信扫码绑定 - InterCraft</title>
<style>
  body { text-align: center; padding: 60px 20px; font-family: -apple-system, sans-serif; }
  img { border: 3px solid #07c160; border-radius: 12px; max-width: 280px; }
  h2 { color: #333; } .status { font-size: 18px; margin: 16px 0; font-weight: bold; }
  .waiting { color: #999; } .scanned { color: #f90; } .confirmed { color: #07c160; } .expired { color: #e33; }
  .timer { color: #999; margin: 8px 0; }
  .spinner { display: inline-block; width: 20px; height: 20px; border: 2px solid #ddd; border-top-color: #07c160; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style></head><body>
<h2>📱 使用微信扫码绑定</h2>
<img src=\"""" + qrcode_image_url + """\" onerror="this.alt='QR load failed'" id="qr-img">
<p class="status waiting" id="status"><span class="spinner"></span>等待扫码…</p>
<p class="timer" id="timer">剩余 300 秒</p>
<script>
const Q = '""" + qrcode_token + """';
const AUTH = '""" + token + """';
let s = 300;
let stopped = false;
const stEl = document.getElementById('status');
const tmEl = document.getElementById('timer');
const imgEl = document.getElementById('qr-img');
const STATUS_MAP = {
  wait: ['waiting', '等待扫码…', 'spinner'],
  scanned: ['scanned', '已扫码，请在微信中确认', ''],
  confirmed: ['confirmed', '✅ 绑定成功！Agent 已激活', ''],
  expired: ['expired', '❌ 二维码已过期，请刷新页面', '']
};
async function poll() {
  if (stopped) return;
  try {
    const resp = await fetch('/api/v1/agent/wechat/qrcode/status?qrcode_token=' + Q,
      {headers: {'Authorization': 'Bearer ' + AUTH}});
    if (!resp.ok) { if (resp.status === 404) { stop('expired'); return; } return; }
    const data = await resp.json();
    const s = data.status || 'wait';
    const [cls, text, extra] = STATUS_MAP[s] || STATUS_MAP.wait;
    stEl.className = 'status ' + cls;
    stEl.innerHTML = (extra ? '<span class="' + extra + '"></span>' : '') + text;
    if (s === 'confirmed') { stopped = true; imgEl.style.opacity = '0.3'; return; }
    if (s === 'expired') { stopped = true; imgEl.style.opacity = '0.3'; return; }
  } catch(e) { console.error(e); }
  if (!stopped) setTimeout(poll, 2000);
}
function stop(reason) {
  stopped = true;
  const [cls, text] = STATUS_MAP[reason] || STATUS_MAP.expired;
  stEl.className = 'status ' + cls; stEl.textContent = text;
  imgEl.style.opacity = '0.3';
}
setInterval(() => {
  s--;
  tmEl.textContent = s <= 0 ? '已过期，请刷新' : '剩余 ' + s + ' 秒';
  if (s <= 0 && !stopped) stop('expired');
}, 1000);
setTimeout(poll, 1000);
</script></body></html>"""
    return HTMLResponse(content=html)


# ── Dependency ──────────────────────────────────────────────────────


def _agent_svc(
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
) -> AgentService:
    return AgentService(session)


# ── QR Code Binding ─────────────────────────────────────────────────


@router.get("/wechat/qrcode", response_model=QrcodeResponse)
async def get_qrcode(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    svc: Annotated[AgentService, Depends(_agent_svc)],
) -> QrcodeResponse:
    """Generate a WeChat iLink QR code for binding. Binds to current user_id."""
    await svc.ensure_agent_exists(user_id)

    client = ILinkClient()
    await client.start()
    try:
        data = await client.get_bot_qrcode()
        qrcode_token = data["qrcode"]
        qrcode_url = _ilink_qrcode_url(data)
        qrcode_image_url = _qrcode_image_endpoint(qrcode_token)

        # Store in memory (Redis is read-only in this environment)
        _store_qrcode(qrcode_token, str(user_id), qrcode_url, ttl=300)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=300)
        return QrcodeResponse(
            qrcode_token=qrcode_token,
            qrcode_url=qrcode_url,
            qrcode_image_url=qrcode_image_url,
            expires_at=expires_at,
            expires_in_sec=300,
        )
    finally:
        await client.stop()


@router.get("/wechat/qrcode/image")
async def get_qrcode_image(qrcode_token: str = Query(...)) -> Response:
    """Return a PNG QR image for the stored iLink scan URL."""
    scan_url = _get_qrcode_scan_url(qrcode_token)
    if scan_url is None:
        raise HTTPException(status_code=404, detail="QR code expired or invalid")
    return Response(
        content=_render_qr_png_bytes(scan_url),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/wechat/qrcode/status", response_model=QrcodeStatusResponse)
async def get_qrcode_status(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    qrcode_token: str = Query(...),
) -> QrcodeStatusResponse:
    """Poll QR code scan status. Validates user_id against QR code creator."""
    creator_id = _get_qrcode_user(qrcode_token)
    if creator_id is None:
        raise HTTPException(status_code=404, detail="QR code expired or invalid")
    if creator_id != str(user_id):
        raise HTTPException(status_code=403, detail="QR code belongs to another user")

    # DEBUG: log every poll invocation so we can see if user is polling at all
    logger.info(
        "qrcode_status_poll user=%s token=%s",
        str(user_id)[:8],
        qrcode_token[:12],
    )

    client = ILinkClient()
    await client.start()
    try:
        try:
            data = await client.get_qrcode_status(qrcode_token)
        except Exception as exc:
            logger.warning("ilink_qrcode_status_failed", extra={"error": str(exc)[:120]})
            # If iLink is slow/unreachable, return current known state
            return QrcodeStatusResponse(status="wait")

        # iLink can return statuses outside our enum (e.g. "scanning" mid-flow,
        # or transient tokens like "cancel" / "timeout"). Normalize to the
        # contract enum so Pydantic response_model doesn't 500.
        status = _normalize_qrcode_status(data.get("status"))

        # DEBUG: log iLink raw response when confirmed (or unexpected status)
        if status == "confirmed" or data.get("errcode"):
            logger.info(
                "iLink_confirmed_raw user=%s data=%s",
                str(user_id)[:8],
                {k: (str(v)[:60] if k != "msgs" else f"<{len(v)} msgs>")
                 for k, v in data.items()},
            )

        if status == "confirmed":
            bot_token = data.get("bot_token", "")
            # iLink confirmed response uses ``ilink_user_id`` for the WeChat
            # openid of the user who scanned the QR. Use it as wechat_uin so
            # the binding row matches the real WeChat user — otherwise the
            # later inbound → agent reply path can't find the user and
            # returns the "未识别到您的账号" fallback. Fall back to the
            # placeholder only if iLink didn't return an openid.
            wechat_uin = data.get("ilink_user_id") or data.get("wechat_uin") or f"wx_{user_id}"

            from app.core.db import get_db_session

            # Bind to DB (explicit commit so the pool task below sees the
            # new credential + binding rows). The async-for `get_db_session`
            # also commits on successful exit, but we want the commit
            # to happen BEFORE we spawn the pool task — otherwise the
            # pool can read stale rows under transaction isolation.
            async for session in get_db_session(user_id=user_id):
                svc = AgentService(session)
                await svc.bind_wechat(user_id, wechat_uin, bot_token)
                await session.commit()
                break

            # Spawn long-poll task in the connection pool
            from app.channels.ilink_pool import get_connection_pool

            await get_connection_pool().add(user_id)
            logger.info("pool_task_added_after_bind", extra={"user_id": str(user_id)})

            _delete_qrcode(qrcode_token)

        return QrcodeStatusResponse(status=status)
    finally:
        await client.stop()


@router.get("/wechat/binding", response_model=BindingStatusResponse)
async def get_binding(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    svc: Annotated[AgentService, Depends(_agent_svc)],
) -> BindingStatusResponse:
    status = await svc.get_binding_status(user_id)
    return BindingStatusResponse(**status)


@router.delete("/wechat/binding", response_model=UnbindResponse)
async def unbind_wechat(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    svc: Annotated[AgentService, Depends(_agent_svc)],
) -> UnbindResponse:
    await svc.unbind_wechat(user_id)

    # Remove long-poll task from connection pool
    from app.channels.ilink_pool import get_connection_pool

    await get_connection_pool().remove(user_id)
    logger.info("pool_task_removed_after_unbind", extra={"user_id": str(user_id)})

    return UnbindResponse(message="微信绑定已解除")


# ── Agent Status ────────────────────────────────────────────────────


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    svc: Annotated[AgentService, Depends(_agent_svc)],
) -> AgentStatusResponse:
    status = await svc.get_agent_status(user_id)
    return AgentStatusResponse(**status)


# ── Preferences ─────────────────────────────────────────────────────


@router.get("/preferences", response_model=AgentPreferencesResponse)
async def get_preferences(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    svc: Annotated[AgentService, Depends(_agent_svc)],
) -> AgentPreferencesResponse:
    pref = await svc.pref_repo.get_by_user(user_id)
    if pref is None:
        return AgentPreferencesResponse()
    return AgentPreferencesResponse(
        display_name=pref.display_name,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        notification_mode=pref.notification_mode,
    )


@router.patch("/preferences", response_model=AgentPreferencesResponse)
async def patch_preferences(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    body: PatchPreferencesRequest,
    svc: Annotated[AgentService, Depends(_agent_svc)],
) -> AgentPreferencesResponse:
    pref = await svc.pref_repo.upsert(
        user_id,
        display_name=body.display_name,
        quiet_hours_start=body.quiet_hours_start,
        quiet_hours_end=body.quiet_hours_end,
        notification_mode=body.notification_mode,
    )
    return AgentPreferencesResponse(
        display_name=pref.display_name,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        notification_mode=pref.notification_mode,
    )


# ── Internal: Send Message ──────────────────────────────────────────


@router.post("/internal/send-message", response_model=SendMessageResponse)
async def internal_send_message(
    body: SendMessageRequest,
) -> SendMessageResponse:
    """Send a message to a user's WeChat. Called by ARQ workers / CLI / admin."""
    from app.channels.message_handler import enqueue_outbound_message
    from app.core.db import get_db_session

    async for session in get_db_session(user_id=body.user_id):
        message_ids = await enqueue_outbound_message(
            body.user_id,
            body.content,
            session=session,
            priority=getattr(body, "priority", "normal"),
        )
        break

    return SendMessageResponse(
        message_id=message_ids[0] if message_ids else None,
        status="queued",
        segment_count=len(message_ids),
    )


# ── Admin ───────────────────────────────────────────────────────────


@router.get("/admin/agents", response_model=AgentAdminListResponse)
async def admin_list_agents(
    svc: Annotated[AgentService, Depends(_agent_svc)],
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> AgentAdminListResponse:
    """List all agents (admin only)."""
    agents = await svc.agent_repo.list_by_status(status or "active", limit=size)
    items = [
        AgentAdminItem(
            user_id=a.user_id,
            agent_status=a.status,
            last_heartbeat_at=a.last_heartbeat_at,
        )
        for a in agents
    ]
    return AgentAdminListResponse(
        items=items,
        total=len(items),
        page=page,
        size=size,
    )
