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
from app.modules.resumes.api_avatar import router as resumes_avatar_router
from app.modules.sessions.api import router as sessions_router
from app.modules.tasks.api import router as tasks_router
from app.modules.versions.api import router as versions_router
# Phase 6
from app.modules.account.router import router as account_router
from app.modules.audit.router import router as audit_router
from app.modules.content.router import router as content_router
from app.api.v1.export import router as export_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(sessions_router, prefix="/users/me/sessions", tags=["sessions"])
# REQ-057 — Dashboard command-center summary (GET /me/dashboard-summary)
from app.modules.dashboard.api import router as dashboard_router

router.include_router(dashboard_router)
router.include_router(resumes_router, tags=["resumes"])
router.include_router(resumes_avatar_router, tags=["resumes-avatar"])
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
# Feature 006 — Personal Ability Profile
from app.modules.ability_profile.api import router as ability_profile_router

router.include_router(ability_profile_router)
# Phase 6 — account (lifecycle, export, import, notification, devices, security)
router.include_router(account_router)
# Phase 6 — audit (user + admin)
router.include_router(audit_router)
# Phase 6 — content (resources, help, search)
router.include_router(content_router)
# Feature 012 - Resume export gateway
router.include_router(export_router, tags=["export"])
# Feature 013 - User Avatar
from app.modules.avatars import router as avatars_router
router.include_router(avatars_router, tags=["avatars"])
# WS endpoints are mounted at app level (not included here)

# Phase 5 — Agent subgraph endpoints
from app.api.v1.agents_resume_optimize import router as resume_optimize_router
from app.api.v1.agents_error_coach import router as error_coach_router
from app.api.v1.agents_general_coach import router as general_coach_router

router.include_router(resume_optimize_router)
router.include_router(error_coach_router)
router.include_router(general_coach_router)

# Phase 7 — Global search command palette
from app.modules.search import router as search_router

router.include_router(search_router, tags=["search"])

# REQ-055 — Resume root / derive
# MUST mount before resumes_v2 so literal paths like /v2/resumes/root and
# /v2/resumes/derive are not swallowed by /v2/resumes/{resume_id}.
from app.modules.resume_intelligence.api import router as resume_intelligence_router
from app.modules.resume_derive.api import router as resume_derive_router

# Intelligence must register before derive so overlapping
# GET /v2/resumes/{id}/suggestions?analysis_id= resolves to REQ-059.
router.include_router(resume_intelligence_router, tags=["resume-intelligence"])
router.include_router(resume_derive_router, tags=["resume-derive"])

# Feature 032 — Resume v2 (renderer + editor)
from app.modules.resumes_v2.api import router as resumes_v2_router

router.include_router(resumes_v2_router, tags=["resumes-v2"])

# REQ-052 — Personal Agent + WeChat Channel
from app.modules.agent.api import router as agent_router

router.include_router(agent_router)

# REQ-053 — Interview Intelligence Engine
from app.modules.research.api import router as research_router

router.include_router(research_router, tags=["research"])

# REQ-061 — AI Runtime control plane
from app.modules.ai_runtime.api import router as ai_runtime_router

router.include_router(ai_runtime_router)

# REQ-061 — AI Metering / experience points (OpenAPI: /api/v1/ai-points/*)
from app.modules.ai_metering.api import router as ai_metering_router

router.include_router(ai_metering_router)

__all__ = ["router"]
