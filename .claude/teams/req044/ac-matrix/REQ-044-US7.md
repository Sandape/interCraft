---
req_id: REQ-044-US7
status: locked
locked_at: 2026-07-04
locked_by: dev-implement
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-044-US7 — Review Snapshots + Metric Trust (FR-027~FR-030)

## SC Gaps

- 无。spec.md US7 (line 289-313) + SC-012 (line 514-516) + Edge Cases 4 类
  (late-arriving data frozen vs live, cohort definition changed,
  export 含 expired → snapshot 拒 + 列 expired, backend 不可达 → 不静默吞错)
  全部覆盖。
- spec US7 line 304-307: snapshot 含 filters + metric definitions + values +
  comparison deltas + freshness + quality flags + annotations + privacy-safe
  evidence links = 8 字段锁定。
- spec US7 line 311-313: frozen snapshot values vs current live values 区分 =
  FR-030 (AC-30.1/30.2/30.3 + snapshot immutable = AC-30.4)。
- spec Edge Cases line 321: cohort definition changes after snapshot →
  snapshot viewer 显示 "cohort definition changed since snapshot" 警告 (EC-2)。
- spec Edge Cases line 332: export period 含 expired → snapshot 拒 + 列
  expired records (EC-3,同 US6 export blocked 语义)。
- spec FR-027: 10 字段 = definition / owner / source / numerator / denominator
  / unit / period / freshness / completeness / quality flags (SC-004 / AC-27.1/27.2)。
- spec FR-028 + SC-011: 5 状态 (valid_zero / missing / partial / stale /
  failed) 视觉区分 = US6 QualityFlagsBadge 已实现 + DataStatus Literal (复用)。

## AC 矩阵

| AC-ID | 描述 | 验证方式 (命令/测试名/可观测指标) | 来源 (spec) |
|-------|------|-----------------------------------|-------------|
| AC-27.1 | 前端 `MetricTooltip` 组件 (US7 新建) 展示 10 字段: definition / owner / source / numerator / denominator / unit / period / freshness / completeness / quality_flags | `grep -c "definition\|owner\|source\|numerator\|denominator\|unit\|period\|freshness\|completeness\|quality_flags" src/admin/components/reports/MetricTooltip.tsx` 期望 ≥ 10 | FR-027 |
| AC-27.2 | 后端 `MetricDefinition` schema (Pydantic) + 前端 `MetricDefinition` type 10 字段字面声明,backend 通过 `_assert_metric_def_no_missing` contract test | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_metric_definition_schema_has_ten_fields -v` | FR-027 + SC-004 |
| AC-27.3 | workspace 中所有 chart tooltip 必含 MetricDefinition 10 字段 (US1 decision signal + US2 funnel + US3 KPI 至少 3 处 reference) | `grep -rn "MetricTooltip\|metric_tooltip\|metricDefinition" src/admin/components/decision-signals/ src/admin/components/product-analytics/ src/admin/components/ai-operations/ 2>/dev/null` 期望 ≥ 3 处 import | FR-027 |
| AC-27.4 | 缺字段 → 显示 "(not provided)" 不静默通过 (`_NOT_PROVIDED` Literal sentry) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_metric_definition_missing_fields_render_as_not_provided -v` | FR-027 + Edge Cases |
| AC-28.1 | `QualityFlagsBadge` 组件 (US6 已建) 接受 5 状态枚举 + 视觉区分 (valid_zero=绿, missing=灰, partial=黄, stale=橙, failed=红) | `grep -c "valid_zero\|missing\|partial\|stale\|failed" src/admin/components/governance/QualityFlagsBadge.tsx` 期望 ≥ 5 | FR-028 + SC-011 |
| AC-28.2 | 后端 `data_status` Pydantic Literal 5 状态 (与 US6 DataStatus 同步) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_data_status_enum_five_values -v` | FR-028 + SC-011 |
| AC-28.3 | snapshot frozen_values 每条必显式 data_status badge + workspace metric 也显示 | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_frozen_values_include_data_status -v` | FR-028 |
| AC-29.1 | 后端 `POST /api/v1/admin-console/review-snapshots` payload: {workspace, filters, comparison_period, annotations};response: {snapshot_id, generated_at, frozen_values[], comparison_deltas[], metric_definitions[], freshness_warnings[], quality_flags{}, evidence_links[]} | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_response_has_eight_fields -v` | FR-029 + SC-012 |
| AC-29.2 | snapshot 自身必含 audit event (FR-034 第 11 类 `review_snapshot` 已就位;US7 复用 `log_governance_change` + 新 helper `log_snapshot_generated`) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_generation_writes_audit_event -v` | FR-029 + FR-034 |
| AC-29.3 | snapshot payload 字段 whitelist (US6 EXPORT_FIELDS_INCLUDED 复用) + 任何 raw 字段强制 redact (`EXPORT_FIELDS_REDACTED` 4 raw_* 必含) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_strips_raw_fields -v` | FR-029 + FR-032 + SC-010 |
| AC-29.4 | snapshot 文件 (markdown / json) 导出路径由 US6 `GET /governance/exports/{export_id}/download` 提供 (US7 不新建 download 端点,沿用 US6 export-as-snapshot 模式) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_download_url_is_export_route -v` | FR-029 + FR-035 |
| AC-29.5 | 前端 `SnapshotGenerateForm` 含 workspace selector + filter picker + annotations textarea + format selector (json/markdown) | `grep -c "workspace-selector\|filter-picker\|annotations\|format-selector" src/admin/components/reports/SnapshotGenerateForm.tsx` 期望 ≥ 4 | FR-029 |
| AC-30.1 | 后端 `GET /api/v1/admin-console/review-snapshots/{id}` 返回 frozen_values 与 current_values 双字段 (后者从 latest seed metric snapshot 取) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_get_returns_frozen_and_current -v` | FR-030 |
| AC-30.2 | 前端 `SnapshotViewer` 显示两列对比: "Frozen at <timestamp>" vs "Current (live, as of <now>)" | `grep -c "frozen-at\|current-live\|FrozenValueTable\|CurrentValueTable" src/admin/components/reports/SnapshotViewer.tsx` 期望 ≥ 3 | FR-030 |
| AC-30.3 | current value 与 frozen value 不同时显示 "Delta: X%" 提示 (late-arriving data 警告) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_delta_computed_when_current_differs -v` + `grep -c "delta\|Delta\|late-arriving" src/admin/components/reports/DeltaIndicator.tsx` 期望 ≥ 3 | FR-030 + EC-1 |
| AC-30.4 | snapshot 自身不可变 (immutable),API 拒 PUT/PATCH/DELETE (返回 405) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_immutable_rejects_mutation_with_405 -v` | FR-030 + 铁律 A |
| SC-12.1 | pytest 验证 snapshot POST response 8 字段 (frozen_values / comparison_deltas / metric_definitions / freshness_warnings / quality_flags / evidence_links / filters / annotations) 全部非空 | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_post_response_eight_fields_all_populated -v` | SC-012 |
| EC-1 | metric 后期因 late-arriving data 变化 → snapshot viewer 显式 "Frozen vs Live delta" 警告 | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_late_arriving_data_warning_emitted -v` | Edge Cases line 326 + FR-030 |
| EC-2 | cohort definition 改后 → snapshot 显示 "cohort definition changed since snapshot" 警告 | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_cohort_definition_changed_warning -v` | Edge Cases line 321 + FR-029 |
| EC-3 | snapshot generate 含 expired sensitive payloads → snapshot 拒生成 + 列出 expired records (复用 US6 EC-2 export blocked 语义) | `cd backend && uv run pytest tests/contract/test_044_review_snapshots.py::test_snapshot_rejects_expired_payloads -v` | Edge Cases line 332 + FR-035 |
| EC-4 | snapshot generate 时 backend 不可达 → 前端显示 "snapshot failed, retry" 不被静默吞错 | `grep -c "snapshot-failed\|snapshot-failed-retry\|retry" src/admin/components/reports/SnapshotViewer.tsx` 期望 ≥ 2 | Edge Cases (inferred) + FR-029 |

## 起草说明 (写给 tester)

### 设计意图

- US7 范围 = FR-027 (10 字段 metric tooltip) + FR-028 (5 状态视觉) +
  FR-029 (review snapshot 含 8 类元数据) + FR-030 (frozen vs live 区分)
  + SC-012 + Edge Cases 4 类 (late-arriving / cohort changed / expired /
  backend unreachable)。
- 后端模块路径: `backend/app/modules/admin_console/review_snapshots/`
  (独立子目录,沿 US1/2/3/4/6 子模块 pattern)。
- 数据源 = seed-driven (in-memory buffer + 静态 seed): 3 demo snapshot
  (含 frozen + current 不一致的 delta 警告示例,模拟 late-arriving data)
  + 4 MetricDefinition 10 字段全部声明 + 5 状态 visual badge 复用 US6。
- 真实 snapshot DB / real-time metric recompute / real-time cohort change
  detector = `[CROSS-TEAM-DEBT]` Phase 2 batch 5:US7 仅交付 surface +
  类型契约 + seed 数据 + in-memory buffer + immutable 405 守卫。
- 复用 baseline (heavy reuse, 不动):
  - `backend/app/modules/admin_console/governance/schemas.py` —
    `DataStatus` Literal + `AuditAction` Literal + `VisibilityMode`
    + `WorkspaceId` (US7 同步 `reports` workspace + 5 状态 + 11 类审计)。
  - `backend/app/modules/admin_console/audit.py` — `log_governance_change`
    + `log_export` (US7 复用 `review_snapshot` action + 加 `log_snapshot_generated` 包装)。
  - `backend/app/modules/admin_console/auth.py` — US7 新加 `REVIEW_SNAPSHOT`
    token (与 US6 `REVEAL/EXPORT/GOVERNANCE_*` 对齐 least-privilege)。
  - `backend/app/modules/admin_console/governance/repository.py` —
    `next_audit_event_id` + `append_audit_event` + `EXPORT_FIELDS_REDACTED`
    (US7 复用 raw_* 强制 redact 逻辑)。
  - `backend/app/modules/telemetry_contracts/metrics.py` —
    `MetricDefinition` (US7 扩 10 字段 via wrapper,不动 dataclass)。
  - `backend/app/modules/telemetry_contracts/redaction_cli.py` —
    `audit_samples` + `REDACTED_PLACEHOLDER` (US7 复用,READ ONLY)。
  - `src/admin/components/governance/QualityFlagsBadge.tsx` — US7 复用
    5 状态 badge (US6 已建,不重写)。
  - `src/admin/components/governance/DataStatusIndicator.tsx` — US7
    复用 US6 已建组件。
  - 已有子模块 decision_signals/product_analytics/ai_operations/incidents/
    governance — US7 不重写,只 import 类型 + 间接通过 MetricTooltip
    tooltip pointer 引用 (AC-27.3 ≥ 3 处 import 锁)。

### 数据契约 (类型 / Literal 锁定)

```python
# FR-027 — MetricDefinition 10 fields
class MetricDefinition10Field(BaseModel):
    metric_id: str
    name: str
    definition: str                       # FR-027 #1
    owner: str                            # FR-027 #2
    source: str                           # FR-027 #3
    numerator: str                        # FR-027 #4
    denominator: str                      # FR-027 #5
    unit: str                             # FR-027 #6
    period: str                           # FR-027 #7
    freshness: str                        # FR-027 #8
    completeness: str                     # FR-027 #9
    quality_flags: DataStatus             # FR-027 #10 (复用 US6 5 状态)
    # AC-27.4: missing fields render as "(not provided)" literal
    _NOT_PROVIDED: Literal["(not provided)"] = "(not provided)"

# FR-029 — Review snapshot
class FrozenValue(BaseModel):
    metric_id: str
    value: float
    unit: str
    captured_at: str          # ISO timestamp (snapshot frozen time)
    data_status: DataStatus   # FR-028 + AC-28.3

class CurrentValue(BaseModel):
    metric_id: str
    value: float
    unit: str
    captured_at: str          # ISO timestamp (live now)
    data_status: DataStatus

class ComparisonDelta(BaseModel):
    metric_id: str
    delta_pct: float          # current vs prior period (baseline)
    period: str

class EvidenceLink(BaseModel):
    label: str                # human-readable, NEVER raw payload
    kind: Literal["incident", "trace", "ai_task", "badcase", "export"]
    target_id: str

class ReviewSnapshotRequest(BaseModel):
    workspace: WorkspaceId
    filters: dict[str, Any]
    comparison_period: str    # "vs prior week" / "vs prior month" etc.
    annotations: str = Field(min_length=0, max_length=4000)
    format: Literal["json", "markdown"] = "json"

class ReviewSnapshotResponse(BaseModel):
    snapshot_id: str
    workspace: WorkspaceId
    generated_at: str
    generated_by: str
    filters: dict[str, Any]
    frozen_values: list[FrozenValue]              # SC-012 + AC-29.1
    comparison_deltas: list[ComparisonDelta]       # SC-012 + AC-29.1
    metric_definitions: list[MetricDefinition10Field]  # SC-012 + AC-29.1
    freshness_warnings: list[str]                  # SC-012 + AC-29.1
    quality_flags: dict[str, DataStatus]           # SC-012 + AC-29.1
    annotations: str                               # SC-012 + AC-29.1
    evidence_links: list[EvidenceLink]             # SC-012 + AC-29.1 (privacy-safe)
    cohort_definition_changed: bool                # EC-2
    late_arriving_warnings: list[str]              # EC-1
    download_url: str                              # AC-29.4 (US6 export route)
    expires_at: str
    data_status: DataStatus

class ReviewSnapshotListResponse(BaseModel):
    snapshots: list[ReviewSnapshotResponse]
    total: int
    data_status: DataStatus
```

### Critical Edge Case Bindings (锁给 dev)

- **EC-1** (late-arriving data): `current_values[i].value != frozen_values[i].value`
  → `late_arriving_warnings.append(f"{metric_id} changed by {delta_pct:.1f}% since snapshot")`,
  `comparison_deltas[i].delta_pct` 必填,前端 `DeltaIndicator` 必显。
- **EC-2** (cohort definition changed): seed helper `seed_demo_cohort_versions()`
  返回 `{cohort_name: version_int}` map;生成 snapshot 时 record current
  cohort_version;viewer GET 时再次取 current version → 不等时
  `cohort_definition_changed=True` + warning 必填。
- **EC-3** (expired payloads): `filters.expired_record_ids` 非空列表 →
  service 抛 `SnapshotBlockedError` → API 422 + `expired_record_ids`
  (与 US6 `ExportBlockedError` 镜像,字段名相同以便前端复用)。
- **EC-4** (backend unreachable): API 层捕获 `httpx.ConnectError` /
  `redis.ConnectionError` → 返回 503 + `{"error":"SNAPSHOT_FAILED",
  "message":"snapshot failed, retry"}`,前端 `SnapshotViewer` 渲染
  `snapshot-failed-retry` testid。

### Critical Capability Token Bindings (锁给 dev)

```python
# 新增 1 capability token (FR-029):
REVIEW_SNAPSHOT = "REVIEW_SNAPSHOT"   # POST + GET review-snapshots

# role grants (per FR-031 least-privilege + US7 PM 是主要 audience):
# - admin / owner: REVIEW_SNAPSHOT
# - pm: REVIEW_SNAPSHOT (FR-029 主要 use case)
# - operations: REVIEW_SNAPSHOT (read-only GET)
# - maintainer: REVIEW_SNAPSHOT (支持导出 reproduce)
# - reviewer: 无 (reviewer 不需要自己生成)
# - viewer: 无 (FR-031 least-privilege)
```

### Critical FR-032 Guard Bindings (锁给 dev)

- snapshot payload `evidence_links[].label` 必不含 raw_resume /
  raw_interview_answer / raw_prompt / raw_model_output 字面。
- snapshot payload `frozen_values[].value` 为 metric scalar number,
  无 raw payload。
- contract test asserts `snapshot_response.evidence_links` 经
  `audit_samples(..., environment="production")` 不触发
  `PolicyViolation`。
- 前端 grep `raw_resume\|raw_prompt\|raw_model_output\|raw_interview_answer`
  在 `src/admin/components/reports/` 必须 0 业务命中 (US6 SC-10.1 模式复用)。

### Critical Immutable Guard Bindings (锁给 dev, AC-30.4)

- `app.include_router(review_snapshots_router, ...)` 后,显式注册
  `PUT` / `PATCH` / `DELETE` 405 端点 (method_not_allowed 实现:
  `@router.put("/{snapshot_id}", status_code=405)` body 返
  `{"error":"SNAPSHOT_IMMUTABLE", "message":"snapshots are immutable"}`)。
- service 层 `_assert_snapshot_immutable(snapshot_id)` 在 PUT/PATCH/DELETE
  handler 首行调用 → 抛 `SnapshotImmutableError` → API 405。
- contract test asserts:
  ```python
  def test_snapshot_immutable_rejects_mutation_with_405():
      app = _app()
      schema = app.openapi()
      for method in ["put", "patch", "delete"]:
          path = schema["paths"]["/api/v1/admin-console/review-snapshots/{snapshot_id}"]
          assert str(path[method]["x-405"]) == "snapshot immutable"
  ```

### 不在本 US 范围

- 真实 review_snapshot DB (Phase 2 batch 5):[CROSS-TEAM-DEBT]
- 真实 late-arriving data 实时计算 (Phase 2 batch 5):[CROSS-TEAM-DEBT]
- 真实 cohort definition 变更探测 (Phase 2 batch 5):[CROSS-TEAM-DEBT]
- snapshot schedule / cron / auto-generate (Phase 2 batch 5):[CROSS-TEAM-DEBT]
- snapshot diff between two snapshots (Phase 2 batch 6):[CROSS-TEAM-DEBT]

### 起草说明 (写给 dev)

- 实施顺序: backend (schemas → repository seed → service → api) →
  backend audit.py 扩 (log_snapshot_generated) + auth.py 扩
  (REVIEW_SNAPSHOT token) → pytest 18+ → frontend types/api/components/page →
  vitest → e2e → typecheck + build → commit。
- 必读 lessons: `req_044_us3_seed_pattern.md` (路径) + `req_044_us6`
  governance seed pattern。
- US7 `data_status` 5 状态必须与 US6 governance `DataStatus` Literal
  同步 (= valid_zero / missing / partial / stale / failed),不要新增
  新值。统一 import US6 `DataStatus` 不要在 US7 schemas 重复声明。
- US7 `evidence_links[].label` 必为 human-readable summary,严禁存
  raw payload (FR-032 + SC-010 守卫)。
- US7 mutation 405 守卫必须 explicit endpoint (不能依赖 FastAPI 自动
 405,需要带 SNAPSHOT_IMMUTABLE error code + audit_event_id,便于
 governance 追溯)。