---
name: admin-console-baseline-for-req044
description: Pre-REQ-044 admin console = 4-item nav + LogCenter shipped (REQ-039 B1/B2) + pm_dashboard 6 panels shipped (REQ-033). REQ-044 will redesign 4→8 workspaces.
metadata:
  reference
---

REQ-044 在动手前需要明确哪些代码已 ship 哪些是 stub。具体基线（2026-07-04 实查）：

**已 ship（可复用）：**
- `backend/app/modules/admin_console/` — 8 文件全 ship: api.py (7 endpoints) + audit.py (4 audit writer) + auth.py (REPLAY_TRIGGER + TASK_TAG capability, admin/viewer role) + models.py (TaskTag + AdminAuditLog + Trace 投影) + rate_limit.py (sliding window 5/min replay, 20/min diff) + repository.py (RLS-aware CRUD) + schemas.py (TaskTag/Diff/Replay/PayloadChunk/AdminAuditEntry/ErrorResponse/RateLimitedError) + service.py (Orchestration)。Mounted at `/api/v1/admin-console/observability`。
- `backend/app/modules/pm_dashboard/` — 6 panels (overview/funnel/resume-diagnosis/mock-interview/ai-operations/version-experiment) + DashboardFilter + QualityFlags schema。Mounted at `/api/v1/pm-dashboard`。
- `backend/app/modules/telemetry_contracts/` — 9 文件: costs/metrics/models/redaction_cli/retention_cli/repository/schemas/README + __init__。metric 定义库 + token cost 估算 + redaction + retention 工具。
- `src/admin/` — main.tsx + routes.tsx + AdminShell.tsx + LogCenter.tsx + LogCenter 命令面板 + 6 log 组件 (TaskList/FilterBar/DetailPanel/ErrorAggregation/Dialogs 4 种/CommandPalette) + styles/admin.css。

**Stub/缺：**
- AdminShell NAV_ITEMS 只有 4 项: dashboard/log-center/trace-explorer/eval-center，后 3 个是 PlaceholderPage。
- LogCenterTaskList 等组件仍保持「log center 为中心」UX。FR-004 要求 raw logs 不再是 PM 默认体验，需重新归位到 Logs & Traces workspace。

**Cross-team contract L031 风险：** 前端扩 WorkspaceId / PanelId Literal 必须同步后端 Pydantic Literal；如果后端扩 audit VALID_ACTIONS (4→7)，前端 audit log viewer 要同步显示新 token。
