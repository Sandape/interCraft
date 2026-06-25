# Implementation Plan: OpenTelemetry & LangGraph Distributed Trace

**Branch**: `029-otel-langgraph-trace` | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/029-otel-langgraph-trace/spec.md`

## Summary

把现有 `prometheus_client` + `structlog` + `_request_id_var` ContextVar 拼凑升级
为 OpenTelemetry 分布式 trace。本次 **partial 实现**：

- **US1 核心**（P1）：单 trace 跨 graph + OTLP export 骨架 ——
  - 新自包含库 `backend/app/observability/`（Constitution I）
  - 集成 `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http`（HTTP 协议，无 gRPC 原生依赖）
  - 5 个 graph 的节点入口/出口加 span（interview / error_coach 已实现，其余 3 个 ⏳）
  - LLM 调用加 child span（model / input tokens / output tokens / latency / cache status）
  - tool 调用加 child span（tool name / args summary / duration）
  - span 层级：graph node span > LLM/tool span（children）
  - OTLP export 配置（endpoint env var）+ **fail-open**（export 失败不阻塞 agent，FR-017）
  - 本地 dev trace viewer（`ConsoleSpanExporter`，免外部依赖，FR-012）
- **基础测试** —— tracer init unit + span generation unit + fail-open test +
  graph integration test（MockLLMClient 跑 interview graph，assert ≥5 node spans + ≥5 LLM spans）
- **现有 request_id 迁移** —— `_request_id_var` 保留（FR-008 backward-compat shim）；
  OTel trace context 作为新增层；structlog 日志加 `trace_id` + `span_id` 字段（FR-013）

**⏳ 标记后续（不在本 partial 范围）**：
- US2 cross-process propagation（HTTP→WS→ARQ，FR-006/007）—— 需改 middleware + WS handler + ARQ worker
- US3 sampling 可配（error 100% / success 10%，FR-011）—— 默认 100% sampling
- US4 logs/metrics join to trace（FR-014 exemplars）—— structlog 加 trace_id 是基础（已做）
- 本地 trace viewer UI（FR-012）—— console exporter 够 dev 用
- PII redaction from span attributes（FR-016）—— 基础 redaction 可做，完整 ⏳
- 026 trace 集成（026 轻量 trace → 029 OTel 升级）—— 029 OTel 是独立层
- 5 graph 全集成：interview + error_coach done，resume_optimize / ability_diagnose / general_coach ⏳

**关键约束**：
- 不 replace 现有 observability（FR-015：augment 不 replace，prometheus_client + structlog 保留）
- request_id 兼容（FR-008：`_request_id_var` ContextVar 保留，OTel context 是新增层）
- fail-open（FR-017：trace export 失败绝不阻塞 agent）
- L004 api-quota-risk：本次范围收窄到 US1，避免 5 graph 全集成导致 API quota 耗尽
- MockLLMClient 发 spans（FR-018）：trace 测试用 MockLLMClient 跑 graph，不依赖真 DeepSeek

## Technical Context

**Language/Version**: Python 3.12（项目要求 `>=3.11`，实际 venv 3.12.7）。

**Primary Dependencies**:
- 新增：`opentelemetry-api==1.43.0`、`opentelemetry-sdk==1.43.0`、
  `opentelemetry-exporter-otlp-proto-http==1.43.0`（HTTP 协议，无 gRPC native dep）
- 保留：FastAPI、LangGraph 0.2、openai、pydantic 2.13、structlog、prometheus_client。

**Storage**: 不新增 DB 表（trace 通过 OTLP export 到外部 backend；本地 dev 用
`ConsoleSpanExporter` + 测试用 `InMemorySpanExporter`）。

**Testing**: pytest（tracing 专项单测在 `backend/tests/unit/test_tracing_*.py`，
graph integration 在 `backend/tests/integration/test_tracing_graph_integration.py`）。

**Target Platform**: Linux server (CI) + dev 本地（Windows + bash）。

**Project Type**: Library（`backend/app/observability/`）+ graph node decorator +
LLM client wrapper + structlog processor + FastAPI lifespan hook。

**Performance Goals**: trace export overhead ≤ 5% total agent latency（SC-004）。
BatchSpanProcessor 异步 flush，不阻塞 invoke 主路径。

**Constraints**:
- 不改 graph 业务节点逻辑（decorator 形式接入，节点函数主体不动）
- 不改 LLM client 契约（`invoke` / `invoke_stream` 签名不变）
- 不改 API 契约（无新 endpoint）
- 既有 586 测试零回归
- export 失败 fail-open（不阻塞 agent）

**Scale/Scope**: 本次实现 2 个 graph（interview + error_coach）的 span 集成 + LLM
client span + structlog trace_id 注入；其余 3 graph ⏳ 后续。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ Pass | `backend/app/observability/` 自包含库：`tracing.py` 单文件 export `init_tracing` / `get_tracer` / `span` / `traced_node` / `traced_tool` / `record_llm_span_attributes` / `finish_span_with_exception` / structlog processor。无 DB / FastAPI 直接依赖（FastAPI lifespan 只是 init 调用方，可被 CLI / 测试绕过）。5 个 graph + LLM client + structlog 后续接入时仅 import 这个库。 |
| II. CLI Interface | ✅ Pass | 测试用 `init_tracing(TracingConfig(exporter="in_memory"))` 拿 `InMemorySpanExporter`，可直接 inspect spans。CI 跑 `uv run pytest tests/unit/test_tracing_*.py tests/integration/test_tracing_graph_integration.py -q`。 |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | TDD：先写 `test_tracing_init.py`（init + fail-open）+ `test_tracing_span.py`（span attributes）+ `test_tracing_graph_integration.py`（interview graph + MockLLMClient，assert ≥5 node spans + ≥5 LLM spans）。 |
| IV. Integration & Synchronization Testing | ✅ Pass | graph integration test 真实跑过 `interview_graph` 的 5 个节点（intake / planner subgraph / interviewer / score / report）+ MockLLMClient 注入，验证 trace 结构（5 node spans + 5 LLM spans under one trace_id）。 |
| V. Observability | ✅ Pass | 每个节点入口/出口 span + LLM call child span + tool call child span；span attributes 含 node_name / model / tokens / latency / cache_status；error span 标 `Status(StatusCode.ERROR)` + exception；fail-open log event `tracing.export_failed`；structlog 加 `trace_id` + `span_id` 字段。 |

**Gate Result**: PASS — 无违规项，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/029-otel-langgraph-trace/
├── plan.md              # This file
├── tasks.md             # Phase 2 output
├── spec.md              # Existing
└── checklists/          # Existing
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── observability/              # 新增: 自包含 OTel trace 库 (Constitution I)
│   │   ├── __init__.py             # 公共 API re-exports
│   │   └── tracing.py              # init / span / decorator / structlog processor
│   ├── agents/
│   │   ├── llm_client.py           # 修改: invoke 内加 LLM child span
│   │   ├── llm_client_mock.py      # 修改: MockLLMClient.invoke 也发 span (FR-018)
│   │   ├── interview/
│   │   │   └── nodes/
│   │   │       ├── intake.py        # 修改: @traced_node 装饰
│   │   │       ├── question_gen.py  # 修改: @traced_node 装饰
│   │   │       ├── score.py         # 修改: @traced_node 装饰
│   │   │       └── report.py         # 修改: @traced_node 装饰
│   │   ├── nodes/
│   │   │   └── error_coach/
│   │   │       ├── hint_ladder.py   # 修改: @traced_node 装饰
│   │   │       ├── evaluate.py      # 修改: @traced_node 装饰
│   │   │       └── ...
│   │   └── tools/
│   │       └── tavily_search.py    # 修改: @traced_tool 装饰 (示范)
│   ├── core/
│   │   ├── logging.py              # 修改: structlog processor 加 trace_id + span_id
│   │   └── config.py               # 修改: 加 OTel 相关 settings 字段
│   └── main.py                     # 修改: lifespan 调 init_tracing + shutdown_tracing
└── tests/
    ├── unit/
    │   ├── test_tracing_init.py    # 新增: tracer init / fail-open / config
    │   └── test_tracing_span.py     # 新增: span attributes / decorator 行为
    └── integration/
        └── test_tracing_graph_integration.py  # 新增: interview graph + MockLLMClient, assert span 结构
```

**Structure Decision**: 单文件 `tracing.py` 而非拆 `__init__.py / _init.py /
_processors.py / _decorators.py`。029 US1 partial 范围内单文件足够，过度拆分
反而增加导入开销；后续 US2 cross-process propagation 时再拆 `propagators.py`。

## Complexity Tracking

> 无 Constitution Check 违规项。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

## Partial Scope Justification

**为什么 partial**：

1. **L004 api-quota-risk**：5 graph 全集成 + LLM 调用各跑一遍 trace 验证 = 至少
   15 次 LLM 调用，单次 pytest 验证可能烧 100K+ tokens。本次只做 interview +
   error_coach 两个 P1 graph，其余 3 个标 ⏳，避免 quota 耗尽。
2. **US2 cross-process propagation 是大工程**：需改 `RequestIDMiddleware` +
   WS handler + ARQ worker `on_job_start` hook + LangGraph `RunnableConfig`
   传递。单独一个 REQ 的工作量，本次仅做 US1 的「单进程内单 trace」基础。
3. **US3 sampling**：默认 100% sampling 已够 dev 用，配置化 sampling rules
   需要设计 `SamplingRule` 抽象 + per-invocation override，单独评估。
4. **US4 exemplars**：prometheus_client 0.25 不原生支持 exemplars（需
   `prometheus-exposition-formats`），且 structlog 加 trace_id 已是基础 join key。

**partial 不影响 SC-001**：SC-001 要求「一次 interview 调用产生 ≥5 node spans +
≥5 LLM spans」—— 本次 interview graph 5 个节点 + MockLLMClient 5 次 LLM 调用
即可达成，不需要 US2/US3/US4。

## Key Design Decisions

### D1: 单文件 `tracing.py`

不拆 `_init.py` / `_decorators.py` / `_processors.py`。partial 范围内单文件
~300 行足够；过度拆分增加导入开销。后续 US2 cross-process propagation 时
再拆 `propagators.py`。

### D2: `span()` context manager + `@traced_node` / `@traced_tool` decorator

`span(name, **attrs)` 是底层 context manager，`@traced_node(name)` /
`@traced_tool(name)` 是基于 `span()` 的高阶 decorator，自动记录 entry/exit +
error status + duration。decorator 形式接入 graph 节点最小侵入（节点函数主体不动）。

### D3: `TracingConfig` dataclass + `init_tracing(config)`

显式 config 对象（不依赖 env var 直接读）—— env var 在 `lifespan` 入口解析
成 `TracingConfig`，再调 `init_tracing(config)`。这样：
- 测试可直接构造 `TracingConfig(exporter="in_memory")` 注入 `InMemorySpanExporter`
- 生产走 env var → config → init
- 不用 monkeypatch env var

### D4: `BatchSpanProcessor` + fail-open

`BatchSpanProcessor` 异步 flush，主路径不阻塞。`OTLPSpanExporter.export()` 失
败时 BatchSpanProcessor 内部 log + drop（不 raise）。再加一层：`init_tracing`
本身 try/except，任何 OTel init 异常 → log warning + 退化为 noop tracer
（`trace.get_tracer()` 返回的默认 tracer 不发 span）。**FR-017 fail-open 达成**。

### D5: structlog processor 加 `trace_id` + `span_id`

新增 `_inject_otel_context` processor（在 `_inject_context` 之后），读 OTel
`trace.get_current_span()` 的 context，注入 `trace_id` + `span_id` 到 event dict。
- 有 span → 注入 hex trace_id + span_id
- 无 span → 不注入（不污染非 trace 路径的日志）

### D6: `@traced_node` 装饰 async 函数

`functools.wraps` + `inspect.iscoroutinefunction` 判断 async / sync 路径。
graph 节点都是 async，但 `_planner_complete_node` 是 sync —— decorator 必须两
种都支持。

### D7: 不 wrap `_planner_complete_node`

planner subgraph 的 `load_context / planner_search / planner_generate` 三个
节点暂不加 `@traced_node`（partial scope，interview graph 主线 5 节点足够达成
SC-001 的 ≥5 node spans）。如果加上，span 数会更多但 US1 验收已满足。

### D8: `record_llm_span_attributes(span, **attrs)` helper

LLM client 调用前后需要分别记录（前置 model/estimated_tokens，后置 actual_tokens/
duration/retry_count）。用 helper 函数避免分散的 `span.set_attribute()` 调用。

### D9: `MockLLMClient` 也发 span（FR-018）

`MockLLMClient.invoke` 内加 `span("llm.invoke", node_name=..., model="mock-llm")`，
这样 trace 测试不需真 DeepSeek。tokens 都为 0（mock 不计 token）—— span 仍
记录 model + latency。

### D10: `traced_tool` 不记录 args / return 全文（PII）

`@traced_tool("tavily_search")` 只记录 `tool_name` + `duration_ms` + `args_summary`
（截断 100 字）+ `result_summary`（截断 100 字）。用户 free-text answer 不进
span attributes（FR-016 基础 redaction）。完整 PII redaction ⏳ 后续。
