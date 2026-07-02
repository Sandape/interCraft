"""Bootstrap script: seed in-memory admin role for demo user, then start uvicorn.

Workaround: REQ-039 B1 capability auth uses process-local role map; no
startup hook seeds demo user as admin. For E2E we pre-grant the role
before starting the ASGI server.
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
auth.set_default_role("admin")
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