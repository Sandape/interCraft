"""Bootstrap script: seed in-memory admin role for demo user, then start uvicorn.

Workaround: REQ-039 B1 capability auth uses process-local role map; no
startup hook seeds demo user as admin. For E2E we pre-grant the role
before starting the ASGI server.

# FIXME: REQ-039 临时方案 — 当前 _user_roles 是进程内 dict，无 DB 持久化。
# FIXME: 未来迁 DB-backed RBAC 时此 bootstrap 应改为调用 RBAC 服务并弃用
# FIXME: auth.set_default_role / auth.grant_role helper。Ticket: REQ-039-POLISH。

# SECURITY: 我们只对 demo 用户显式 grant_role("admin")，不调
# set_default_role("admin")——后者会把「任何未显式赋权的用户」也变成 admin，
# 违反最小权限原则。E2E 之外的生产部署如果误用这个 bootstrap，会全员 admin。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID

# Bootstrap BEFORE importing uvicorn so the same in-process role map is used.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modules.admin_console import auth  # noqa: E402

DEMO_USER_ID = UUID("019ebc56-fb4f-7978-bf91-29abc5c13d93")
# Only grant demo user explicitly — do NOT call set_default_role("admin")
# (that would make any unknown user an admin too; violates least-privilege).
auth.grant_role(DEMO_USER_ID, "admin")
print(f"[bootstrap] demo user {DEMO_USER_ID} granted admin role", flush=True)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8202,
        log_level="warning",
    )