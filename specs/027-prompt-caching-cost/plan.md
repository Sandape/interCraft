# Implementation Plan: Prompt Caching & Token Cost Engineering

**Branch**: `027-prompt-caching-cost` | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-prompt-caching-cost/spec.md`

## Summary

把 `LLMClient` 的 prompt 分层（system / tools / snapshot / requirements 稳定前缀
+ dynamic tail），接入 DeepSeek V4 Pro context caching，降本 60-90%。本次
**partial 实现**：

- **US1 核心**（P1）：prompt 分层 + cache hit observability ——
  - 新自包含库 `backend/app/agents/prompt_caching/`（Constitution I）
  - `PromptLayer.prepare()` 把 messages 分为 stable prefix（system prompt +
    tool defs + resume snapshot + requirements）+ dynamic tail（user message +
    current question + scores），按 OpenAI messages 格式组装（FR-001）
  - `CachePrefix` dataclass：prefix hash + component hashes（system prompt /
    tool defs / snapshot / requirements）+ node + version（FR-009）
  - `CacheHitRecord` dataclass：per-invocation cache outcome（trace id / node /
    prefix hash / hit-miss / cached tokens / uncached tokens / miss reason /
    cost saved）（FR-007）
  - tool definitions 序列化：alphabetical by tool name（FR-002，添加 tool
    不 reorder 现有）
  - PII 不进 prefix：caller 责任，文档 + 测试 assert user free-text 不在
    stable components 中（FR-005）
  - graceful fallback：provider cache API unavailable → uncached invocation +
    structured warning（FR-008）
  - DeepSeek V4 context caching 协议抽象层：`build_cache_control_headers()`
    + `build_cache_control_segments()`，本次用 placeholder（emit prefix hash
    + log），具体协议（cache_control header / segment marker / prefix hash）
    在 plan 阶段验证后接入（FR-006）
- **基础测试** —— PromptLayer 分层 unit + prefix hash 稳定性 unit + tool
  alphabetical 序列化 unit + CacheHitRecord 持久化 unit + cache simulation
  stub（`_CacheSimulatingClient`，FR-017）
- **observability** —— prometheus counter（cache hit rate per node + per
  graph，FR-014）+ cache miss log with prefix hash + miss reason（structlog，
  FR-015）+ cache discount applied counter per user + per graph（FR-016）

**⏳ 标记后续（不在本 partial 范围）**：

- **US2 quota model**（cached/uncached rate 计价，FR-010/011/012/013）——
  需改 LLMClient `_pre_deduct` / `_actual_adjust` + 新 `PricingConfig` 表，
  范围大，单独一个 REQ
- **US3 frontend quota display**（raw vs effective tokens，FR-013）—— 需改
  前端 Settings 页，范围大
- **US4 eval suite cache hit regression**（FR-018，026 eval suite 检测 cache
  hit rate drop）—— 依赖 026 eval suite 扩展
- **DeepSeek V4 context caching 协议完整验证**（cache_control header /
  segment marker）—— 本次用 placeholder 抽象层，plan 阶段验证后接入
- **5 graph 全集成 prompt 分层** —— US1 只做 interview graph 集成点（
  working tree M 文件，跟随 024 落地），其余 4 graph ⏳
- **LLMClient 集成点**（在 invoke 内调 `PromptLayer.prepare()`）——
  `llm_client.py` / `token_estimator.py` / `llm_client_mock.py` 在 working
  tree 是 M 状态（024 遗留），按 CLAUDE.md 不动 working tree M 文件。本次
  实现：prompt_caching 模块自包含 + 测试独立 commit；LLMClient 集成点留
  working tree 跟随 024 落地，不入 commit。跟 029 OTel / 031 A2A 同策略。

**关键约束**：
- 不破坏现有 LLMClient：`invoke` / `invoke_stream` 现有逻辑保留（pre-deduct
  + retry + actual-adjust），prompt 分层作为新增层在 invoke 前处理 messages
- MockLLMClient 兼容：mock client 加 cache_mode 参数（always_hit /
  always_miss / realistic），测试不依赖真实 DeepSeek
- L004 api-quota-risk：本次范围收窄到 US1 + interview graph。其余 4 graph
  集成 ⏳。如果 DeepSeek cache 协议验证卡住，用 placeholder（emit prefix
  hash + log，不真调 cache API），标 ⏳ 后续验证
- Constitution I (Library-First)：prompt_caching 模块自包含，有 README 描述
  PromptLayer / CachePrefix / CacheHitRecord + DeepSeek V4 cache 协议说明
- Constitution III (Test-First)：PromptLayer 分层 + hash 稳定性 + tool
  alphabetical 序列化先写测试再实现
- Constitution V (Observability)：cache hit rate + miss reason + discount
  applied 全结构化日志 + prometheus

## Technical Context

**Language/Version**: Python 3.12（项目要求 `>=3.11`，实际 venv 3.12.7）。

**Primary Dependencies**:
- 保留：FastAPI、LangGraph 0.2、openai、pydantic 2.13、structlog、
  prometheus_client、`app.observability`（029 OTel tracing）。
- 不新增依赖（prompt_caching 用 stdlib `hashlib` + `json` + prometheus_client
  已有）。

**Storage**: 不新增 DB 表（US1 scope：cache hit record 通过 prometheus
counter + structlog 暴露；US2 ⏳ 才需 `QuotaLedger` / `PricingConfig` 表）。

**Testing**: pytest（prompt_caching 专项单测在
`backend/tests/unit/test_prompt_caching.py`）。

**Target Platform**: Linux server (CI) + dev 本地（Windows + bash）。

**Project Type**: Library（`backend/app/agents/prompt_caching/`）+ LLM client
集成点（⏳ working tree）+ prometheus counter + structlog log event。

**Performance Goals**: PromptLayer.prepare() ≤ 1ms（SHA256 + JSON dump，纯
CPU，无 IO）。prefix hash 计算不影响 invoke 主路径延迟。

**Constraints**:
- 不改 LLM client 契约（`invoke` / `invoke_stream` 签名不变；集成点在
  invoke 内调 `PromptLayer.prepare()`，但本次留 working tree 不入 commit）
- 不改 API 契约（无新 endpoint）
- 不改 graph 业务节点逻辑（interview graph 节点主体不动；集成点是节点
  调 `client.invoke()` 前组装 messages 时用 `PromptLayer.prepare()`）
- 既有 716 测试零回归
- PII 不进 prefix（FR-005，caller responsibility）

**Scale/Scope**: 本次实现 prompt_caching 自包含库 + 专项测试；interview
graph 集成点 + LLMClient 集成点留 working tree（⏳）。其余 4 graph 集成
⏳ 后续。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ Pass | `backend/app/agents/prompt_caching/` 自包含库：`layer.py` 单文件 export `PromptLayer` / `LayeredPrompt` / `CachePrefix` / `CacheHitRecord` / `serialize_tool_definitions` / `compute_prefix_hash` / `record_cache_hit` / `build_cache_control_headers` / `build_cache_control_segments`。无 DB / FastAPI 直接依赖（prometheus + structlog 是 stdlib-grade）。LLMClient + 5 graph 后续接入时仅 import 这个库。README.md 描述 PromptLayer / CachePrefix / CacheHitRecord + DeepSeek V4 cache 协议说明。 |
| II. CLI Interface | ✅ Pass | 测试用 `PromptLayer().prepare(system_prompt=..., tool_defs=..., ...)` 直接调用，返回 `LayeredPrompt` 对象可 inspect（`messages` / `prefix.prefix_hash` / `stable_token_count`）。CI 跑 `uv run pytest tests/unit/test_prompt_caching.py -q`。 |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | TDD：先写 `test_prompt_caching.py`（PromptLayer 分层 + hash 稳定性 + tool alphabetical 序列化 + PII 隔离 + CacheHitRecord + cache simulation stub FR-017）再实现。 |
| IV. Integration & Synchronization Testing | ✅ Pass | cache simulation stub（`_CacheSimulatingClient`）模拟 cache hit/miss 行为，验证 first-call miss → second-call hit → prefix-changed miss 三条路径，不需真 DeepSeek。 |
| V. Observability | ✅ Pass | prometheus counter（cache hit rate per node + per graph，FR-014）+ structlog miss log with prefix hash + miss reason（FR-015）+ cache discount counter per user + per graph（FR-016）。 |

**Gate Result**: PASS — 无违规项，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/027-prompt-caching-cost/
├── plan.md              # This file
├── tasks.md             # Phase 2 output
├── spec.md              # Existing
└── checklists/          # Existing
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── agents/
│   │   ├── prompt_caching/             # 新增: 自包含 prompt 分层 + cache 库 (Constitution I)
│   │   │   ├── __init__.py              # 公共 API re-exports
│   │   │   ├── layer.py                 # PromptLayer + CachePrefix + CacheHitRecord + metrics
│   │   │   └── README.md               # Constitution I: library 描述 + DeepSeek V4 cache 协议
│   │   ├── llm_client.py                # 修改 (working tree ⏳): invoke 内调 PromptLayer.prepare()
│   │   ├── llm_client_mock.py           # 修改 (working tree ⏳): 加 cache_mode 参数 (FR-017)
│   │   └── token_estimator.py           # 修改 (working tree ⏳): per-node token estimate 反映 post-cache
│   └── core/
│       └── metrics.py                   # 修改: 加 cache hit/discount counters (re-export from prompt_caching)
└── tests/
    └── unit/
        └── test_prompt_caching.py      # 新增: PromptLayer + CachePrefix + CacheHitRecord + cache simulation
```

**Structure Decision**: 单文件 `layer.py` 而非拆 `__init__.py / _prefix.py /
_hit_record.py / _metrics.py`。027 US1 partial 范围内单文件 ~400 行足够，
过度拆分反而增加导入开销；后续 US2 quota model 时再拆 `quota.py` +
`pricing.py`。

## Complexity Tracking

> 无 Constitution Check 违规项。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

---

## Partial Scope Justification

**为什么 partial**：

1. **L004 api-quota-risk**：5 graph 全集成 + LLM 调用各跑一遍 cache 验证 =
   至少 35 次 LLM 调用（5 graph × 7 节点平均），单次 pytest 验证可能烧
   100K+ tokens。本次只做 prompt_caching 自包含库 + 专项测试，集成点留
   working tree 不入 commit，避免 quota 耗尽。
2. **US2 quota model 是大工程**：需改 LLMClient `_pre_deduct` /
   `_actual_adjust` 引入 cached/uncached rate 计价 + 新 `PricingConfig` 表
   + Alembic migration + 配置外部化。单独一个 REQ 的工作量。
3. **US3 frontend quota display**：需改前端 Settings 页加 raw vs effective
   tokens 显示 + QuotaLedger API endpoint。范围大，单独评估。
4. **US4 eval suite regression**：依赖 026 eval suite 扩展（添加 cache hit
   rate 检测 case），026 本身是 partial，需先完成 026 US2 eval suite 扩展。
5. **DeepSeek V4 context caching 协议完整验证**：DeepSeek V4 Pro 支持
   context caching（前缀稳定可降 60-90% 输入成本），但具体协议（cache_control
   header / segment marker / prefix hash）在 plan 阶段验证。本次实现先用
   抽象层（`build_cache_control_headers()` + `build_cache_control_segments()`
   placeholder），DeepSeek 协议适配在 `_call_deepseek` 内部，可 placeholder。

**partial 不影响 SC-001/006**：SC-001（cache hit rate ≥60%）需要真 DeepSeek
调用 + interview graph 集成，本次用 cache simulation stub 验证 cache hit/miss
逻辑正确性，SC-001 实测 ⏳ 后续集成验证。SC-006（cache miss with diagnostic
log）本次达成（`record_cache_hit()` 在 miss 时 emit structured log with
prefix hash + miss reason）。

## Key Design Decisions

### D1: 单文件 `layer.py`

不拆 `_prefix.py` / `_hit_record.py` / `_metrics.py` / `_serialization.py`。
partial 范围内单文件 ~400 行足够；过度拆分增加导入开销。后续 US2 quota
model 时再拆 `quota.py` + `pricing.py`。

### D2: `PromptLayer.prepare()` 接受结构化输入，不解析 flat messages

`PromptLayer.prepare(*, system_prompt, tool_defs, snapshot, requirements,
dynamic_messages, node)` 接受结构化参数（caller 显式区分 stable / dynamic），
不解析 flat `messages: list[dict]` 推断哪些是 stable。原因：

- 推断 flat messages 不可靠（system role 可能是 stable 也可能是 dynamic
  tool result；user role 永远是 dynamic 但 caller 可能误传）
- 显式参数让 PII 隔离（FR-005）成为 caller responsibility —— caller 必须把
  user free-text 放在 `dynamic_messages`，不能放进 `snapshot` / `requirements`
- 测试更稳定（不依赖推断启发式）

### D3: `CachePrefix` 用 frozen dataclass + 显式 component_hashes dict

`CachePrefix(prefix_hash, component_hashes, node, version)`：

- `prefix_hash`：聚合 SHA256（所有 component hashes 排序后 `|`-join 再 SHA256）
- `component_hashes`：`{"system_prompt": "...", "tool_defs": "...",
  "snapshot": "...", "requirements": "..."}` —— 每个稳定段单独 SHA256，便于
  miss 诊断（哪个 component 变了）
- `version`：schema 版本（`"v1"`），未来 prompt 分层结构变（加新 component
  类型）时 bump，让 cache 全部失效

frozen dataclass 保证 hashable + 可作为 dict key（cache lookup 用）。

### D4: tool definitions 序列化用 `json.dumps(sort_keys=True)` + 按 tool name 排序

`serialize_tool_definitions(tool_defs)`：

1. 按 tool name 排序（OpenAI tool 格式是 `{"type": "function", "function":
   {"name": "..."}}`，按 `function.name` 排序；plain dict 格式按 `name` 排序）
2. `json.dumps(sorted_defs, sort_keys=True, ensure_ascii=False)` —— 内部
   dict 字段也按 key 排序

这样添加新 tool 不会 reorder 现有 tool 的字段顺序，cache prefix 稳定
（FR-002）。

### D5: `_estimate_tokens()` 用 CJK-friendly 估算（不依赖 tiktoken）

复用 `requirements_block.estimate_tokens()` 同款算法：1 CJK char ≈ 1.5
token，1 ASCII char ≈ 0.25 token。tiktoken 依赖重（~10MB），prompt_caching
库保持 stdlib-only。token 估算只用于 `stable_token_count` /
`dynamic_token_count` 报告，不影响计费（计费用 provider 返回的
`response.usage.prompt_tokens`）。

### D6: DeepSeek V4 cache 协议抽象层（placeholder）

`build_cache_control_headers(prefix)` + `build_cache_control_segments(prefix)`：

- US1 placeholder：emit prefix hash 作为 diagnostic header
  (`X-InterCraft-Prefix-Hash`)，segment markers 用 dict list
- DeepSeek V4 实际协议（cache_control segment marker / prefix hash header）
  验证后接入 —— 这两个函数是集成点，签名不变
- LLMClient `_call_deepseek` 内部调用 `build_cache_control_headers()` 把
  header 加到 request（⏳ working tree）

### D7: `record_cache_hit()` 同步函数，不阻塞 invoke 主路径

`record_cache_hit(record, *, graph, user_id)` 同步更新 prometheus counter
+ emit structlog log event。prometheus_client Counter.inc() 是 O(1) thread-safe
操作，structlog logger.info() 也是 sync（async log 在 structlog 24.x 不原生
支持）。不阻塞 invoke 主路径。

### D8: cache simulation stub（`_CacheSimulatingClient`）独立于 MockLLMClient

`_CacheSimulatingClient` 是测试 local stub（在 `test_prompt_caching.py` 内
定义），不修改 production `MockLLMClient`（working tree M 状态）。验证：

- `cache_mode="realistic"`：first call with prefix_hash X → miss (first-call)；
  second call with same prefix_hash → hit；call with different prefix_hash →
  miss (prefix-changed)
- `cache_mode="always_hit"` / `"always_miss"`：强制 hit/miss，测试 cache
  unavailable fallback（FR-008）

满足 FR-017（cache simulation 可测，不依赖真 provider）。

### D9: PII 隔离靠 caller + 测试 assert

`PromptLayer.prepare()` 不做 PII 检测（regex 不可靠，PII 形式多样）。PII
隔离靠：

- 文档：`PromptLayer.prepare()` docstring 明确 "PII from user input MUST
  NOT appear in `snapshot` / `requirements` / `system_prompt`"
- 测试：`test_pii_stays_in_dynamic_tail` assert user free-text 放在
  `dynamic_messages` 后，stable prefix 中不含 user free-text
- code review：US3 spec FR-005 要求 code review 检查 prompt layering discipline
