"""Agent Pydantic schemas — REQ-052 contracts/agent-api.yaml."""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AgentStatus = Literal["active", "degraded", "dormant"]
NotificationMode = Literal["realtime", "hourly_digest"]
# iLink returns "wait" (not "waiting"), CoPaw/Bote both use raw values.
QrcodeStatus = Literal["wait", "scanned", "confirmed", "expired"]


# ── QR Code Binding ────────────────────────────────────────────────


class QrcodeResponse(BaseModel):
    qrcode_token: str
    # Direct iLink / WeChat scan URL.
    qrcode_url: str
    # Browser-renderable PNG endpoint URL. JSON carries a URL, not base64.
    qrcode_image_url: str
    expires_at: datetime
    expires_in_sec: int = 300


class QrcodeStatusResponse(BaseModel):
    status: QrcodeStatus
    wechat_nickname: str | None = None
    wechat_avatar_url: str | None = None


# ── Binding ─────────────────────────────────────────────────────────


class BindingStatusResponse(BaseModel):
    bound: bool
    wechat_nickname: str | None = None
    wechat_avatar_url: str | None = None
    bound_at: datetime | None = None
    agent_status: AgentStatus = "dormant"


class UnbindResponse(BaseModel):
    message: str = "微信绑定已解除"


# ── Agent Status ────────────────────────────────────────────────────


class AgentStatusResponse(BaseModel):
    user_id: UUID
    status: AgentStatus
    display_name: str = "我的求职助手"
    wechat_bound: bool = False
    last_heartbeat_at: datetime | None = None
    messages_sent_total: int = 0
    messages_received_total: int = 0


# ── Preferences ─────────────────────────────────────────────────────


class AgentPreferencesResponse(BaseModel):
    display_name: str = "我的求职助手"
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    notification_mode: NotificationMode = "realtime"


class PatchPreferencesRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=20)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    notification_mode: NotificationMode | None = None


# ── Internal Send ───────────────────────────────────────────────────


class SendMessageRequest(BaseModel):
    user_id: UUID
    content: str = Field(min_length=1)
    priority: Literal["normal", "high"] = "normal"


class SendMessageResponse(BaseModel):
    message_id: UUID
    status: str = "queued"
    segment_count: int = 1


# ── Admin ───────────────────────────────────────────────────────────


class AgentAdminItem(BaseModel):
    user_id: UUID
    user_email: str = ""
    agent_status: AgentStatus
    wechat_nickname: str | None = None
    last_heartbeat_at: datetime | None = None
    messages_sent: int = 0
    messages_received: int = 0


class AgentAdminListResponse(BaseModel):
    items: list[AgentAdminItem]
    total: int
    page: int
    size: int
