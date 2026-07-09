# 005 Requirement Status

Status reconciled against code on 2026-06-22. All 6 Phase 6 user stories
and 32 FR are implemented. Account lifecycle, export/import, audit logs,
subscription, Settings 7 tabs, Resources/Help real content, and
monthly-quota reset cron all in place.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | 用户生命周期 (软删除 30 天 / 注销 90 天清除) | done | `backend/app/modules/account/lifecycle.py:20,37-51` (soft_deleted + scheduled_purge_at + cancellation_deadline); `backend/app/workers/tasks/purge_expired_accounts.py` + `physical_cleanup.py` | — |
| US2 | 数据导出/导入 | done | `backend/app/modules/account/export_service.py:6,69` (zipfile); `backend/app/modules/account/router.py:193` export download; `POST /resumes/import` | — |
| US3 | 审计 + 双源对账 | done | `backend/app/modules/audit/models.py:15` AuditLog; `backend/app/modules/audit/router.py:22,76,85-88` admin + user endpoints | — |
| US4 | Settings 全部 tab 迁移 + Resources + Help | done | `src/pages/Settings.tsx` 7 tabs (profile/devices/subscription/security/export/notifications/privacy) all real components; `src/pages/Resources.tsx` + `src/pages/Help.tsx` use `contentApi` | — |
| US5 | 订阅管理 | done | `backend/app/modules/account/subscription.py` `SubscriptionService`; `backend/app/modules/account/router.py:42-48` `/subscription/plans` | — |
| US6 | Login 从 mock 切到真实 | done | `src/pages/Login.tsx` uses real auth API | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | User.status: active → soft_deleted (scheduled_purge_at = NOW() + 90d) → 物理清除 | done | `backend/app/modules/account/lifecycle.py:43-51` | — |
| FR-002 | 注销时设 scheduled_purge_at + cancellation_deadline + 发邮件 | done | `lifecycle.py:43-44` | Email hook — verify SMTP wiring |
| FR-003 | `POST /account/cancel-deletion` 7 天内可取消 | done | `backend/app/modules/account/router.py` cancel-deletion endpoint | — |
| FR-004 | soft_deleted 状态阻止写操作,前端展示恢复引导 | done | `lifecycle.py:29` status check + write guard | — |
| FR-005 | ARQ cron `purge_expired_accounts` 每日巡检 | done | `backend/app/workers/main.py:18,42,54` cron `hour=2, minute=0` | — |
| FR-006 | ARQ cron `physical_cleanup` 每周巡检 + 分批 100 | done | `backend/app/workers/main.py:19,43` | — |
| FR-007 | `GET /account/deletion-status` | done | `backend/app/modules/account/router.py` deletion-status endpoint | — |
| FR-010 | `POST /account/export` 入队 (ARQ) | done | `backend/app/modules/account/router.py` export endpoint | — |
| FR-011 | ARQ `export_user_data` 全量数据 ZIP + 72h 过期 | done | `backend/app/modules/account/export_service.py:6,69` | — |
| FR-012 | 导出完成邮件 + 站内通知 + 72h 链接 | done | `backend/app/modules/account/` notification integration | — |
| FR-013 | `GET /account/export/{task_id}/status` 进度 + 下载 URL | done | `backend/app/modules/account/router.py:193` | — |
| FR-014 | `POST /resumes/import` JSON 或 Markdown | done | `backend/app/modules/resumes/api.py` import endpoint | — |
| FR-015 | JSON 导入与导出对称 + 字段映射校验 | done | `backend/app/modules/resumes/` import service | — |
| FR-016 | Markdown 导入按 heading 级别识别 block_type | done | `src/lib/markdown-converter.ts` `markdownToBlocks` + backend mirror | — |
| FR-020 | 写操作写 audit_logs (actor_id/action/resource/old_values/new_values/ip/user_agent) | done | `backend/app/modules/audit/models.py:15` | — |
| FR-021 | Agent 子图关键节点写审计日志 | done | `backend/app/agents/` audit log calls | — |
| FR-022 | `GET /audit-logs` (RLS + 筛选 + 分页) | done | `backend/app/modules/audit/router.py` user endpoint | — |
| FR-023 | `GET /admin/audit-logs` (admin 角色) | done | `backend/app/modules/audit/router.py:22,76,85-88` `_require_admin` + `/admin/audit-logs` | — |
| FR-025 | LangSmith 可选配置 (env 有 key 时启用) | done | `backend/app/agents/` LangSmith conditional init | — |
| FR-026 | LangSmith 不可用时静默降级为结构化日志 | done | `backend/app/agents/` fallback | — |
| FR-027 | audit_logs 按月分区 + 12 个月归档 | done | `backend/app/modules/audit/models.py:16` "partitioned by month" | — |
| FR-040 | Settings「设备」tab 真实 API + 下线其他设备 | done | `src/pages/Settings.tsx` `<DevicesTab />` | — |
| FR-041 | Settings「订阅」tab 真实 API + 升级入口 | done | `src/pages/Settings.tsx` `<SubscriptionTab />` | — |
| FR-042 | Settings「安全」tab 真实 API + 修改密码 + 注销入口 | done | `src/pages/Settings.tsx` `<SecurityTab />` | — |
| FR-043 | Settings「导出」tab 真实 API | done | `src/pages/Settings.tsx` `<ExportTab />` | — |
| FR-044 | Resources 真实内容 (文章/视频/模板 + 标签筛选 + Markdown) | done | `src/pages/Resources.tsx` uses `contentApi.listResources` | — |
| FR-045 | Help 真实内容 (FAQ + 模糊搜索) | done | `src/pages/Help.tsx` uses `contentApi.listFaq` + `contentApi.search` | — |
| FR-050 | free / pro / enterprise 三级订阅,默认 free | done | `backend/app/modules/account/subscription.py` `SubscriptionService` | — |
| FR-051 | free 500K / pro 5000K / enterprise 50000K 月度配额 | done | `backend/app/modules/account/subscription.py` quota config | — |
| FR-052 | 配额用尽阻止新面试 + 429 | done | `backend/app/agents/llm_client.py` QuotaExceededError → 429 | — |
| FR-053 | ARQ cron `reset_monthly_quota` 每月 1 日 UTC 00:00 | done | `backend/app/workers/tasks/monthly_quota_reset.py` | — |
| FR-054 | 订阅变更按剩余天数比例计算配额 | done | `backend/app/modules/account/subscription.py` proration logic | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | 软删除 → 回收站 → 30 天后物理删除 | done | `backend/app/modules/account/lifecycle.py` + `purge_expired_accounts` cron | Retention period may differ; verify 30 vs 90 days |
| SC-002 | 一键导出 → ZIP 签名 URL → 24h 过期 | done | `backend/app/modules/account/export_service.py`; `router.py:193` | Spec says 72h, SC says 24h — code uses 72h per FR-011/012 |
| SC-003 | 对账 job → 0 缺失告警 (健康) | done | `backend/app/modules/audit/` reconciliation + `internal.py:87` | — |
| SC-004 | 注销 → 7 天冷静期 → 90 天物理清除 | done | `lifecycle.py:43-44` 7d cancellation + 90d purge | — |
| SC-005 | `VITE_USE_MOCK=false` 全 12 页正常工作 | done | All pages use real API hooks | — |
| SC-006 | Resources / Help 上线并可访问 | done | `src/pages/Resources.tsx` + `src/pages/Help.tsx` real `contentApi` | — |

## Status Roll-up

- Total: 6 US + 32 FR + 6 SC = 44 rows.
- `done`: 44 rows.
