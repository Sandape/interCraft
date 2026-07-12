# Contract: Calibrate Decision (REQ-063)

**Owner**: `backend/app/modules/resume_derive/calibrate_decision.py`
**Caller**: `agents/nodes/resume_derive/calibrate_pages.py`

## Purpose

Deterministic policy: given target pages + latest `PageMeasureResult`, choose spacing vs Agent vs guidance vs Bad Case — **no LLM inside this function**.

## Input

| Field | Notes |
|---|---|
| `target` | 1 \| 2 \| 3 |
| `measured` | from PageMeasureResult.page_count |
| `last_page_fill_ratio` | from measure |
| `line_height` | current |
| `line_height_floor` / `line_height_ceil` | readable band |
| `rounds_used` / `max_rounds` | default max 5 |
| `sparse_threshold` | default 1/3 |
| `comfort_threshold` | default 2/3 |
| `can_prune` / `can_expand` | material availability flags from prior nodes |

## Output

| Field | Notes |
|---|---|
| `action` | `pass` \| `tighten_line_height` \| `adjust_line_height_for_fill` \| `agent_prune` \| `agent_expand` \| `needs_guidance` |
| `record_bad_case` | bool |
| `bad_case_kind` | `budget_underestimate` \| null |
| `reason` | stable code for logs/tests |

## Normative decision table

See [research.md R2](../research.md). Unit tests MUST encode at least:

1. target=1, measured=2, fill=0.25 → `tighten_line_height` (first)
2. same after floor exhausted → `agent_prune`
3. target=2, measured=2, fill=0.70 → `pass`
4. target=2, measured=2, fill=0.50 → `adjust_line_height_for_fill` then `agent_expand`
5. target=2, measured=2, fill=0.20 → `agent_expand` + `record_bad_case`
6. target=3, measured=1 → `agent_expand`
7. max rounds → `needs_guidance`

## Agent hooks (when action is prune/expand)

- Must run existing source validation before persist
- Must re-measure after mutation
- Must not fabricate facts to chase fill ratio
