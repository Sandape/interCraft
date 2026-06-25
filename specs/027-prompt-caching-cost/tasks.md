# Tasks: Prompt Caching & Token Cost Engineering

**Input**: Design documents from `/specs/027-prompt-caching-cost/`

**Prerequisites**: plan.md, spec.md

**Tests**: Tests are included (Constitution III TDD). Each implementation phase
has test tasks first.

**Organization**: Tasks grouped by user story. **本次仅实现 US1 + cache hit
observability**；US2 / US3 / US4 任务列出但标记 ⏳ 后续。

**Partial Scope**: 见 plan.md "Partial Scope Justification" 节。本次实现范围
= US1 prompt 分层 + cache hit observability 自包含库 + 专项测试；LLMClient
集成点 + interview graph 集成点留 working tree（⏳，跟随 024 落地）。

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline + create directory structure.

- [X] T001 [P] Verify backend tests green: `cd backend && uv run pytest -q`
  (716 passed baseline after 031)
- [X] T002 [P] Create `backend/app/agents/prompt_caching/__init__.py` (empty
  package marker)
- [X] T003 [P] Create `backend/tests/unit/test_prompt_caching.py` placeholder

---

## Phase 2: Foundational (Prompt Caching Library — BLOCKS US1 Integration)

**Purpose**: Build the prompt_caching self-contained library. This is the
library that LLMClient + 5 graphs will import (integration point ⏳ working
tree).

**⚠️ CRITICAL**: No US1 integration work can begin until this phase is complete.

### Tests for Foundational (TDD)

- [X] T010 [P] [US1] Unit test `backend/tests/unit/test_prompt_caching.py` —
  PromptLayer 分层:
  - `test_prepare_places_system_prompt_first` — `PromptLayer().prepare(system_prompt="S", dynamic_messages=[{"role":"user","content":"U"}])` → messages[0] is system, messages[-1] is user
  - `test_prepare_places_tool_defs_after_system_prompt` — `prepare(system_prompt="S", tool_defs=[...])` → tool defs segment comes after system prompt, before dynamic tail
  - `test_prepare_places_snapshot_and_requirements_in_prefix` — `prepare(system_prompt="S", snapshot="SNAP", requirements="REQ")` → snapshot + requirements in stable prefix (before dynamic_messages)
  - `test_prepare_dynamic_tail_appended_after_prefix` — `prepare(system_prompt="S", dynamic_messages=[user, assistant, user])` → all 3 dynamic messages appended after stable prefix, in order
  - `test_prepare_empty_dynamic_messages_returns_only_prefix` — `prepare(system_prompt="S")` with no dynamic_messages → messages has only stable prefix
  - `test_prepare_no_snapshot_no_requirements_still_works` — `prepare(system_prompt="S", dynamic_messages=[...])` → no snapshot/requirements segments, prefix hash still computed

- [X] T011 [P] [US1] Unit test — prefix hash 稳定性 (FR-009):
  - `test_same_inputs_produce_same_prefix_hash` — `prepare(system_prompt="S", snapshot="X")` twice → same `prefix.prefix_hash`
  - `test_changing_system_prompt_changes_prefix_hash` — `prepare(system_prompt="S1")` vs `prepare(system_prompt="S2")` → different prefix_hash
  - `test_changing_snapshot_changes_prefix_hash` — same system_prompt, different snapshot → different prefix_hash (但 system_prompt component hash 相同)
  - `test_changing_requirements_changes_prefix_hash` — same system_prompt + snapshot, different requirements → different prefix_hash
  - `test_component_hashes_independently_track_each_segment` — `prefix.component_hashes["system_prompt"]` 只依赖 system_prompt 内容，不依赖 snapshot / requirements
  - `test_prefix_hash_includes_version_for_invalidation` — `prefix.version == "v1"`，bump version → prefix_hash 全变（cache 全失效）

- [X] T012 [P] [US1] Unit test — tool definitions alphabetical 序列化 (FR-002):
  - `test_serialize_tool_definitions_sorts_by_function_name` — `[{"function":{"name":"z"}}, {"function":{"name":"a"}}]` → serialized order is `[a, z]`
  - `test_serialize_tool_definitions_sorts_by_plain_name` — `[{"name":"z"}, {"name":"a"}]` → serialized order is `[a, z]`
  - `test_serialize_tool_definitions_adding_new_tool_does_not_reorder_existing` — 2 tools serialized, add 3rd → first 2 in same order, 3rd appended in sorted position
  - `test_serialize_tool_definitions_internal_dict_keys_sorted` — `{"b":1, "a":2}` → JSON output has `a` before `b`
  - `test_serialize_tool_definitions_empty_list_returns_empty_string` — `[]` → `""`
  - `test_serialize_tool_definitions_same_input_same_output` — same list twice → same string (deterministic)

- [X] T013 [P] [US1] Unit test — PII 隔离 (FR-005):
  - `test_pii_stays_in_dynamic_tail_not_in_prefix` — user free-text 放 `dynamic_messages`，stable prefix (system_prompt + snapshot + requirements) 中不含 user free-text
  - `test_prepare_does_not_inspect_dynamic_messages_for_pii` — `dynamic_messages` 内容不影响 `prefix_hash`（只 stable components 影响）

- [X] T014 [P] [US1] Unit test — CacheHitRecord (FR-007):
  - `test_cache_hit_record_hit_path` — `CacheHitRecord(trace_id="t", node="n", prefix_hash="h", hit=True, cached_tokens=100, uncached_tokens=50, miss_reason=None, cost_saved=100)` → dataclass fields correct
  - `test_cache_hit_record_miss_path` — `hit=False, miss_reason="first-call"` → dataclass fields correct
  - `test_cache_hit_record_immutable` — frozen dataclass，赋值 `record.hit = False` raises `FrozenInstanceError`
  - `test_record_cache_hit_increments_prometheus_counters` — `record_cache_hit(hit_record, graph="interview", user_id="u")` → `LLM_CACHE_HIT_TOTAL.labels(node, graph, "hit").inc()` called
  - `test_record_cache_miss_increments_miss_counter` — `record_cache_hit(miss_record, ...)` → `LLM_CACHE_HIT_TOTAL.labels(node, graph, "miss").inc()` called
  - `test_record_cache_hit_logs_structured_with_prefix_hash` — `record_cache_hit(record)` → structlog `llm.cache.hit` event with `prefix_hash` + `cached_tokens` + `cost_saved`
  - `test_record_cache_miss_logs_with_miss_reason` — `record_cache_hit(miss_record)` → structlog `llm.cache.miss` event with `prefix_hash` + `miss_reason` (FR-015)

- [X] T015 [P] [US1] Unit test — cache simulation stub (FR-017):
  - `test_cache_simulating_client_realistic_first_call_miss` — `_CacheSimulatingClient(cache_mode="realistic")` first call with new prefix → miss (miss_reason="first-call")
  - `test_cache_simulating_client_realistic_second_call_hit` — same prefix second call → hit (cached_tokens > 0)
  - `test_cache_simulating_client_realistic_prefix_changed_miss` — different prefix → miss (miss_reason="prefix-changed")
  - `test_cache_simulating_client_always_hit_mode` — `cache_mode="always_hit"` → all calls hit (even first call)
  - `test_cache_simulating_client_always_miss_mode` — `cache_mode="always_miss"` → all calls miss (miss_reason="provider-cache-unavailable")
  - `test_cache_simulating_client_records_cost_saved` — hit → `cost_saved > 0`；miss → `cost_saved == 0`

- [X] T016 [P] [US1] Unit test — graceful fallback (FR-008):
  - `test_build_cache_control_headers_returns_diagnostic_headers` — `build_cache_control_headers(prefix)` returns dict with `X-InterCraft-Prefix-Hash` + `X-InterCraft-Cache-Version`
  - `test_build_cache_control_segments_returns_segment_markers` — `build_cache_control_segments(prefix)` returns list of `{component, hash, cacheable}` for each stable component
  - `test_graceful_fallback_when_cache_unavailable` — cache simulation `always_miss` mode → record_cache_hit emits structured warning + metrics still increment（无 user-facing error）

### Implementation for Foundational

- [X] T017 [US1] Implement `backend/app/agents/prompt_caching/layer.py`:
  - `@dataclass(frozen=True) CachePrefix`: `prefix_hash: str`, `component_hashes: dict[str, str]`, `node: str`, `version: str = "v1"`
  - `@dataclass(frozen=True) CacheHitRecord`: `trace_id: str`, `node: str`, `prefix_hash: str`, `hit: bool`, `cached_tokens: int`, `uncached_tokens: int`, `miss_reason: str | None`, `cost_saved: int`
  - `@dataclass LayeredPrompt`: `messages: list[dict]`, `prefix: CachePrefix`, `stable_token_count: int`, `dynamic_token_count: int`
  - `serialize_tool_definitions(tool_defs: list[dict]) -> str` — sort by `function.name` or `name`, then `json.dumps(sort_keys=True, ensure_ascii=False)` (FR-002)
  - `compute_prefix_hash(component_hashes: dict[str, str]) -> str` — sort by key, `|`-join `k:hash` pairs, SHA256
  - `_sha256(text: str) -> str` — SHA256 hex digest
  - `_estimate_tokens(text: str) -> int` — CJK-friendly estimate (1 CJK ≈ 1.5 token, 1 ASCII ≈ 0.25 token)
  - `class PromptLayer` with `VERSION = "v1"` + `prepare(*, system_prompt, tool_defs=None, snapshot=None, requirements=None, dynamic_messages=None, node="unknown") -> LayeredPrompt`:
    - assemble messages: system_prompt → tool_defs → snapshot → requirements → dynamic_messages (FR-001)
    - compute component_hashes for each present stable segment (FR-009)
    - compute prefix_hash from component_hashes (FR-009)
    - estimate stable_token_count + dynamic_token_count
    - return LayeredPrompt
  - `build_cache_control_headers(prefix: CachePrefix) -> dict[str, str]` — placeholder: emit `X-InterCraft-Prefix-Hash` + `X-InterCraft-Cache-Version` (FR-006, DeepSeek protocol ⏳)
  - `build_cache_control_segments(prefix: CachePrefix) -> list[dict]` — placeholder: list of `{component, hash, cacheable: True}` per stable segment (FR-006)
  - `record_cache_hit(record: CacheHitRecord, *, graph="unknown", user_id=None) -> None` — increment prometheus counters (FR-014/016) + emit structlog `llm.cache.hit` / `llm.cache.miss` event with prefix_hash + miss_reason (FR-015)
  - Prometheus counters: `LLM_CACHE_HIT_TOTAL` (labels: node, graph, result), `LLM_CACHE_CACHED_TOKENS_TOTAL` (labels: node, graph), `LLM_CACHE_UNCACHED_TOKENS_TOTAL` (labels: node, graph), `LLM_CACHE_DISCOUNT_TOKENS_TOTAL` (labels: user_id, graph)
  - structlog logger: `app.agents.prompt_caching`

- [X] T018 [US1] Implement `backend/app/agents/prompt_caching/__init__.py`:
  - Re-export public API: `PromptLayer, LayeredPrompt, CachePrefix, CacheHitRecord, serialize_tool_definitions, compute_prefix_hash, record_cache_hit, build_cache_control_headers, build_cache_control_segments`
  - Module docstring: feature 027 US1 scope summary + ⏳ deferred items list (US2/US3/US4 + DeepSeek protocol + 5 graph full integration)

- [X] T019 [US1] Implement `backend/app/agents/prompt_caching/README.md` (Constitution I):
  - Library purpose: prompt 分层 + cache hit observability
  - Public API overview (PromptLayer / LayeredPrompt / CachePrefix / CacheHitRecord)
  - DeepSeek V4 context caching 协议说明 (placeholder + ⏳ 验证后接入)
  - Usage example (prepare → invoke → record_cache_hit)
  - PII 隔离 caller responsibility (FR-005)
  - ⏳ Deferred items list

**Checkpoint**: Foundation ready — prompt_caching library can prepare layered prompts + compute prefix hash + record cache hit/miss + emit metrics + logs.

---

## Phase 3: User Story 1 - Prompt Layering + Cache Hit Observability (Priority: P1) 🎯 MVP

**Goal**: prompt_caching 自包含库 + 专项测试全绿。LLMClient / interview
graph 集成点留 working tree（⏳，跟随 024 落地）。

**Independent Test**: `cd backend && uv run pytest tests/unit/test_prompt_caching.py -q`
全绿。

### Implementation for User Story 1

- [X] T020 [US1] Run prompt_caching 专项测试:
  ```bash
  cd backend && uv run pytest tests/unit/test_prompt_caching.py -q
  ```
  所有 test case 通过（≥20 test cases）。

- [X] T021 [US1] Run 全量回归测试:
  ```bash
  cd backend && uv run pytest -q
  ```
  既有 716 测试零回归（+ 新增 prompt_caching 测试）。

- [X] T022 [US1] Verify metrics + log emission:
  - `record_cache_hit()` 调用后 prometheus counter increment
  - `record_cache_hit()` 调用后 structlog `llm.cache.hit` / `llm.cache.miss` event emitted with prefix_hash + miss_reason

**Checkpoint**: US1 self-contained library complete. LLMClient 集成 + interview
graph 集成 ⏳ working tree（跟随 024 落地）。

---

## Phase 4: User Story 2 - Quota Model Reflects Cached Discount (Priority: P3) ⏳ DEFERRED

**Goal**: cached/uncached rate 计价，quota pre-deduct 用 conservative upper
bound，actual-adjust 按 cached_rate × cached_tokens + full_rate ×
uncached_tokens 计费。

**⏳ Deferred** — 需改 LLMClient `_pre_deduct` / `_actual_adjust` + 新
`PricingConfig` 表 + Alembic migration + 配置外部化（FR-010/011/012/013）。
单独一个 REQ。

### Tests for User Story 2 (⏳ NOT IMPLEMENTED)

- [ ] T023 [P] [US2] Unit test — `PricingConfig` model + repository
- [ ] T024 [P] [US2] Unit test — `_pre_deduct` 用 conservative upper bound (assume cache miss)
- [ ] T025 [P] [US2] Unit test — `_actual_adjust` 按 cached_rate × cached + full_rate × uncached 计费
- [ ] T026 [P] [US2] Unit test — `QuotaLedger` raw vs effective tokens

### Implementation for User Story 2 (⏳ NOT IMPLEMENTED)

- [ ] T027 [P] [US2] Alembic migration: `pricing_configs` table + `quota_ledgers` table
- [ ] T028 [US2] `PricingConfig` repository + service
- [ ] T029 [US2] LLMClient `_pre_deduct` 用 conservative upper bound (FR-010)
- [ ] T030 [US2] LLMClient `_actual_adjust` 按 cached/uncached rate 计费 (FR-011)
- [ ] T031 [US2] `QuotaLedger` repository + service (raw vs effective tokens, FR-013)

---

## Phase 5: User Story 3 - Prompts Are Layered For Cacheability (Priority: P2) ⏳ PARTIAL

**Goal**: 5 graph 的 prompt 组装都走 `PromptLayer.prepare()`。

**⏳ Partial** — 本次只做 interview graph 集成点（working tree，不入 commit）。
其余 4 graph ⏳ 后续。

### Implementation for User Story 3 (PARTIAL)

- [ ] T032 [US3] interview graph nodes 调 `PromptLayer.prepare()` 组装 messages (working tree ⏳):
  - `intake.py` — `intake_node` 内 `client.invoke(messages=...)` 改为 `PromptLayer.prepare(system_prompt=..., dynamic_messages=[{"role":"user","content":prompt}])`
  - `question_gen.py` — `question_gen_node` 同上
  - `score.py` — `score_node` 同上
  - `report.py` — `report_node` 同上
- [ ] T033 [US3] LLMClient `invoke` 内调 `PromptLayer.prepare()` + `record_cache_hit()` (working tree ⏳):
  - invoke 接受 `LayeredPrompt` 或在内部调 `PromptLayer.prepare()`
  - 调用 `_call_deepseek` 时传 `build_cache_control_headers()` 返回的 headers
  - 响应回来后根据 `response.usage.cached_tokens`（DeepSeek V4 返回字段，⏳ 验证）构造 `CacheHitRecord` + `record_cache_hit()`
- [ ] T034 [US3] ⏳ resume_optimize graph 集成
- [ ] T035 [US3] ⏳ ability_diagnose graph 集成
- [ ] T036 [US3] ⏳ general_coach graph 集成
- [ ] T037 [US3] ⏳ error_coach graph 集成

---

## Phase 6: User Story 4 - Quota Model Reflects Cached Discount (Frontend Display) (Priority: P3) ⏳ DEFERRED

**Goal**: 前端 Settings 页显示 raw vs effective tokens + cache discount line。

**⏳ Deferred** — 需改前端 Settings 页 + QuotaLedger API endpoint。范围大。

### Implementation for User Story 4 (⏳ NOT IMPLEMENTED)

- [ ] T038 [P] [US4] QuotaLedger API endpoint (`GET /api/v1/quota/usage`)
- [ ] T039 [US4] Frontend Settings 页加 raw vs effective tokens 显示
- [ ] T040 [US4] Frontend cache discount line 可见

---

## Phase 7: DeepSeek V4 Cache Protocol Verification + Eval Suite (Priority: P2) ⏳ DEFERRED

**Goal**: 验证 DeepSeek V4 context caching 协议（cache_control header /
segment marker / prefix hash），接入 `build_cache_control_headers()` +
`build_cache_control_segments()`。026 eval suite 加 cache hit rate regression
case。

**⏳ Deferred** — DeepSeek V4 协议在 plan 阶段验证后接入；026 eval suite
扩展依赖 026 US2 完成。

### Implementation (⏳ NOT IMPLEMENTED)

- [ ] T041 [US1] 验证 DeepSeek V4 context caching 协议（cache_control header / segment marker / prefix hash）
- [ ] T042 [US1] `build_cache_control_headers()` 接入真实协议（替换 placeholder）
- [ ] T043 [US1] `build_cache_control_segments()` 接入真实协议
- [ ] T044 [US4] 026 eval suite 加 cache hit rate regression case (FR-018)
- [ ] T045 [US4] 026 eval suite 检测 prompt layering 破坏导致 cache hit rate drop

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 文档 + 集成点验证。

- [X] T046 [P] Documentation: `backend/app/agents/prompt_caching/README.md` (Constitution I)
- [ ] T047 ⏳ LLMClient 集成点（working tree M，跟随 024 落地）
- [ ] T048 ⏳ interview graph 集成点（working tree M，跟随 024 落地）
- [ ] T049 ⏳ DeepSeek V4 cache 协议完整验证（plan 阶段验证后接入）
- [ ] T050 ⏳ 5 graph 全集成 prompt 分层（interview done in working tree / 其余 4 graph ⏳）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS US1 integration
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion
- **User Story 2 (Phase 4)**: ⏳ Deferred — needs LLMClient _pre_deduct/_actual_adjust changes
- **User Story 3 (Phase 5)**: Partial — interview graph 集成点 ⏳ working tree
- **User Story 4 (Phase 6)**: ⏳ Deferred — needs frontend changes
- **DeepSeek Protocol + Eval (Phase 7)**: ⏳ Deferred — needs protocol verification + 026 extension
- **Polish (Phase 8)**: Partial — README done; 集成点 ⏳

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Models/dataclasses before helpers
- Helpers before public API
- Core implementation before integration

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tests marked [P] can run in parallel (test cases are independent)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks US1 integration)
3. Complete Phase 3: User Story 1 (self-contained library + tests)
4. **STOP and VALIDATE**: Test prompt_caching library independently
5. LLMClient + interview graph 集成点 ⏳ working tree（跟随 024 落地）

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 → Test independently → Deploy/Demo (MVP!)
3. ⏳ Add US2 → cached/uncached rate 计价
4. ⏳ Add US3 → 5 graph 全集成
5. ⏳ Add US4 → 前端 quota display + eval regression

---

## Notes

- 本次实现严格收窄到 US1 self-contained library + tests，不入 commit 任何
  working tree M 文件修改（llm_client.py / token_estimator.py /
  llm_client_mock.py）
- LLMClient 集成点 + interview graph 集成点在 working tree 跟随 024 落地
  （跟 029 OTel / 031 A2A 同策略）
- DeepSeek V4 context caching 协议用 placeholder 抽象层，plan 阶段验证后
  接入（不影响 US1 cache hit observability 逻辑）
- MockLLMClient cache_mode 参数 ⏳ working tree（FR-017 由测试 local stub
  `_CacheSimulatingClient` 满足）
- 既有 716 测试零回归（prompt_caching 是新模块，不改既有代码）
