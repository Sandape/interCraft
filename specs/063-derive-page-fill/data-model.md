# Data Model: REQ-063 派生满页校准

**Date**: 2026-07-12
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Existing entities (unchanged identity)

### `resumes_v2` (derived rows)

| Field | Change |
|---|---|
| `target_page_count` | 不变；∈ {1,2,3} |
| `actual_page_count` | **语义变更**：必须来自真实测量或保存回写的预览/PDF 页数，不得来自字符估算 |
| `derive_meta.page_report` | **形状扩展**（见下） |
| `data.metadata.markdown.pageCount` | 与预览同步；保存时与 `actual_page_count` 对齐 |

### `resume_derive_runs`

| Field | Change |
|---|---|
| `artifacts.page_report` | 扩展为权威校准报告 |
| `calibrate_round` | 继续 0..max（≤5） |
| `status` | `succeeded` 仅当页数=目标且充实门禁通过；否则 `needs_guidance` / `failed` |

## PageMeasureResult (logical)

| Field | Type | Rules |
|---|---|---|
| `page_count` | int ≥ 1 | 真实分页页数 |
| `last_page_fill_ratio` | float (0,1] | `last_used_px / page_content_px` |
| `pages[]` | optional | `{ page_number, used_px, fill_ratio }`；前 N−1 页 fill 视为 1.0 |
| `line_height` | int | 本次测量所用行距 |
| `theme_id` | string | 主题 |
| `measure_version` | string | 测量脚本/算法版本，便于复盘 |

## page_report (logical JSON)

```text
{
  target: 1|2|3,
  measured: int,
  last_page_fill_ratio: float,
  line_height: int,
  comfort_threshold: float,   # default 0.666...
  sparse_threshold: float,    # default 0.333...
  rounds: int,
  strategies: string[],       # e.g. tighten_line_height, agent_prune, agent_expand
  decision: string,           # final decide_calibrate_action
  decisions: { round, action, measure }[],
  bad_case_ref: uuid | null,
  measure_version: string
}
```

### Validation

- `succeeded` ⇒ `measured == target` AND `last_page_fill_ratio >= comfort_threshold`
- `needs_guidance` ⇒ 可有 `measured != target` 或 fill 不达标；`actual_page_count` 仍存真实 `measured`
- 禁止：`status=succeeded` 且 `measured != target`

## CalibrateDecision (logical)

| Field | Values |
|---|---|
| `action` | `pass` \| `tighten_line_height` \| `adjust_line_height_for_fill` \| `agent_prune` \| `agent_expand` \| `needs_guidance` |
| `record_bad_case` | bool |
| `bad_case_kind` | `budget_underestimate` \| null |
| `reason` | short machine-readable code |

## `resume_page_bad_cases` (new)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid | RLS / tenant |
| `run_id` | uuid | FK → resume_derive_runs |
| `derived_resume_id` | uuid nullable | 落库后可填 |
| `kind` | text | e.g. `budget_underestimate` |
| `target_page_count` | smallint | |
| `measured_page_count` | smallint | |
| `last_page_fill_ratio` | numeric | |
| `theme_id` | text | |
| `decision` | text | |
| `outcome` | text | `expanded` \| `needs_guidance` \| `succeeded_after_expand` \| … |
| `payload` | jsonb | optional extra measure snapshot |
| `created_at` | timestamptz | |

**Deletion**: 随用户删除或简历删除策略级联/清理（继承平台用户数据生命周期）。

## State transitions (calibrate)

```text
draft_ready
  → measure
  → decide
      → pass → succeeded (if fill ok)
      → tighten/adjust line height → re-measure → decide
      → agent_prune / agent_expand → validate_sources → re-measure → decide
      → needs_guidance (terminal for auto loop)
  → (max rounds) needs_guidance
```

## Compatibility

- 旧派生行无 fill 字段：打开后以当前预览为准；**保存时**回写 `actual_page_count`。
- 旧 `page_report.measured` 若来自字符估算：新运行覆盖；列表以 DB `actual_page_count` 为准直到用户保存刷新。
