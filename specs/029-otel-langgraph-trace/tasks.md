# Tasks: OpenTelemetry & LangGraph Distributed Trace

**Input**: Design documents from `/specs/029-otel-langgraph-trace/`

**Prerequisites**: plan.md, spec.md

**Tests**: Tests are included (Constitution III TDD). Each implementation phase
has test tasks first.

**Organization**: Tasks grouped by user story. **本次仅实现 US1 + OTLP export
骨架**；US2 / US3 / US4 任务列出但标记 ⏳ 后续。

**Partial Scope**: 见 plan.md "Partial Scope Justification" 节。本次实现范围
= US1 单 trace 跨 graph + OTLP export 骨架 + structlog trace_id 注入 +
interview + error_coach 两 graph 集成；其余 3 graph + US2/US3/US4 ⏳ 后续。

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline + create directory structure + add deps.

- [X] T001 [P] Verify backend tests green: `cd backend && uv run pytest -q` (≥ 586 passed baseline)
- [X] T002 [P] Add deps: `uv add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http`
- [X] T003 [P] Verify OTel imports work: `uv run python -c "from opentelemetry import trace; from opentelemetry.sdk.trace import TracerProvider; from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor; from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter; from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter; print('OK')"`
- [X] T004 [P] Create `backend/app/observability/__init__.py` (empty package marker)
- [X] T005 [P] Create `backend/tests/unit/test_tracing_init.py` placeholder
- [X] T006 [P] Create `backend/tests/unit/test_tracing_span.py` placeholder
- [X] T007 [P] Create `backend/tests/integration/test_tracing_graph_integration.py` placeholder

---

## Phase 2: Foundational (Tracing Library — BLOCKS US1 Integration)

**Purpose**: Build the OTel tracing library + structlog processor. This is the
self-contained library that all 5 graphs + LLM client + tools will import.

**⚠️ CRITICAL**: No US1 integration work can begin until this phase is complete.

### Tests for Foundational (TDD)

- [X] T010 [P] [US1] Unit test `backend/tests/unit/test_tracing_init.py`:
  - `test_init_tracing_with_noop_exporter_does_not_raise` — `exporter="none"` → noop tracer, no spans
  - `test_init_tracing_with_console_exporter_emits_spans` — `exporter="console"` → ConsoleSpanExporter, span emitted
  - `test_init_tracing_with_in_memory_exporter_collects_spans` — `exporter="in_memory"` → InMemorySpanExporter, span collected
  - `test_init_tracing_with_otlp_exporter_endpoint_configured` — `exporter="otlp"` + `endpoint="http://localhost:4318"` → OTLPSpanExporter configured
  - `test_init_tracing_with_otlp_exporter_no_endpoint_falls_back_to_console` — `exporter="otlp"` + no endpoint → fallback to console (dev mode)
  - `test_init_tracing_fail_open_on_exception` — mock OTLPSpanExporter to raise → init_tracing catches + log warning + noop tracer (FR-017)
  - `test_init_tracing_idempotent` — calling `init_tracing` twice does not re-register provider
  - `test_shutdown_tracing_flushes_spans` — `shutdown_tracing()` calls `provider.force_flush()`

- [X] T011 [P] [US1] Unit test `backend/tests/unit/test_tracing_span.py`:
  - `test_span_creates_with_correct_name` — `with span("test.span") as s: ...` → span.name == "test.span"
  - `test_span_attributes_set_correctly` — `span("test", node_name="intake", model="deepseek")` → span attributes include `node_name`, `model`
  - `test_span_records_exception_on_error` — exception inside `with span(...)` → span status = ERROR, exception recorded
  - `test_span_no_error_on_success` — normal exit → span status = UNSET (not ERROR)
  - `test_traced_node_decorator_async_emits_span` — `@traced_node("intake")` on async fn → span named `node.intake` created
  - `test_traced_node_decorator_sync_emits_span` — `@traced_node("planner_complete")` on sync fn → span named `node.planner_complete` created
  - `test_traced_node_decorator_propagates_exception` — fn raises → span status = ERROR + exception propagated to caller
  - `test_traced_tool_decorator_emits_span_with_args_summary` — `@traced_tool("tavily_search")` → span has `tool_name`, `args_summary` (truncated to 100 chars)
  - `test_record_llm_span_attributes_sets_model_and_tokens` — `record_llm_span_attributes(span, model="X", prompt_tokens=100, ...)` → span attributes set
  - `test_structlog_processor_injects_trace_id_when_span_active` — `_inject_otel_context` processor → event_dict has `trace_id` + `span_id` when span active
  - `test_structlog_processor_no_trace_id_when_no_span` — no active span → event_dict has no `trace_id` field

### Implementation for Foundational

- [X] T012 [US1] Implement `backend/app/observability/tracing.py`:
  - `@dataclass TracingConfig`:
    - `service_name: str = "intercraft-backend"`
    - `exporter: Literal["none", "console", "in_memory", "otlp"] = "console"`
    - `otlp_endpoint: str | None = None` (e.g. `http://localhost:4318/v1/traces`)
    - `otlp_headers: dict[str, str] | None = None`
    - `sample_ratio: float = 1.0` (US3 ⏳ — default 100%)
  - `init_tracing(config: TracingConfig) -> None` — register `TracerProvider` + `BatchSpanProcessor` (OTLP/console) or `SimpleSpanProcessor` (in_memory/console). Fail-open: any exception → log warning + noop.
  - `shutdown_tracing() -> None` — `provider.force_flush()` + `provider.shutdown()`. Best-effort, no raise.
  - `get_tracer() -> trace.Tracer` — `trace.get_tracer("intercraft")`. Always returns a tracer (noop if not init).
  - `@contextmanager span(name: str, **attrs) -> Iterator[Span]` — start span + set attrs + try/except + record exception on error. Fail-open: never raises.
  - `@traced_node(name: str)` decorator — wraps async or sync fn, creates `node.{name}` span, sets `node.name` attr, records exception, propagates return value.
  - `@traced_tool(name: str)` decorator — wraps async or sync fn, creates `tool.{name}` span, sets `tool.name` + `args_summary` (truncated) + `result_summary` (truncated) attrs.
  - `record_llm_span_attributes(span, **attrs) -> None` — set model / prompt_tokens / completion_tokens / duration_ms / cache_status / retry_count on a span. Best-effort.
  - `finish_span_with_exception(span, exc) -> None` — set status ERROR + record exception. Best-effort.
  - `_inject_otel_context(_, __, event_dict) -> dict` — structlog processor, reads `trace.get_current_span()` context, injects `trace_id` + `span_id` hex strings when available. Fail-open: never raises.
  - All span operations wrapped in try/except — fail-open (FR-017).
  - `get_in_memory_exporter() -> InMemorySpanExporter | None` — for tests to inspect collected spans.
  - `_reset_tracing_for_test() -> None` — clear provider + reset module state (test-only helper).

- [X] T013 [US1] Implement `backend/app/observability/__init__.py`:
  - Re-export public API: `TracingConfig, init_tracing, shutdown_tracing, get_tracer, span, traced_node, traced_tool, record_llm_span_attributes, finish_span_with_exception, get_in_memory_exporter, _reset_tracing_for_test`
  - Module docstring: feature 029 US1 scope summary + ⏳ deferred items list.

**Checkpoint**: Foundation ready — tracing library can init + emit spans + fail-open + structlog processor.

---

## Phase 3: User Story 1 - LLM Client + MockLLMClient Span Integration (Priority: P1) 🎯 MVP

**Goal**: LLM 调用发 child span（model / tokens / latency / cache status）。
MockLLMClient 也发 span（FR-018），使 trace 测试不依赖真 DeepSeek。

**Independent Test**: `uv run pytest tests/unit/test_tracing_span.py tests/unit/test_llm_client.py -q` 全绿。

### Tests for User Story 1 (TDD)

- [X] T020 [P] [US1] Unit test `backend/tests/unit/test_tracing_span.py` (extend):
  - `test_llm_invoke_creates_child_span_with_model_and_tokens` — patch LLM client, run invoke, assert `llm.invoke` span has `model`, `prompt_tokens`, `completion_tokens`, `duration_ms`, `cache_status` attrs
  - `test_llm_invoke_span_status_error_on_failure` — mock LLM raises → span status = ERROR
  - `test_mock_llm_invoke_creates_span` — MockLLMClient.invoke → `llm.invoke` span created with `model="mock-llm"`

### Implementation for User Story 1

- [X] T021 [US1] Modify `backend/app/agents/llm_client.py`:
  - Import `span`, `record_llm_span_attributes`, `finish_span_with_exception` from `app.observability`
  - In `LLMClient.invoke`: wrap `_call_deepseek` call site in `with span("llm.invoke", node_name=node_name, model=model) as s:` block
  - Set initial attrs: `model`, `node_name`, `estimated_tokens`, `user_id`, `thread_id` (NOT message content — PII)
  - After response: `record_llm_span_attributes(s, model=..., prompt_tokens=..., completion_tokens=..., duration_ms=..., cache_status="miss", retry_count=...)`
  - On exception: `finish_span_with_exception(s, exc)` then re-raise
  - Same pattern for `invoke_stream` (best-effort — streaming span may not have final tokens until end)

- [X] T022 [US1] Modify `backend/app/agents/llm_client_mock.py`:
  - Import `span`, `record_llm_span_attributes` from `app.observability`
  - In `MockLLMClient.invoke`: wrap content generation in `with span("llm.invoke", node_name=node_name, model="mock-llm") as s:` block
  - Set `cache_status="mock"` + `prompt_tokens=0` + `completion_tokens=0` + `duration_ms=0`
  - Fail-open: span operations in try/except (mock must never break on OTel init failure)

**Checkpoint**: LLM client emits child spans; MockLLMClient also emits spans (FR-018).

---

## Phase 4: User Story 1 - Graph Node Span Integration (Priority: P1) 🎯 MVP

**Goal**: 5 个 interview graph 节点 + 2 个 error_coach 节点入口/出口加 span。
SC-001 要求「一次 interview 调用产生 ≥5 node spans + ≥5 LLM spans」。

**Independent Test**: `uv run pytest tests/integration/test_tracing_graph_integration.py -q` 全绿。

### Tests for User Story 1 (TDD)

- [X] T030 [P] [US1] Integration test `backend/tests/integration/test_tracing_graph_integration.py`:
  - `test_interview_graph_produces_single_trace_with_5_node_spans` — init tracing with InMemorySpanExporter, run interview graph (MockLLMClient), assert all spans share one `trace_id` + ≥5 spans named `node.intake` / `node.question_gen` / `node.score` / `node.report` (or subgraph nodes)
  - `test_interview_graph_produces_5_llm_invoke_spans` — same trace, assert ≥5 spans named `llm.invoke` (intake / question_gen ×5 / score ×5 / report — at least 5 emitted)
  - `test_llm_spans_are_children_of_node_spans` — assert each `llm.invoke` span's `parent_span_id` matches a `node.*` span's `span_id`
  - `test_error_node_span_marked_with_error_status` — mock LLM raises → `node.intake` span status = ERROR + exception recorded
  - `test_trace_export_fail_open_does_not_block_agent` — set unreachable OTLP endpoint, run interview graph, assert graph still completes successfully (FR-017)

### Implementation for User Story 1

- [X] T031 [P] [US1] Modify `backend/app/agents/interview/nodes/intake.py`:
  - Add `@traced_node("intake")` decorator on `intake_node`
  - Import from `app.observability`

- [X] T032 [P] [US1] Modify `backend/app/agents/interview/nodes/question_gen.py`:
  - Add `@traced_node("question_gen")` decorator on `question_gen_node`

- [X] T033 [P] [US1] Modify `backend/app/agents/interview/nodes/score.py`:
  - Add `@traced_node("score")` decorator on `score_node`

- [X] T034 [P] [US1] Modify `backend/app/agents/interview/nodes/report.py`:
  - Add `@traced_node("report")` decorator on `report_node`

- [X] T035 [P] [US1] Modify `backend/app/agents/nodes/error_coach/hint_ladder.py`:
  - Add `@traced_node("error_coach_hint")` decorator on `hint_ladder_node`

- [X] T036 [P] [US1] Modify `backend/app/agents/nodes/error_coach/evaluate.py`:
  - Add `@traced_node("error_coach_evaluate")` decorator on `evaluate_node`

- [X] T037 [P] [US1] Modify `backend/app/agents/tools/tavily_search.py`:
  - Add `@traced_tool("tavily_search")` decorator on `tavily_search` (示范 tool span)

**Checkpoint**: interview + error_coach graph nodes emit spans; SC-001 measurable.

---

## Phase 5: structlog + FastAPI lifespan Integration (Priority: P1)

**Goal**: structlog 日志加 `trace_id` + `span_id` 字段（FR-013）；FastAPI
lifespan 启动时 init tracing + 关闭时 shutdown。

### Tests for User Story 1 (TDD)

- [X] T040 [P] [US1] Unit test `backend/tests/unit/test_tracing_span.py` (extend):
  - `test_structlog_processor_injects_trace_id_during_node_span` — start a span, log a structlog event, assert event_dict has `trace_id` matching span's trace_id
  - `test_structlog_processor_clears_when_span_exits` — exit span, log another event, assert no `trace_id` field

### Implementation for User Story 1

- [X] T041 [US1] Modify `backend/app/core/logging.py`:
  - Import `_inject_otel_context` from `app.observability`
  - Add `_inject_otel_context` to structlog processors list (after `_inject_context`, before `add_log_level`)
  - `_inject_otel_context` reads `trace.get_current_span()` context — fails open (no trace_id when no span)

- [X] T042 [US1] Modify `backend/app/core/config.py`:
  - Add `otel_service_name: str = "intercraft-backend"` setting
  - Add `otel_traces_exporter: str = "console"` setting (`none` / `console` / `otlp`)
  - Add `otel_exporter_otlp_endpoint: str = ""` setting
  - Add `otel_exporter_otlp_headers: str = ""` setting (comma-separated `key:val` pairs)

- [X] T043 [US1] Modify `backend/app/main.py`:
  - In `lifespan`: build `TracingConfig` from settings, call `init_tracing(config)` before `yield`
  - In `finally`: `await shutdown_tracing()` (best-effort, before `close_checkpointer`)

**Checkpoint**: logs carry trace_id; FastAPI lifespan inits + shuts down tracing.

---

## Phase 6: Polish & Regression

- [X] T050 Run `cd backend && uv run pytest -q` — 全量回归零失败（≥ 586 passed + tracing 新增）
- [X] T051 Run `npm run typecheck` — 前端 clean（本 feature 不动前端）
- [X] T052 Update `specs/README.md` 029 行 Status 为 `in_progress (US1 partial)`
- [ ] T053 [P] Write `specs/029-otel-langgraph-trace/requirements-status.md` 标记 US1 done / US2-4 ⏳ — **⏳ 后续**（US1 全量回归 + SC-001 实测后补）

---

## Phase 7: ⏳ Deferred — US2 Cross-Process Propagation (Priority: P2, 后续)

**Goal**: trace context 跨 HTTP → WS → ARQ worker → LLM call → graph node 全程传播。

**依赖**: US1 tracing library 完成（已完成）。本 phase 修改 middleware + WS
handler + ARQ worker，范围大。

- [ ] T060 [US2] ⏳ `RequestIDMiddleware` 改造：从 HTTP header `traceparent` /
  `tracestate` 解析 OTel context，注入当前 span
- [ ] T061 [US2] ⏳ WS handler (`backend/app/api/v1/ws/interview.py`) 接收
  `traceparent` 并 set span context
- [ ] T062 [US2] ⏳ ARQ worker `on_job_start` hook：从 job kwargs 提取
  `traceparent`，set context
- [ ] T063 [US2] ⏳ interview planner subgraph 父子 span context propagation
  (FR-007)
- [ ] T064 [US2] ⏳ integration test：HTTP → ARQ 跨进程，assert 同一 trace_id
- [ ] T065 [US2] ⏳ integration test：trace context 丢失时 fail-open + warning log

**Checkpoint**: ⏳ 后续 — US1 baseline 完成后启动。

---

## Phase 8: ⏳ Deferred — US3 Sampling Config (Priority: P2, 后续)

**Goal**: sampling rules 可配（error 100% / success 10%）。

**依赖**: US2 cross-process propagation（不然单进程内的 sampling 简单）。

- [ ] T070 [US3] ⏳ `SamplingRule` dataclass：`graph_name, outcome, ratio`
- [ ] T071 [US3] ⏳ `ParentBasedSampler` + `TraceIdRatioSampler` 组合
- [ ] T072 [US3] ⏳ per-invocation override：`RunnableConfig` 传 `sampling_ratio`
- [ ] T073 [US3] ⏳ integration test：error trace 100% sampled，success trace 按 ratio

**Checkpoint**: ⏳ 后续 — US2 完成后启动。

---

## Phase 9: ⏳ Deferred — US4 Logs/Metrics Join Exemplars (Priority: P3, 后续)

**Goal**: prometheus exemplars + 完整 trace join。

**依赖**: US1 structlog trace_id 注入（已完成基础）。

- [ ] T080 [US4] ⏳ 评估 `prometheus-exposition-formats` 包兼容性
- [ ] T081 [US4] ⏳ Counter / Histogram 加 exemplar（trace_id 作为 label）
- [ ] T082 [US4] ⏳ metrics endpoint 输出 exemplars
- [ ] T083 [US4] ⏳ integration test：metric exemplar trace_id 与 active span 匹配

**Checkpoint**: ⏳ 后续 — prometheus exemplars 支持评估后启动。

---

## Phase 10: ⏳ Deferred — Local Trace Viewer UI (Priority: P3, 后续)

**Goal**: 本地 dev 用 trace viewer（FR-012）。

**依赖**: US1 console exporter（已满足基础 dev 需求）。

- [ ] T090 [US4] ⏳ 评估 Jaeger UI / Tempo / 自研 web viewer
- [ ] T091 [US4] ⏳ Docker compose 加 Jaeger all-in-one 服务
- [ ] T092 [US4] ⏳ `backend/scripts/trace_viewer.py` CLI 启动 viewer

**Checkpoint**: ⏳ 后续 — console exporter 够 dev 用，专门 viewer 后续。

---

## Phase 11: ⏳ Deferred — PII Redaction from Span Attributes (Priority: P2, 后续)

**Goal**: span attributes 自动 redact PII（FR-016）。

**依赖**: US1 tracing library（已完成基础 — `@traced_tool` 已截断 args_summary）。

- [ ] T100 [US1] ⏳ `RedactingSpanProcessor` 包装 `BatchSpanProcessor`
- [ ] T101 [US1] ⏳ PII pattern library（email / phone / 身份证 / free-text answer）
- [ ] T102 [US1] ⏳ integration test：span attributes 不含 PII

**Checkpoint**: ⏳ 后续 — 当前 `@traced_tool` 已做基础截断，完整 redaction 后续。

---

## Phase 12: ⏳ Deferred — 其余 3 Graph 集成 (Priority: P2, 后续)

**Goal**: resume_optimize / ability_diagnose / general_coach 三 graph 加 span。

**依赖**: US1 interview + error_coach 框架验证（已完成）。

- [ ] T110 [US1] ⏳ `resume_optimize` graph：`@traced_node` on load_branch / diff_jd / suggest_blocks / apply_or_discard
- [ ] T111 [US1] ⏳ `ability_diagnose` graph：`@traced_node` on aggregate_scores / compare_baseline / generate_insight / update_dimensions
- [ ] T112 [US1] ⏳ `general_coach` graph：`@traced_node` on intent / route / respond

**Checkpoint**: ⏳ 后续 — interview + error_coach 框架验证后批量补。

---

## Phase 13: ⏳ Deferred — 026 Trace 集成 (Priority: P3, 后续)

**Goal**: 026 轻量 trace 升级为 029 OTel（026 当前 `app/eval/` 用 stub trace）。

**依赖**: US1 OTel tracing library（已完成）。

- [ ] T120 [US1] ⏳ 026 EvalRunner 用 OTel span 代替 stub trace
- [ ] T121 [US1] ⏳ eval case 跑完后 assert OTel trace 结构

**Checkpoint**: ⏳ 后续 — 026 US3 trace 采集完成时升级到 OTel。

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — create dirs + verify baseline + add deps
- **Foundational (Phase 2)**: BLOCKS US1 integration — tracing library must exist before LLM client / graph integration
- **US1 LLM span (Phase 3)**: Depends on Phase 2
- **US1 graph node span (Phase 4)**: Depends on Phase 2 + Phase 3 (LLM spans are children of node spans)
- **US1 structlog + lifespan (Phase 5)**: Depends on Phase 2
- **Polish (Phase 6)**: Depends on Phase 3-5 complete
- **⏳ Deferred (Phase 7-13)**: Future work — US2/US3/US4 + 3 graph + 026

### Within Each User Story

- Tests first (TDD) — watch them fail, then implement
- Library code before integration
- Single-file changes can run in parallel ([P] marker)
- LLM client integration before graph node integration (LLM spans are children)

### Parallel Opportunities

- Phase 2 T010 + T011 can run in parallel (different test files)
- Phase 4 T031-T037 can all run in parallel (different node files)
- Phase 5 T040-T042 can run in parallel (different files)

---

## Implementation Strategy

### MVP First (US1 partial only)

1. Complete Phase 1: Setup (dirs + baseline + deps)
2. Complete Phase 2: Tracing library (TDD)
3. Complete Phase 3: LLM client + MockLLMClient span integration
4. Complete Phase 4: interview + error_coach graph node spans
5. Complete Phase 5: structlog + FastAPI lifespan
6. **STOP and VALIDATE**: `uv run pytest tests/unit/test_tracing_*.py tests/integration/test_tracing_graph_integration.py -q` + `uv run pytest -q` 全绿
7. **DEFER**: US2 (cross-process) → 单独 REQ；US3 (sampling) → 单独评估；US4 (exemplars) → prometheus 兼容性评估；其余 3 graph → 框架验证后批量补

### Incremental Delivery (Future)

1. Add US2 cross-process propagation (after US1 baseline stable)
2. Add US3 sampling (after US2 propagation — sampling needs cross-process decision)
3. Add US4 exemplars (after prometheus-exposition-formats compatibility check)
4. Add 3 remaining graph integrations (after interview + error_coach framework validated)
5. Add PII redaction (after span attribute audit)
6. Add 026 trace upgrade (after 026 US3 trace collection)

---

## Notes

- [P] tasks = different files, no dependencies
- Constitution III TDD: tests first, watch them fail, then implement
- Commit after each phase or logical group
- Stop at any checkpoint to validate story independently
- **Partial scope**: 本次仅实现 US1 + OTLP export 骨架；US2/US3/US4 + 其余 3 graph + 026 集成全部 ⏳ 后续
- **关键避坑**:
  - L004 (api-quota-risk): 范围已收窄到 US1，不扩展实现 US2/US3/US4
  - L002 (test-pattern): tracing 测试放 `backend/tests/unit/test_tracing_*.py` + `backend/tests/integration/test_tracing_graph_integration.py`，不污染既有测试目录
  - L003 (interview-caveat): trace 测试用 MockLLMClient，不依赖真 DeepSeek
  - Constitution V (Observability): fail-open 是核心原则，trace export 失败绝不阻塞 agent (FR-017)
  - FR-008 backward-compat: `_request_id_var` 保留，OTel context 是新增层
  - FR-015 augment 不 replace: prometheus_client + structlog 保留
  - FR-018 MockLLMClient 发 spans: trace 测试不依赖真 provider
  - PII: span attributes 只放 node name + model + token counts + latency，不放 user free-text answer
