# M14 · LangGraph 基础设施(超核心模块)

> 状态: draft · 所属领域: E · 优先级: P0
> 引用原文档: §2.3, §3.5, §7.3, §15, §16, §17

## 1. 需求摘要

**整个 AI 编排体系的地基**。落地:
1. **PostgresCheckpointer** 安装与初始化
2. **state.py / runtime.py** 统一封装,所有子图通过 `runtime.astream()` 进入
3. **ToolNode 装饰器** `@tool` + 限流 / 鉴权 / 持锁校验
4. **`tool_call_logs` / `ai_conversations` / `ai_messages`** 业务表写入
5. **WebSocket 数据面** `agent.{thread_id}` 频道(token / node / tool / interrupt 事件)
6. **双源写入 hooks**:节点回调时同步写 ai_messages,与 checkpointer 共享事务策略
7. **断线重连重放**:基于 `last_seen_checkpoint_id`
8. **三层限流**:工具级 / LLM 级 / Graph 级

子图(M15-M19)只负责定义节点与状态,**所有共性能力来自本模块**。

## 2. 验收标准

- [ ] `langgraph-checkpoint-postgres` 安装完成,checkpoint 内部表自动创建(无 Alembic 干预)
- [ ] `PostgresCheckpointer` 单例,所有子图共享
- [ ] `app/agents/state.py` 定义 GraphState TypedDict 基类与各子图特化类型
- [ ] `app/agents/runtime.py` 提供 `run_agent(graph_name, thread_id, input, config)` 统一入口
- [ ] `app/agents/tools/registry.py` `@tool` 装饰器,自动注册 + 限流 + 鉴权 + 持锁校验 + 记录 tool_call_logs
- [ ] 节点回调 `on_node_finished` 钩子:同步写 ai_messages(content AES-GCM 加密)
- [ ] `ai_conversations` 表落地(含 graph_name / graph_version)
- [ ] `ai_messages` 表落地(含 thread_id / checkpoint_ns / checkpoint_id / run_id / node_name,见 §3.2)
- [ ] `tool_call_logs` 表落地
- [ ] WebSocket 数据面 `/ws/agent` + `agent.{thread_id}` 频道,9 个事件全部可推送
- [ ] 断线重连:客户端发 `{type:"resume", last_seen_checkpoint_id}` → 服务端从下一节点开始(参见 A4)
- [ ] 限流装饰器:工具级 Redis token bucket / LLM 级月度 token / Graph 级 50 步上限
- [ ] checkpointer 隔离:每次 put/get 前应用层校验 thread_id ∈ 当前用户(参见 A2)

## 3. 依赖与被依赖关系

**强依赖**: M02(ai_conversations / ai_messages / tool_call_logs 表)、M03(Redis 限流 + 加密)、M05(JWT / RLS)、M11(interview_sessions 关联)
**弱依赖**: M12(共享 WS 基础设施)
**被以下模块依赖**: M15-M19(所有 Agent 子图)、M22(对账 job)
**外部依赖**:
- `langgraph >= 0.2`
- `langgraph-checkpoint-postgres`
- `langchain` + `langchain-openai` / `langchain-anthropic`
- `langsmith`(可选)

## 4. 数据模型

**`ai_conversations` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
context_type TEXT NOT NULL  -- interview / resume_optimize / coach / diagnose
context_id UUID NULL  -- 业务锚点 id
graph_name TEXT NOT NULL  -- A6 决议:与 checkpoint_ns 同名
graph_version TEXT NOT NULL  -- e.g. "1.0.0"
thread_id TEXT NOT NULL  -- A6 决议:派生规则集中在本模块
model TEXT NOT NULL  -- e.g. "claude-sonnet-4-6"
prompt_hash CHAR(64) NULL  -- 提示词版本指纹
status TEXT NOT NULL  -- active / finished / aborted / orphan
started_at TIMESTAMPTZ NOT NULL DEFAULT now()
ended_at TIMESTAMPTZ NULL
created_at / updated_at / deleted_at
```

**约束**:`UNIQUE (thread_id, graph_name)`(A6)

**`ai_messages` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
conversation_id UUID NOT NULL FK(ai_conversations.id)
thread_id TEXT NOT NULL
checkpoint_ns TEXT NOT NULL
checkpoint_id TEXT NOT NULL
run_id UUID NOT NULL  -- LangGraph config["run_id"]
node_name TEXT NOT NULL
role TEXT NOT NULL  -- system / ai / user / tool
content_enc BYTEA NOT NULL  -- AES-256-GCM
content_hash CHAR(64) NULL  -- sha256(plaintext),用于去重 / 对账
tokens_in INT NULL
tokens_out INT NULL
latency_ms INT NULL
created_at  -- immutable
```

**索引**:
- `(thread_id, checkpoint_id, run_id)` 双源对账
- `(conversation_id, created_at)` 消息流分页
- `(user_id, created_at DESC)` 全局历史

**`tool_call_logs` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
run_id UUID NOT NULL
thread_id TEXT NOT NULL
tool_name TEXT NOT NULL
arguments_json JSONB NOT NULL
result_json JSONB NULL
status TEXT NOT NULL  -- success / failed / rate_limited / forbidden
error_code TEXT NULL
latency_ms INT NOT NULL
occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

## 5. 接口契约

**REST**(Agent 入口由 M15-M19 提供;本模块提供查询):
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/agents/{thread_id}/state` | 当前 GraphState 快照(断线恢复) |
| GET | `/api/v1/agents/{thread_id}/checkpoints` | 历史 checkpoint 列表 |

**WebSocket** (`/ws/agent`,JWT 验签 + thread_id 鉴权):
| Channel | 事件 |
|---|---|
| `agent.{thread_id}` | `node.started / node.finished / token.delta / tool.called / tool.returned / interrupt / state.snapshot / error / final` |

**事件 payload**(参见 §10.6):
```json
{
  "event": "node.started",
  "thread_id": "...",
  "graph": "interview",
  "graph_version": "1.0.0",
  "run_id": "uuid",
  "node": "question_gen",
  "ts": "ISO",
  "data": {}
}
```

**Python API**:
```python
# app/agents/runtime.py
async def run_agent(
    graph_name: str,
    thread_id: str,
    input: dict | Command,
    config: RunnableConfig,
) -> AsyncIterator[StreamEvent]:
    compiled = get_compiled_graph(graph_name, config.get("graph_version"))
    async for event in compiled.astream(
        input,
        config={
            **config,
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": graph_name,
            },
        },
    ):
        await on_node_event(event)        # 推 WS
        await mirror_to_ai_messages(event) # 双源写
        yield event

# app/agents/tools/registry.py
@tool(
    name="query_resume_blocks",
    rate_limit=RateLimit(times=100, per_seconds=60),
    requires_user=True,
    requires_lock=LockSpec(resource="resume_branch", key_arg="branch_id"),
)
async def query_resume_blocks(branch_id: UUID, include_inherited: bool = True): ...
```

## 6. 关键设计点

- **PostgresCheckpointer 安装与升级**:
  ```python
  from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
  checkpointer = AsyncPostgresSaver.from_conn_string(DSN)
  await checkpointer.setup()  # 启动时跑一次
  ```
- **graph_name = checkpoint_ns**:统一约定,简化 thread 路由
- **thread_id 派生集中管理**(A6):
  ```python
  def derive_thread_id(graph: str, ctx: dict) -> str:
      if graph == "interview": return str(ctx["session_id"])
      if graph == "ability_diagnose": return f"{ctx['session_id']}::diagnose"
      if graph == "resume_optimize": return str(ctx["branch_id"])
      if graph == "error_coach": return f"{ctx['user_id']}:{ctx['error_question_id']}:{int(time.time()*1000)}"
      if graph == "general_coach": return str(uuid7())
  ```
- **双源 hooks**:节点回调里 INSERT ai_messages,与 checkpointer 共享 SQLAlchemy session(同事务),但 checkpointer 内部独立事务(参见 §17.2)→ 接受短期不一致,M22 对账 job 修复
- **断线重连重放策略**(A4 决议):
  - 客户端断线发 `last_seen_checkpoint_id`
  - 服务端 `get_state(thread_id, before=last_seen_checkpoint_id)` → 找到检查点
  - **丢弃**断线节点的 partial tokens,从该 checkpoint 之后的**下一节点**开始重跑
- **限流三层**(§16.3):
  - 工具级:Redis token bucket(`ratelimit:tool:{name}:{user_id}`)
  - LLM 级:`users.monthly_token_used` 预扣
  - Graph 级:进程内计数器,>50 抛 `MaxStepsExceeded`
- **checkpointer 跨用户隔离**(A2):应用层包装,所有 `put/get` 前查 `ai_conversations` 校验 thread_id ∈ user
- **WS 鉴权**:`/ws/agent?token=...&thread_id=...`,服务端校验 thread_id 属于 user
- **graph 热更新**:`graph_version` 灰度,新版本切流入新 thread,旧 thread 跑完老图

## 7. 待澄清

- **[A1]** 双源 / 三源关系 → 本模块按方案 A 实现(`ai_messages` 唯一权威,`interview_messages` 为视图)
- **[A2]** checkpoints RLS → 应用层校验
- **[A4]** token 流重放 → 丢弃断线节点 partial,从下个节点开始
- **[A6]** thread_id 派生 → 本模块集中实现
- **[A14]** WS 事件文档冗余 → 本模块以 §10.6 为权威
- LangSmith 启用(A17):本模块支持开关,默认关闭

## 8. 实现提示

- 文件:
  - `backend/app/agents/state.py`
  - `backend/app/agents/runtime.py`
  - `backend/app/agents/checkpoint.py`
  - `backend/app/agents/tools/registry.py`
  - `backend/app/agents/tools/{query_resume,query_jd,record_score,...}.py`(具体工具)
  - `backend/app/api/v1/ws_agent.py`
  - `backend/app/services/ai_message_writer.py`(双源 hook)
  - `backend/app/domain/{ai_conversations,ai_messages,tool_call_logs}.py`
- 复用: M02 ORM、M03 加密 / 限流 / Redis、M12 WS 基础(可共享 connection registry)
- 与 mockData 关系: 无(全新引入)
