# Prompt Caching & Token Cost Engineering (032 / spec 027-prompt-caching-cost)

Self-contained library for prompt 分层 + cache hit observability.

## Purpose

DeepSeek V4 Pro 支持 context caching（前缀稳定可降 60-90% 输入成本）。本库
提供 prompt 分层抽象，让 LLMClient 把 messages 分为 stable prefix（system
prompt + tool defs + resume snapshot + requirements）+ dynamic tail（user
message + current question + scores），接入 DeepSeek cache 协议降本。

## Public API

### `PromptLayer`

```python
from app.agents.prompt_caching import PromptLayer

layer = PromptLayer()
layered = layer.prepare(
    system_prompt="You are an interviewer.",
    tool_defs=[{"type": "function", "function": {"name": "search", ...}}],
    snapshot="Resume snapshot (no PII)",
    requirements="Job requirements (no PII)",
    dynamic_messages=[{"role": "user", "content": "user free-text answer"}],
    node="intake",
)
# layered.messages → OpenAI-format messages, stable prefix first, dynamic tail last
# layered.prefix.prefix_hash → SHA256 of stable prefix
# layered.prefix.component_hashes → per-component SHA256 for diagnosis
# layered.stable_token_count → estimated tokens in stable prefix
# layered.dynamic_token_count → estimated tokens in dynamic tail
```

### `CachePrefix`

```python
@dataclass(frozen=True)
class CachePrefix:
    prefix_hash: str           # aggregate SHA256 of all component hashes
    component_hashes: dict[str, str]  # {system_prompt, tool_defs, snapshot, requirements}
    node: str
    version: str = "v1"        # bump to invalidate all cached prefixes
```

### `CacheHitRecord`

```python
@dataclass(frozen=True)
class CacheHitRecord:
    trace_id: str              # OTel trace id
    node: str
    prefix_hash: str
    hit: bool                  # True if cache hit on stable prefix
    cached_tokens: int         # input tokens served from cache
    uncached_tokens: int       # input tokens NOT served from cache
    miss_reason: str | None    # None on hit; "first-call"/"prefix-changed"/...
    cost_saved: int            # tokens saved by caching
```

### `record_cache_hit(record, *, graph, user_id)`

记录 cache hit/miss 到 prometheus counter + structlog log。永不抛异常
（graceful fallback, FR-008）。

```python
from app.agents.prompt_caching import record_cache_hit, CacheHitRecord

record = CacheHitRecord(
    trace_id="trace-1",
    node="intake",
    prefix_hash=layered.prefix.prefix_hash,
    hit=True,
    cached_tokens=1500,
    uncached_tokens=200,
    miss_reason=None,
    cost_saved=1500,
)
record_cache_hit(record, graph="interview", user_id="user-uuid")
```

### `serialize_tool_definitions(tool_defs)`

工具定义按 tool name alphabetical 序列化（FR-002）。添加新 tool 不会
reorder 现有 tool，cache prefix 稳定。

### `build_cache_control_headers(prefix)` / `build_cache_control_segments(prefix)`

DeepSeek V4 context caching 协议抽象层。**US1 placeholder** —— emit prefix
hash + segment markers 作为 diagnostic。真实协议（cache_control header /
segment marker）在 plan 阶段验证后接入，签名不变。

## DeepSeek V4 Context Caching 协议说明

DeepSeek V4 Pro 支持 context caching：稳定前缀自动缓存，后续调用用相同
前缀可获输入 token 折扣（60-90% 降本）。

**具体协议**（cache_control header / segment marker / prefix hash）在 plan
阶段验证。本次 US1 用 placeholder：

- `build_cache_control_headers()` 返回 `{"X-InterCraft-Prefix-Hash": <hash>,
  "X-InterCraft-Cache-Version": "v1"}`
- `build_cache_control_segments()` 返回 `[{component, hash, cacheable}, ...]`
  per stable component

LLMClient `_call_deepseek` 集成时（⏳ working tree）把 headers 加到 request，
segments 加到 messages metadata。真实协议验证后替换 placeholder，签名不变。

## PII 隔离 (FR-005)

**Caller responsibility** —— `PromptLayer.prepare()` 不检测 PII（regex 不可靠，
PII 形式多样）。Caller 必须把 user free-text 放在 `dynamic_messages`，**不**
放进 `snapshot` / `requirements` / `system_prompt`。

测试 `test_pii_stays_in_dynamic_tail_not_in_prefix` assert user free-text 放
在 `dynamic_messages` 后，stable prefix 中不含 user free-text。

## Observability (Constitution V)

### Prometheus Counters

| Counter | Labels | Description |
|---------|--------|-------------|
| `llm_cache_hit_total` | node, graph, result(hit\|miss) | cache hit/miss count (FR-014) |
| `llm_cache_cached_tokens_total` | node, graph | cached input tokens (FR-014) |
| `llm_cache_uncached_tokens_total` | node, graph | uncached input tokens (FR-014) |
| `llm_cache_discount_tokens_total` | user_id, graph | cache discount (tokens saved) (FR-016) |

### Structlog Log Events

| Event | Fields | When |
|-------|--------|------|
| `llm.cache.hit` | trace_id, node, graph, prefix_hash, cached_tokens, uncached_tokens, cost_saved, user_id | cache hit |
| `llm.cache.miss` | trace_id, node, graph, prefix_hash, cached_tokens, uncached_tokens, miss_reason, user_id | cache miss (FR-015) |
| `llm.cache.metric_failed` | counter, exc_info | prometheus counter inc failed (best-effort) |

`miss_reason` 取值（FR-015）：
- `first-call`: 首次调用该 prefix（无 cache entry）
- `prefix-changed`: prefix 变了（snapshot 更新等）
- `ttl-expired`: cache entry 过期（provider TTL 默认分钟级）
- `provider-cache-unavailable`: provider cache API 不可用（FR-008 graceful fallback）

## Usage Example (LLMClient 集成点 ⏳ working tree)

```python
from app.agents.prompt_caching import PromptLayer, record_cache_hit, CacheHitRecord

# In LLMClient.invoke (⏳ working tree, follows 024 landing):
layer = PromptLayer()
layered = layer.prepare(
    system_prompt=system_prompt,
    tool_defs=tool_defs,
    snapshot=snapshot,
    requirements=requirements,
    dynamic_messages=dynamic_messages,
    node=node_name,
)

# Call DeepSeek with cache-control headers (US1 placeholder)
headers = build_cache_control_headers(layered.prefix)
response = await self._call_deepseek(
    messages=layered.messages,
    model=model,
    extra_headers=headers,
    ...
)

# Construct cache hit record from response (DeepSeek V4 cache fields ⏳ verified)
record = CacheHitRecord(
    trace_id=trace_id,
    node=node_name,
    prefix_hash=layered.prefix.prefix_hash,
    hit=bool(response.usage.cached_tokens),  # ⏳ DeepSeek V4 field name
    cached_tokens=response.usage.cached_tokens or 0,  # ⏳
    uncached_tokens=response.usage.prompt_tokens - (response.usage.cached_tokens or 0),
    miss_reason=None if response.usage.cached_tokens else "first-call",
    cost_saved=response.usage.cached_tokens or 0,
)
record_cache_hit(record, graph="interview", user_id=user_id)
```

## ⏳ Deferred Items

- **US2 quota model**（cached/uncached rate 计价，FR-010/011/012/013）——
  需改 LLMClient `_pre_deduct` / `_actual_adjust` + 新 `PricingConfig` 表 +
  Alembic migration
- **US3 frontend quota display**（raw vs effective tokens，FR-013）—— 需改
  前端 Settings 页
- **US4 eval suite cache hit regression**（FR-018）—— 依赖 026 eval suite
  扩展
- **DeepSeek V4 context caching 协议完整验证**（cache_control header /
  segment marker）—— 本次用 placeholder，plan 阶段验证后接入
- **5 graph 全集成** —— interview graph 集成点在 working tree（⏳）；
  resume_optimize / ability_diagnose / general_coach / error_coach ⏳
- **LLMClient 集成点**（在 `invoke` 内调 `PromptLayer.prepare()` +
  `record_cache_hit()`）—— `llm_client.py` working tree M 状态（024 遗留），
  跟随 024 落地，不入 commit
- **MockLLMClient `cache_mode` 参数**（FR-017 production mock）——
  `llm_client_mock.py` working tree M 状态；FR-017 由测试 local stub
  `_CacheSimulatingClient`（在 `tests/unit/test_prompt_caching.py`）满足
