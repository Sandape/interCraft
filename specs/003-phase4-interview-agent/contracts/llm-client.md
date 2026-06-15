# 统一 LLM 客户端接口 (M14) — DeepSeek V4 Pro

> Phase 4 统一 LLM 客户端:通过 OpenAI 兼容协议调用 DeepSeek V4 Pro(`deepseek-chat`),集中处理速率限制、自动重试、token 配额预扣/实扣、结构化日志。
> 
> **决议 2026-06-13**:使用 DeepSeek V4 Pro + OpenAI 协议,所有节点统一模型,API key 保存在 `backend/.env`。

## 接口定义

```python
# backend/app/agents/llm_client.py

class LLMClient:
    """统一 LLM 客户端。单例,通过 OpenAI 兼容协议调用 DeepSeek V4 Pro。"""

    def __init__(self):
        self._client = openai.AsyncOpenAI(
            base_url=os.environ["DEEPSEEK_BASE_URL"],  # https://api.deepseek.com/v1
            api_key=os.environ["DEEPSEEK_API_KEY"],
        )
        self._model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    async def invoke(
        self,
        *,
        messages: list[dict[str, str]],     # OpenAI message format: [{"role": "...", "content": "..."}]
        estimated_tokens: int,              # 预估消耗 token 数
        user_id: str,                       # 用于配额预扣
        thread_id: str,                     # 用于日志关联
        node_name: str,                     # 调用来源节点名称
        checkpoint_id: str | None,          # 关联 checkpoint
        max_retries: int = 3,               # 最大重试次数
        timeout_ms: int = 30_000,           # 单次调用超时
        stream: bool = False,               # 是否流式返回
    ) -> LLMResponse:
        """
        调用 DeepSeek V4 Pro,执行:
        1. token 配额预扣(原子 SELECT...FOR UPDATE)
        2. DeepSeek API 调用(OpenAI 协议,含重试)
        3. token 配额实扣(按实际 usage 调整)
        4. 结构化日志 + ai_messages 写入
        5. Prometheus 指标更新
        """
        ...

    async def invoke_stream(
        self, *, messages, estimated_tokens, user_id, thread_id, node_name, ...
    ) -> AsyncIterator[TokenDelta]:
        """流式版本:yield token.delta 片段,WS 直接推送。"""
        ...

class LLMResponse(TypedDict):
    content: str                     # LLM 返回内容(非流式完整文本)
    model: str                       # deepseek-chat
    prompt_tokens: int               # 输入 token 数
    completion_tokens: int           # 输出 token 数
    duration_ms: int                 # 调用耗时
    checkpoint_id: str | None        # 关联的 checkpoint
```

## 预扣/实扣流程

```
invoke(messages, estimated_tokens=2500)
  │
  ├── 1. 预扣检查
  │   SELECT monthly_token_used, monthly_token_quota
  │   FROM users WHERE id = :user_id FOR UPDATE
  │   IF used + estimate > quota:
  │     RAISE QuotaExceededError
  │   UPDATE users SET monthly_token_used = monthly_token_used + estimate
  │
  ├── 2. DeepSeek API 调用(OpenAI 协议)
  │   self._client.chat.completions.create(
  │     model="deepseek-chat",
  │     messages=messages,
  │     stream=True/False,
  │     timeout=30,
  │   )
  │   response.usage.prompt_tokens, response.usage.completion_tokens
  │
  ├── 3. 实扣调整
  │   actual = prompt_tokens + completion_tokens
  │   UPDATE users SET monthly_token_used = monthly_token_used - estimate + actual
  │
  ├── 4. 写入 ai_messages
  │   INSERT INTO ai_messages (user_id, thread_id, checkpoint_id, node_name,
  │     role, model, prompt_tokens, completion_tokens, duration_ms, occurred_at)
  │
  └── 5. 返回 LLMResponse
```

## 重试策略

OpenAI SDK 内置 retry,配置 `max_retries=3`:

| 错误类型 | 重试 | 退避 | 最大次数 |
|---|---|---|---|
| `RateLimitError`(429) | ✅ | SDK 内置 jitter | 3 |
| `APITimeoutError` | ✅ | SDK 内置 | 3 |
| `APIConnectionError` | ✅ | SDK 内置 | 3 |
| `InternalServerError`(500) | ✅ | SDK 内置 | 3 |
| `BadRequestError`(400) | ❌ | — | — |
| `AuthenticationError`(401) | ❌ | — | — |

重试耗尽后:抛出 `LLMInvokeError`,记录 structured error log,前端收到 WS `error` 事件(code=`llm_timeout` 或 `internal_error`)。

## Token 估算表(DeepSeek 单模型)

| 节点 | Model | 预估 input | 预估 output | 合计 |
|---|---|---|---|---|
| intake | deepseek-chat | 500 | 200 | 700 |
| question_gen | deepseek-chat | 2000 | 500 | 2500 |
| score | deepseek-chat | 1500 | 300 | 1800 |
| report | deepseek-chat | 4000 | 1500 | 5500 |

**一场面试总计**:(700 + 5×2500 + 5×1800 + 5500) = 27,700 tokens(估算)

```python
# TokenEstimator
NODE_TOKEN_ESTIMATES = {
    "intake": 700,
    "question_gen": 2500,
    "score": 1800,
    "report": 5500,
}
```

## 环境变量

```bash
# backend/.env
DEEPSEEK_API_KEY=sk-5053a1a6d1d146f0ab02aa020637155d
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
MONTHLY_TOKEN_QUOTA=500000
```

## 指标

每次调用更新 Prometheus:

```text
# Counter
llm_invoke_total{model="deepseek-chat", node, result}       # success / error / rate_limited / quota_exceeded
llm_token_consumed_total{model="deepseek-chat", type}       # input / output

# Histogram
llm_invoke_duration_seconds{model="deepseek-chat", node}    # P50/P95/P99
```

## 结构化日志

每次调用记录(通过 structlog):

```json
{
  "event": "llm.invoke",
  "request_id": "uuid",
  "user_id": "uuid",
  "thread_id": "uuid",
  "node_name": "question_gen",
  "model": "deepseek-chat",
  "estimated_tokens": 2500,
  "actual_tokens": 2317,
  "prompt_tokens": 1942,
  "completion_tokens": 375,
  "duration_ms": 1247,
  "retry_count": 0,
  "result": "success"
}
```
