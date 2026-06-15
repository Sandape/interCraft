"""API v1 router — mounts all v1 sub-routers (Phase 1-6)."""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.abilities.api import router as abilities_router
from app.modules.activities.api import router as activities_router
from app.modules.errors.api import router as errors_router
from app.modules.auth.api import router as auth_router
from app.modules.auth.users_api import router as users_router
from app.modules.interviews.api import router as interviews_router
from app.modules.jobs.api import router as jobs_router
from app.modules.locks.api import router as locks_router
from app.modules.locks.ws_handler import router as locks_ws_router
from app.modules.outbox.api import router as outbox_router
from app.modules.resumes.api import router as resumes_router
from app.modules.sessions.api import router as sessions_router
from app.modules.tasks.api import router as tasks_router
from app.modules.versions.api import router as versions_router
# Phase 6
from app.modules.account.router import router as account_router
from app.modules.audit.router import router as audit_router
from app.modules.content.router import router as content_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(sessions_router, prefix="/users/me/sessions", tags=["sessions"])
router.include_router(resumes_router, tags=["resumes"])
router.include_router(versions_router, tags=["versions"])
router.include_router(abilities_router, tags=["abilities"])
router.include_router(errors_router, tags=["error-questions"])
router.include_router(jobs_router, tags=["jobs"])
router.include_router(tasks_router, tags=["tasks"])
router.include_router(activities_router, tags=["activities"])
router.include_router(interviews_router, tags=["interview-sessions"])
# Phase 3
router.include_router(locks_router, tags=["locks"])
router.include_router(outbox_router, tags=["outbox"])
# Phase 6 — account (lifecycle, export, import, notification, devices, security)
router.include_router(account_router)
# Phase 6 — audit (user + admin)
router.include_router(audit_router)
# Phase 6 — content (resources, help, search)
router.include_router(content_router)
# WS endpoints are mounted at app level (not included here)

# Phase 5 — Agent subgraph endpoints
from app.api.v1.agents_resume_optimize import router as resume_optimize_router
from app.api.v1.agents_error_coach import router as error_coach_router
from app.api.v1.agents_general_coach import router as general_coach_router

router.include_router(resume_optimize_router)
router.include_router(error_coach_router)
router.include_router(general_coach_router)

__all__ = ["router"]
