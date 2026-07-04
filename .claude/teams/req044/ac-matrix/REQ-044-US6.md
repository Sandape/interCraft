---
req_id: REQ-044-US6
status: locked
locked_at: 2026-07-04
locked_by: dev-implement
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-044-US6 — Governance / Audit / Export / Retention (FR-031~FR-036)

## SC Gaps

- 无。spec.md US6 (line 259-285) + SC-008/009/010/011 + Edge Cases 4 类 (sensitive reveal deny 后已开 trace、export 含 expired、retention 改 → cache invalidation、governance 自我审计) 全部覆盖。
- spec US6 line 274-276 "5 role × workspace/field/action/export" least-privilege → FR-031 RBAC matrix 5 role × 8 workspace × 6 capability。
- spec US6 line 278-279 "actor / time / target / action / reason / result / visibility_mode" 7 字段全部进 FR-034 audit event schema。
- spec US6 line 281-282 "approved fields / redaction state / freshness state / filters / audit metadata" → FR-035 export whitelist 5 类 metadata。
- spec US6 line 284-285 "retention window → unavailable due to retention → don't serve stale cached sensitive content" → FR-036 retention expiry + cache invalidation (EC-3)。

## AC 矩阵

| AC-ID | 描述 | 验证方式 (命令/测试名/可观测指标) | 来源 (spec) |
|-------|------|-----------------------------------|-------------|
| AC-31.1 | 后端 `GET /api/v1/admin-console/governance/access-matrix` 返回 5 role × 8 workspace × 6 capability 矩阵 (RBAC_VIEW capability) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_access_matrix_returns_full_grid -v` | FR-031 |
| AC-31.2 | 前端 Governance workspace 顶部 Access Matrix table 显示 5×8 网格 (read / write / change / export / reveal / audit) | `grep -c "AccessMatrixTable\|role-row\|workspace-col" src/admin/components/governance/AccessMatrixTable.tsx` 期望 ≥ 3 | FR-031 |
| AC-31.3 | role 在某 workspace 无 read capability 时,sidebar 该项不可见 (与 US1 resolveRole 一致) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_viewer_denied_governance_workspace -v` (view role → 403) | FR-031 + SC-008 |
| AC-31.4 | UserPrivacySafe 字段级权限: 前端 sensitive 字段 (raw_resume / raw_interview_answer / raw_prompt / raw_model_output) 显示 'hidden' / 'masked' / 'full' 三档 | `grep -c "permission-state\|hidden\|masked\|full" src/admin/components/governance/FieldPermissionBadge.tsx` 期望 ≥ 2 | FR-031 (field) |
| AC-32.1 | 前端 workspace 不展示 raw 字段 (grep `raw_resume\|raw_prompt\|raw_model_output\|raw_interview_answer` 业务代码必须 0 命中) | `grep -rF "raw_resume\|raw_prompt\|raw_model_output\|raw_interview_answer" src/admin/pages/ src/admin/components/governance/ 2>/dev/null` 期望 0 命中业务代码 | FR-032 + SC-010 |
| AC-32.2 | backend `UserPrivacySafe` schema 不含 raw_* 字段 (Pydantic Literal schema lock) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_user_privacy_safe_no_raw_fields -v` (Pydantic schema 字段集白名单校验) | FR-032 |
| AC-32.3 | sensitive 字段 mask 规则: 返回 '***REDACTED***' 字符串,不返回原值 | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_sensitive_field_redacted_to_string -v` | FR-032 |
| AC-32.4 | reveal 请求被 deny 时,console 显示 "access denied" + reason + audit_event_id | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_reveal_denied_returns_audit_event_id -v` | FR-032 + FR-033 |
| AC-33.1 | 后端 `POST /api/v1/admin-console/governance/reveal-requests` payload: {target_type, target_id, reason (≥ 20 chars)};audit log 写 actor / timestamp / target / reason / result / visibility_mode | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_create_reveal_request_audit_fields -v` | FR-033 + FR-034 |
| AC-33.2 | 后端 `GET /api/v1/admin-console/governance/reveal-requests` 列出 reveal 审计 (AUDIT_VIEW) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_list_reveal_requests_requires_audit_view -v` | FR-033 |
| AC-33.3 | 前端 Reveal Request form 含 reason textarea (≥ 20 chars 强制) + submit | `grep -c "minLength\|20\|reason-textarea\|reveal-reason" src/admin/components/governance/RevealRequestForm.tsx` 期望 ≥ 3 | FR-033 |
| AC-33.4 | 缺 reason 或 reason < 20 chars → 422 | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_reveal_request_short_reason_rejected -v` | FR-033 |
| AC-33.5 | reveal 完成显示 masked content,audit event 必先写 (顺序) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_reveal_writes_audit_before_returning_content -v` | FR-033 + FR-034 |
| AC-34.1 | 后端 audit 事件 11 类齐全: replay_triggered / diff_computed / tag_added / tag_removed / incident_status_changed / incident_comment_added / badcase_status_changed / badcase_escalated / sensitive_reveal / export / review_snapshot (US1+US4+US6 累计 11) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_audit_event_taxonomy_eleven_actions -v` (frozenset 长度 == 11) | FR-034 + SC-009 |
| AC-34.2 | 前端 Audit Log viewer (Governance workspace) 显示 audit event list 含 actor / timestamp / target / action / reason / result / visibility_mode 7 字段 | `grep -c "actor\|timestamp\|target\|action\|reason\|result\|visibility" src/admin/components/governance/AuditLogViewer.tsx` 期望 ≥ 7 | FR-034 |
| AC-34.3 | audit log UI 无 delete 按钮 | `grep -c "delete\|Delete\|onDelete" src/admin/components/governance/AuditLogViewer.tsx` 期望 0 | FR-034 |
| AC-34.4 | SC-009: 100% 11 类敏感操作 → audit 事件必有 actor / target / action / time / result + reason (where required) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_all_eleven_actions_emit_audit_event -v` (驱动各 action helper,验证 in-memory buffer 收到) | SC-009 |
| AC-35.1 | 后端 `POST /api/v1/admin-console/governance/exports` payload: {workspace, filters, format (json\|csv\|markdown)};response: {export_id, download_url, expires_at, fields_included, fields_redacted, freshness_warnings} | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_export_response_has_six_fields -v` | FR-035 |
| AC-35.2 | 前端 Export form 含 format selector + filter picker + generate | `grep -c "format-selector\|filter-picker\|generate\|csv\|markdown" src/admin/components/governance/ExportForm.tsx` 期望 ≥ 4 | FR-035 |
| AC-35.3 | export 必含 audit metadata: actor / timestamp / filters / fields_included (白名单) / fields_redacted (脱敏清单) / redaction_state | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_export_payload_includes_audit_metadata -v` | FR-035 + FR-034 |
| AC-35.4 | 不在白名单的 raw_* 字段强制 redact,export payload 不含 | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_export_strips_raw_fields -v` | FR-032 + FR-035 |
| AC-35.5 | export 自身触发 audit event (FR-034 11 类第 10 类 "export") | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_export_triggers_audit_event -v` | FR-035 + FR-034 |
| AC-36.1 | 后端 `GET /api/v1/admin-console/governance/retention-policy` 返回 {workspace_field, retention_days, action (block\|warn\|redact), last_reconciled_at} | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_get_retention_policy_envelope -v` | FR-036 |
| AC-36.2 | 后端 `PUT /api/v1/admin-console/governance/retention-policy` 更新策略 (audit logged) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_update_retention_policy_audit_logged -v` | FR-036 + FR-034 |
| AC-36.3 | 超过 retention window → backend response 字段返回 null + "expired" tag | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_expired_payload_returns_null_with_tag -v` | FR-036 |
| AC-36.4 | 前端 retention policy editor + retention status board (per workspace field) | `grep -c "retention-policy-editor\|retention-status\|workspace-field" src/admin/components/governance/RetentionPolicyEditor.tsx` 期望 ≥ 3 | FR-036 |
| SC-8.1 | pytest 验证 5 role × 8 workspace 矩阵,viewer 在 governance workspace 必须 403 | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_rbac_matrix_5role_x_8workspace -v` (parametrize 40 case) | SC-008 |
| SC-9.1 | pytest 验证 11 类事件全部触发 audit 后写入 in-memory buffer | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_all_eleven_actions_emit_audit_event -v` | SC-009 |
| SC-10.1 | grep `raw_resume\|raw_prompt\|raw_model_output` 在 `src/admin/pages/` + `src/admin/components/governance/` 必须 0 业务命中 (AC-32.1 重复校验) | 同 AC-32.1 | SC-010 |
| SC-11.1 | 前端 QualityFlagsBadge 5 状态视觉区分: valid_zero=绿, missing=灰, partial=黄, stale=橙, failed=红 | `grep -c "valid_zero\|missing\|partial\|stale\|failed" src/admin/components/governance/QualityFlagsBadge.tsx` 期望 ≥ 5 | SC-011 + FR-028 |
| SC-11.2 | backend response 必含 `data_status` 字段 5 档枚举 (valid_zero / missing / partial / stale / failed) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_data_status_enum_five_values -v` | SC-011 + FR-028 |
| EC-1 | reveal 拒后用户已开 trace → 整个 trace drawer 关闭 + "access denied" 全屏 (前端) | `grep -c "access-denied-fullscreen\|onRevealDenied" src/admin/components/governance/RevealRequestForm.tsx` 期望 ≥ 2 | Edge Cases line 330 |
| EC-2 | export period 含 expired → export 拒 + 列出 expired records 列表 | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_export_rejects_when_period_contains_expired -v` | Edge Cases line 332 |
| EC-3 | retention policy 改 → 已在缓存的 sensitive content 不再被服务 (cache invalidation) | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_retention_policy_change_invalidates_cache -v` | Edge Cases (inferred) + FR-036 |
| EC-4 | governance setting 改 → 自身 audit event (US6 self-audit, FR-034 11 类第 11 类 "governance_change") | `cd backend && uv run pytest tests/contract/test_044_governance.py::test_governance_change_self_audit -v` | FR-034 |

## 起草说明 (写给 tester)

### 设计意图

- US6 范围 = FR-031~FR-036 (governance / privacy / audit) + SC-008/009/010/011 + Edge Cases 4 类 (reveal deny 后 trace 关闭 / export 含 expired / retention 改 → cache invalidation / governance self-audit)。
- 后端模块路径: `backend/app/modules/admin_console/governance/` (独立子目录,沿 US1/2/3/4 子模块 pattern)。
- 数据源 = seed-driven (in-memory buffer + 静态 seed): access matrix 5×8×6 + reveal requests + audit events + retention policies。
- 真实 governance DB / 真实 redaction enforcement / 真实 retention enforcement = `[CROSS-TEAM-DEBT]` Phase 2 batch 5:US6 仅交付 governance surface + 类型契约 + seed 数据 + in-memory audit buffer。
- 复用 baseline (heavy reuse, 不动):
  - `backend/app/modules/admin_console/audit.py` (US1+US4 扩 8 类 → US6 扩 11 类,in-memory buffer + DB no-op helper)
  - `backend/app/modules/admin_console/auth.py` (US6 加 RBAC_VIEW / SENSITIVE_REVEAL / AUDIT_VIEW / EXPORT / GOVERNANCE_VIEW / GOVERNANCE_CHANGE tokens)
  - `backend/app/modules/telemetry_contracts/retention_cli.py` (READ ONLY,US6 只 import retention enforcement interface 作为 policy-binding hint,不在 US6 阶段实现真 retention scheduler)
  - `backend/app/modules/telemetry_contracts/redaction_cli.py` (READ ONLY)
  - `backend/app/modules/admin_console/decision_signals/` + `product_analytics/` + `ai_operations/` + `incidents/` — 已有 seed pattern

### 数据契约 (类型 / Literal 锁定)

```python
# FR-031 capability matrix
CapabilityToken = Literal[
    "READ",          # workspace view
    "WRITE",         # create / mutate
    "CHANGE",        # status / config change
    "EXPORT",        # export generate
    "REVEAL",        # sensitive reveal (with audit)
    "AUDIT",         # audit log read
]
WorkspaceId = Literal[
    "command-center",
    "product-analytics",
    "ai-operations",
    "incidents-badcases",
    "logs-and-traces",
    "users-accounts",
    "reports",
    "governance",
]
ConsoleRole = Literal["pm", "operations", "maintainer", "reviewer", "owner"]

# FR-032 user privacy safe (no raw_*)
class UserPrivacySafe(BaseModel):
    user_id: str
    display_name: Optional[str]  # masked
    email: Optional[str]         # masked
    raw_resume: Optional[str]    # ALWAYS None — privacy-safe
    raw_interview_answer: Optional[str]  # ALWAYS None
    # ... 8 safe fields total
    data_status: Literal["valid_zero", "missing", "partial", "stale", "failed"]
    visibility_mode: Literal["hidden", "masked", "full"]

# FR-033 reveal request
class RevealRequest(BaseModel):
    target_type: Literal["user_resume", "user_interview", "ai_prompt", "ai_model_output", "incident_payload"]
    target_id: str
    reason: str = Field(min_length=20, max_length=2000)

# FR-034 audit event (11 categories — US1+US4+US6)
AuditAction = Literal[
    "replay_triggered",      # US1
    "diff_computed",         # US1
    "tag_added",             # US1
    "tag_removed",           # US1
    "incident_status_changed",       # US4
    "incident_comment_added",        # US4
    "badcase_status_changed",        # US4
    "badcase_escalated",             # US4
    "sensitive_reveal",       # US6 NEW
    "export",                # US6 NEW
    "review_snapshot",       # US6 NEW (governance_change subsumes 11th)
]
# NOTE: review_snapshot reserved for Phase 2 reports US7;US6 enforces the
# count = 11 via Literal size assertion. Implementation: 10 active +
# review_snapshot in taxonomy (literal size 11 = contract).

# FR-035 export
ExportFormat = Literal["json", "csv", "markdown"]
class ExportRequest(BaseModel):
    workspace: WorkspaceId
    filters: dict[str, Any]
    format: ExportFormat

# FR-036 retention
RetentionAction = Literal["block", "warn", "redact"]
class RetentionPolicy(BaseModel):
    workspace_field: WorkspaceId  # which workspace
    retention_days: int = Field(ge=1, le=3650)
    action: RetentionAction
    last_reconciled_at: str
```

### Critical Edge Case Bindings (锁给 dev)

- EC-1 (reveal 后 trace 关闭): audit write MUST happen before content reveal;前端 `FieldPermissionBadge` 在 `visibility_mode="hidden"` 时显示 "access denied fullscreen" 占位。
- EC-2 (export 含 expired): service 必须在 `fields_redacted` 数组中列出 expired record ids;200 response 带 `expired_record_ids` 数组。
- EC-3 (retention 改 → cache invalidation): `_RETENTION_CACHE` (in-memory dict keyed by workspace_field) MUST be cleared on `PUT retention-policy`;下一次 GET 必重新 seed + audit event。
- EC-4 (governance self-audit): PUT retention-policy handler MUST 调用 `_write_audit_unsafe(action="review_snapshot", target_kind="governance")` (US6 自审计)。

### Critical Capability Token Bindings (锁给 dev)

```python
# 新增 6 capability tokens (FR-031/033/034/035/036):
RBAC_VIEW = "RBAC_VIEW"             # GET /access-matrix (FR-031)
SENSITIVE_REVEAL = "SENSITIVE_REVEAL"  # POST /reveal-requests (FR-033)
AUDIT_VIEW = "AUDIT_VIEW"           # GET /audit-events + /reveal-requests list (FR-034)
EXPORT = "EXPORT"                    # POST /exports (FR-035)
GOVERNANCE_VIEW = "GOVERNANCE_VIEW"  # GET /retention-policy (FR-036)
GOVERNANCE_CHANGE = "GOVERNANCE_CHANGE"  # PUT /retention-policy (FR-036, EC-4)

# role grants (per FR-031 least-privilege):
# - admin / owner: 全部 6
# - pm: GOVERNANCE_VIEW (只读), AUDIT_VIEW
# - operations: AUDIT_VIEW
# - reviewer: AUDIT_VIEW
# - maintainer: AUDIT_VIEW + EXPORT
# - viewer: AUDIT_VIEW (合规 baseline)
```

### Critical Hidden-Raw Guard Bindings (锁给 dev, SC-010)

- backend `UserPrivacySafe` schema 必须 Pydantic Literal field set 校验;test asserts `set(UserPrivacySafe.model_fields.keys())` 不包含 raw_*。
- 前端 grep `raw_resume\|raw_prompt\|raw_model_output\|raw_interview_answer` 在 `src/admin/pages/` + `src/admin/components/governance/` 必须 0 业务命中。
- export payload `fields_redacted` 必须包含 raw_* 字段名 (即使 attempt reveal 也是 redacted)。

### 不在本 US 范围

- 真实 governance DB (Phase 2 batch 5):[CROSS-TEAM-DEBT]
- 真实 redaction enforcement (Phase 2 batch 5):[CROSS-TEAM-DEBT]
- 真实 retention scheduler (Phase 2 batch 5):[CROSS-TEAM-DEBT]
- review_snapshot action helper 实现 (FR-030 reports US7 实施,US6 仅占位审计 helper)

### 起草说明 (写给 dev)

- 实施顺序: backend (schemas → repository seed → service → api) → backend audit.py 扩 + auth.py 扩 → pytest 18+ → frontend types/api/hooks/components/page → vitest → e2e → typecheck + build → commit。
- 必读 lessons: `req_044_us1_seed_pattern.md` + `req_044_us4_seed_pattern.md` (路径) 以沿种子 pattern。
- US6 **第 11 类 audit action 是** `review_snapshot`(FR-034 11 类包含 snapshot generation);governance_change 自身审计复用 `sensitive_reveal` action + 不同 target_kind OR 加第 11 个 action `governance_change`。**最终选择** = 第 11 个 action `review_snapshot`(贴近 spec FR-034 字面"admin access / saved-view / incident / badcase / sensitive reveal / export / snapshot / governance change" — 8 类,但 US1/4 已累计 8 类,US6 加 sensitive_reveal + export + governance_change = 11 类锁定)。**说明给 tester**:Literal size 必须 = 11,与 spec FR-034 8 类不同 (因 spec 类别按主题,US1-6 实现按 token;两边均正确)。**冲突以 US6 AC 为准** (= 11)。

