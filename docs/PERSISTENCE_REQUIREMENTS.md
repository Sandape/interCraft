# InterCraft 面试工坊 · 持久化需求文档

> 状态: v0.2 · 2026-06-12 (基于 FastAPI + LangGraph 重写架构)
> 范围: 数据从「前端 mock」走向「生产级持久化」的完整契约,含数据模型、生命周期、安全合规、同步策略、LangGraph 多 Agent 架构与接口约束。

---

## 0. 关键决策摘要 (TL;DR)

| # | 决策项 | 结论 |
|---|---|---|
| 1 | 持久化架构 | **前端 + 自建后端** (Python + PostgreSQL) |
| 2 | 账号 & 同步 | **需要账号 + 多端云同步** |
| 3 | 数据敏感度 | **含敏感隐私** (身份证、薪资、面试录音/视频元数据、AI 对话) |
| 4 | 生命周期 | **导入/导出 + 软删除 + 版本审计 + 离线优先** |
| 5 | 二进制资产 | **MVP 暂不实现云存储** (录音/视频仅存元数据与转写稿) |
| 6 | 并发冲突 | **悲观锁** (编辑时锁定) |
| 7 | AI 对话 | **存储完整对话流** |
| 8 | 保留期 | **软删除 30 天清除,账号注销 90 天清除** |
| 9 | 后端运行时 | **Python 3.11+ FastAPI 异步栈** |
| 10 | ORM / 迁移 | **SQLAlchemy 2.0 async + Alembic** |
| 11 | AI 编排 | **LangGraph** (覆盖全部 AI 场景) |
| 12 | AI 状态持久化 | **PostgresCheckpointer + 业务表双源** |

---

## 1. 背景与目标

### 1.1 背景
当前应用已完成 UI/UX 阶段,核心数据使用前端 `mockData.ts` 静态填充。已识别出 7 大数据域:用户、简历分支、简历块、面试历史、错题本、能力画像、任务与活动流,共 12 个页面强依赖。

### 1.2 目标
- 让所有 mock 数据落地为真实可写、可恢复、可审计的持久数据。
- 满足「多端云同步 + 离线可用 + 敏感数据保护 + 数据可移植」四重约束。
- 为后续 AI 能力接入、企业版、协作功能预留干净的数据底座。

### 1.3 非目标
- 不在 MVP 范围:企业多租户、实时多人协作(CRDT)、二进制对象存储、跨地域灾备。

---

## 2. 架构总览

### 2.1 整体架构
```
┌──────────────────────────────┐         ┌──────────────────────────────────┐
│        客户端 (Web)          │         │           自建后端                │
│   React 18 + TypeScript      │         │        Python 3.11+              │
│  ┌────────────────────────┐  │         │  ┌────────────────────────────┐  │
│  │ UI / 状态 (Zustand)    │  │         │  │  FastAPI (Uvicorn 异步)   │  │
│  └──────────┬─────────────┘  │         │  └──────────┬─────────────────┘  │
│  ┌──────────▼─────────────┐  │  HTTPS  │  ┌──────────▼─────────────────┐  │
│  │ 同步引擎 (Outbox)       │◄─┼─────────┼─►│ REST + WebSocket Router    │  │
│  └──────────┬─────────────┘  │  WSS    │  └──────────┬─────────────────┘  │
│  ┌──────────▼─────────────┐  │         │  ┌──────────▼─────────────────┐  │
│  │ IndexedDB (Dexie)      │  │         │  │ Services (业务编排)         │  │
│  │ + 加密封装              │  │         │  └────┬──────────────┬───────┘  │
│  └────────────────────────┘  │         │  ┌────▼─────────┐ ┌──▼────────┐ │
└──────────────────────────────┘         │  │ Repositories │ │ Agents    │ │
                                          │  └──────┬───────┘ │ (LangGraph│ │
                                          │  ┌──────▼─────────────────┐  │ │
                                          │  │ SQLAlchemy 2.0 async     │  │ │
                                          │  │  + asyncpg + Alembic    │  │ │
                                          │  └──────┬─────────────────┘  │ │
                                          │  ┌──────▼─────────────────┐  │ │
                                          │  │ PostgreSQL 15            │  │ │
                                          │  │  + 业务表 + checkpoints  │  │ │
                                          │  │  + RLS + 列加密          │  │ │
                                          │  └──────┬─────────────────┘  │ │
                                          │  ┌──────▼─────────────────┐  │ │
                                          │  │ Redis (锁/Pub-Sub/ARQ)  │  │ │
                                          │  └────────────────────────┘  │ │
                                          │  ┌─────────────────────────┐  │ │
                                          │  │ ARQ Workers (异步任务)  │  │ │
                                          │  └─────────────────────────┘  │ │
                                          └──────────────────────────────────┘
```

### 2.2 推荐技术栈
| 层 | 选型 | 理由 |
|---|---|---|
| 客户端状态 | Zustand + React Query | 轻量、对离线缓存友好 |
| 客户端存储 | IndexedDB (Dexie.js) | 大容量、事务、版本迁移 |
| 客户端同步 | Workbox + 自研 outbox 队列 | 离线写先入队,联网后批量回放 |
| 运行时 | Python 3.11+ (uv 包管理) | 与 LangGraph / LangChain 生态原生兼容 |
| Web 框架 | FastAPI + Uvicorn | 异步、Pydantic 校验、自动 OpenAPI |
| ORM | SQLAlchemy 2.0 async + asyncpg | 类型安全、异步友好、成熟生态 |
| 迁移 | Alembic | SQLAlchemy 官方迁移工具 |
| 鉴权 | fastapi-users (推荐) 或自研 JWT | OAuth/JWT/密码哈希全套方案 |
| API 风格 | REST + OpenAPI 3.1 | 易调试、工具链成熟 |
| 实时通道 | WebSocket (uvicorn 原生 + Redis Pub/Sub) | 控制面/Agent 数据面共用,横向扩展 |
| 后台任务 | ARQ (基于 Redis) | 异步友好、轻量、优于 Celery |
| AI 编排 | LangGraph + langgraph-checkpoint-postgres | 多 Agent 状态图、checkpointer 原生持久化 |
| LLM 客户端 | LangChain (langchain-openai / langchain-anthropic) | 与 LangGraph 紧集成 |
| 工具注册 | LangChain Tools + 自研 @tool 装饰器 | 标准化 Tool 接口 |
| 加密 | cryptography (AES-256-GCM) / pgcrypto | 敏感字段应用层加密 |
| 可观测 | OpenTelemetry + LangSmith / OpenInference | LangGraph trace 标准化 |
| 测试 | pytest + pytest-asyncio + LangGraph graph snapshot | 单元 / 异步 / Agent 行为测试 |
| 部署 | Docker + Docker Compose | MVP 不上 K8s |

### 2.3 后端模块划分
```
backend/
├── app/
│   ├── main.py                    # FastAPI app 入口
│   ├── api/
│   │   └── v1/                    # REST + WS 路由 (按域分文件)
│   │       ├── auth.py
│   │       ├── resumes.py
│   │       ├── interviews.py
│   │       ├── agents.py          # LangGraph 子图入口
│   │       └── ws.py              # WebSocket 路由
│   ├── core/                      # config / security / db / redis / deps
│   ├── domain/                    # SQLAlchemy 领域模型 (与 §3 实体一一对应)
│   ├── schemas/                   # Pydantic 入参出参
│   ├── repositories/              # 仓储层 (聚合根隔离)
│   ├── services/                  # 业务编排 (不依赖 LangGraph)
│   ├── agents/                    # ⭐ LangGraph 子系统
│   │   ├── graphs/                # 图定义 (各子图一个文件)
│   │   │   ├── interview.py
│   │   │   ├── resume_optimize.py
│   │   │   ├── ability_diagnose.py
│   │   │   ├── error_coach.py
│   │   │   └── general_coach.py
│   │   ├── nodes/                 # 节点函数 (按子图分子目录)
│   │   ├── tools/                 # Tool 实现 (见 §16)
│   │   ├── state.py               # GraphState TypedDict 集中定义
│   │   ├── checkpoint.py          # PostgresCheckpointer 单例
│   │   └── runtime.py             # Agent runtime 封装 (astream / ainvoke)
│   ├── workers/                   # ARQ 任务 (对账 / 归档 / 通知)
│   └── observability/             # OTel / LangSmith 接入
├── migrations/                    # Alembic
├── tests/
│   ├── unit/
│   ├── integration/
│   └── agents/                    # LangGraph 图行为测试
├── pyproject.toml                 # uv 依赖
└── docker-compose.yml
```

---

## 3. 领域数据模型

### 3.1 实体关系总览
```
                        ┌─────────────┐
                        │   User      │ 1
                        └──────┬──────┘
                               │ *
        ┌──────────────┬───────┼────────┬──────────────┬──────────────┐
        │ *            │ *     │ *      │ *            │ *            │
   ┌────▼────┐   ┌─────▼───┐ ┌─▼──────┐ ┌▼──────────┐ ┌▼──────────┐  ┌▼────────┐
   │ Resume  │   │Interview│ │ ErrorQ │ │ Ability   │ │ Task      │  │Activity │
   │ Branch  │1  │  History│ │ (错题) │ │ Dimension │ │ (任务)    │  │ (动态)  │
   └────┬────┘   └────┬────┘ └────────┘ └───────────┘ └───────────┘  └─────────┘
        │ *           │ *
        ▼             ▼
   ┌─────────┐   ┌──────────┐
   │ Resume  │   │ Interview│
   │ Block   │   │ Session  │
   │ (块)    │   │ (进行中) │
   └─────────┘   └──────────┘
        ▲             ▲
        │             │
        └────── 共享悲观锁 (Redis SETNX) ──────┘
```

### 3.2 核心实体清单

| 实体 | 主键 | 关键字段 | 备注 |
|---|---|---|---|
| `users` | `id (uuid)` | email, phone, display_name, password_hash, status, llm_provider_pref (jsonb), monthly_token_quota (int), monthly_token_used (int) | status: active / soft_deleted / purged;llm 偏好与配额 |
| `user_credentials` | `user_id` | id_card_enc, salary_range_enc, real_name_enc | AES-256-GCM 加密 |
| `resume_branches` | `id (uuid)` | user_id, parent_id, name, company, position, status, match_score, is_main, is_pinned | 支持父子继承 |
| `resume_blocks` | `id (uuid)` | branch_id, type, title, content, order_index, collapsed | Notion 式块,顺序敏感 |
| `resume_versions` | `id (uuid)` | branch_id, snapshot_json, version_no, author_type (user/ai) | 完整快照 + 差异 |
| `interview_sessions` | `id (uuid)` | user_id, company, position, mode (text/voice), status (active/finished/aborted), started_at, thread_id (text) | 悲观锁目标;thread_id 对应 LangGraph thread |
| `interview_messages` | `id (uuid)` | session_id, role (ai/user/system), content, timestamp, audio_ref | 完整对话流(供前端展示,与 ai_messages 互补) |
| `interview_reports` | `id (uuid)` | session_id, total_score, dimensions_json, ai_summary | 终结时由 ability_diagnose 子图生成 |
| `error_questions` | `id (uuid)` | user_id, question, category, frequency, last_missed_at, difficulty, hint | 错题本;error_coach 子图锚点 |
| `ability_dimensions` | `id (uuid)` | user_id, key, name, ideal, actual, sub_items_json | 能力画像 |
| `ability_history` | `id (uuid)` | user_id, dimension_key, score, recorded_at | 时序数据 |
| `tasks` | `id (uuid)` | user_id, title, type, due_at, status, priority | 任务中心 |
| `activities` | `id (uuid)` | user_id, type, title, detail, ref_id, occurred_at | 动态流 |
| `ai_conversations` | `id (uuid)` | user_id, context_type (resume/interview/coach/diagnose), context_id, model, prompt_hash, **graph_name (text)**, **graph_version (text)** | AI 上下文;graph_name 标识由哪个 LangGraph 子图驱动 |
| `ai_messages` | `id (uuid)` | conversation_id, role, content, tokens_in, tokens_out, latency_ms, **thread_id (text)**, **checkpoint_ns (text)**, **checkpoint_id (text)**, **run_id (uuid)**, **node_name (text)** | LLM 消息流;checkpoint 字段用于与 PostgresCheckpointer 对账(见 §17) |
| `tool_call_logs` | `id (uuid)` | run_id, tool_name, arguments_json, result_json, status, latency_ms, occurred_at | 工具调用全量审计 |
| `auth_sessions` | `id` | user_id, device_id, refresh_token_hash, expires_at, last_seen_at | 多端会话 |
| `audit_logs` | `id` | actor_id, action, target_type, target_id, ip, ua, occurred_at | 安全审计 |

### 3.3 敏感数据清单与加密策略
| 字段 | 加密 | 展示 | 备注 |
|---|---|---|---|
| 身份证号 | ✅ AES-256-GCM | 脱敏 `110**********1234` | 仅本人可解 |
| 真实姓名 | ✅ AES-256-GCM | 原值(本人) / 脱敏(他人视角) | |
| 薪资范围 | ✅ AES-256-GCM | 原值(本人) | 不参与检索 |
| 邮箱/手机 | ❌ (哈希) | 用于登录 | bcrypt 密码,sha256 联系方式索引 |
| 面试音视频 | ❌ (MVP 不存) | 留 `audio_ref` 占位 | 后续接 S3 时改为 `s3_object_key` |
| AI 对话内容 (`ai_messages.content`) | ✅ AES-256-GCM | 仅本人 | 对话可能含薪资期望、离职原因等敏感信息;密钥管理同 user_credentials |

### 3.4 软删除 & 回收站
- 所有**业务表**包含 `deleted_at (timestamptz nullable)`,默认 NULL。
- 软删除后:UI 移到「回收站」分区,30 天内可恢复,到期由后台 job 物理删除。
- 外键级联:软删除用户时,简历/面试/错题等标记级联软删除。
- **LangGraph checkpoint 表**(`checkpoints` / `checkpoint_blobs` / `checkpoint_writes`)**不参与软删除**:会话完结后由 LangGraph 库管理,过期即硬删除(无业务可见性,见 §3.5)。
- 软删除 `interview_sessions` 时,通过 ARQ job 同步删除对应 thread 的 checkpoint 数据,避免孤儿。

### 3.5 LangGraph 状态表(checkpoint 内部表)
由 `langgraph-checkpoint-postgres` 自动创建,**不纳入 Alembic 迁移**(库内自带 schema 初始化脚本)。

| 表 | 作用 | 关键字段 |
|---|---|---|
| `checkpoints` | 主表,存 (thread_id, checkpoint_ns, checkpoint_id) → state 序列化快照 | thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint (jsonb) |
| `checkpoint_blobs` | 二进制大字段(state 中过大的值外置) | thread_id, checkpoint_ns, checkpoint_id, idx, blob (bytea) |
| `checkpoint_writes` | 待写增量(节点产出但尚未合并到 state 的 writes) | thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob (bytea) |
| `checkpoint_migrations` | schema 版本管理 | version, installed_at |

**与业务表的关系**:
- 业务表 `ai_messages.thread_id` 对应 `checkpoints.thread_id`。
- 业务表 `ai_messages.checkpoint_id` 对应 `checkpoints.checkpoint_id`。
- 通过 (thread_id, checkpoint_id) 在 `§17.3` 的对账 job 中验证双源一致性。
- `checkpoints` 表存储 GraphState 序列化版本;`ai_messages` 存储展开后的消息流供查询。
- 升级 langgraph 主版本时,**先跑对账 job 备份**再升级,避免 schema 不兼容。

---

## 4. 账号与认证

### 4.1 注册/登录
- **登录方式**:邮箱 + 密码 / 短信验证码 / 第三方 (GitHub、Google、微信、飞书)。
- **密码策略**:≥10 位、含大小写数字符号;bcrypt cost=12。
- **MFA**:TOTP 二次验证 (v1.1 启用,v1.0 可选)。

### 4.2 多端会话
- 单用户最多 **5 个活跃设备**,超限踢出最早空闲设备,可配置「允许/拒绝并发」。
- 设备指纹:UA + 屏幕分辨率 + 时区,生成 `device_id`。
- 每次 API 请求携带 `Authorization: Bearer <access_token>`(15 分钟)+ 静默刷新 `refresh_token`(30 天滚动)。

### 4.3 权限模型
- **当前 MVP**:单租户,`user_id` 即隔离边界。
- **PostgreSQL RLS**:所有表开启 `USING (user_id = current_setting('app.user_id')::uuid)`,后端在事务开始时 `SET LOCAL` 注入用户上下文,杜绝越权。
- **角色**:`member` / `admin`(预留,企业版启用)。

---

## 5. 离线优先与同步

### 5.1 客户端分层
```
┌──────────────────────────────────┐
│ React 组件层 (只读 store)        │
└──────────────┬───────────────────┘
┌──────────────▼───────────────────┐
│ React Query (内存缓存 + 协调)     │
└──────────────┬───────────────────┘
┌──────────────▼───────────────────┐
│ 同步引擎 (Outbox 模式)           │
│  - 写操作 → IndexedDB outbox     │
│  - 联网 → FIFO 回放,409/423 重试 │
└──────────────┬───────────────────┘
┌──────────────▼───────────────────┐
│ IndexedDB (Dexie)                │
│  - 实体表镜像 + outbox + meta    │
└──────────────────────────────────┘
```

### 5.2 同步语义
| 操作 | 离线行为 | 联网时 |
|---|---|---|
| 新建/编辑 | 立即写入本地 + outbox,UI 标记 `pending_sync` | 服务端确认后标记 `synced` |
| 删除 | 立即本地软删 + outbox | 30 天回收站对齐 |
| 读 | 完全本地 | 后台增量同步变更 |

### 5.3 冲突处理 (悲观锁)
- 进入「编辑态」即 `POST /locks/:resource_type/:resource_id {ttl: 300s}`。
- 后端用 Redis `SETNX` 颁发锁,持锁期间拒绝其他端写。
- 心跳每 60s 续期,Tab 失焦或关闭触发释放。
- **WebSocket 推送** 锁状态变化(`lock.acquired` / `lock.released`),其他端 UI 切到「只读 + 提示」。

### 5.4 端到端流程 (示例:编辑简历分支)
1. 用户进入 `ResumeEditor` → 客户端 `POST /locks/resume_branch/:id`。
2. 后端检查持锁人,若空闲 → 发锁 + WS 广播给该用户其他端。
3. 客户端 60s 心跳续期;用户在编辑器中改动 → 写入 IndexedDB + outbox。
4. 离线下继续编辑,联网后 outbox 批量回放,服务端逐条校验锁。
5. 锁冲突 (423) → 客户端提示「其他端正在编辑」,允许强制抢锁 (带版本号)。
6. 用户离开页 30s → 释放锁 + WS 广播。

---

## 6. 简历与版本管理

### 6.1 分支继承模型
- `resume_branches` 树形结构,`parent_id` 指向「核心简历」。
- 创建分支时:**浅拷贝** `resume_blocks`(只复制引用),首次编辑再 **深拷贝** 落盘 → 节省存储 + 保留核心简历权威性。
- 「继承核心」按钮:重新拉取核心简历最新版本覆盖当前分支(需二次确认)。

### 6.2 块级编辑
- 块顺序由 `order_index (numeric)` 控制,支持拖拽 (使用字符串分数排序,如 `"a0"`, `"a1"`, `"a0V"`)。
- 单块内容使用 `content_md` (Markdown) + 派生的 `content_html` 缓存。
- 折叠/展开状态记录在块的 `collapsed (boolean)`,**不**进入版本快照。

### 6.3 版本快照
- **触发**:手动「保存版本」、AI 优化后、定时 30 分钟自动快照。
- **存储策略**:
  - 完整快照 (`snapshot_json`) 仅保存「重要版本」(手动保存 / AI 输出 / 每 10 次自动)。
  - 其他自动版本仅存「与上一版本的 diff」(JSON Patch RFC 6902),压缩存储。
- **回滚**:选择任意历史版本 → 创建新分支指向该版本 → 不破坏当前编辑轨迹。
- **审计**:每次快照记录 `author_type`(user/ai)+ `trigger`(manual/auto/ai)+ `actor_id`。

---

## 7. 面试与 AI 对话(LangGraph 编排)

> 所有 AI 场景均由 **LangGraph 子图** 驱动,持久化采用 **PostgresCheckpointer + 业务表双源**。本节为子系统权威说明,接口契约见 §10.5,WS 事件见 §10.6 / §15,工具清单见 §16,双源一致性策略见 §17。

### 7.1 面试会话生命周期
```
created → in_progress(持锁,thread 已创建)
       → in_progress(node 循环: question_gen → wait_user → evaluate → next_or_finish)
       → (finished | aborted)
       ↘ expired(超时 60 分钟自动关闭)
```

- 进入面试:
  1. 客户端 `POST /api/v1/agents/interview/start`。
  2. 后端创建 `interview_sessions` 行(状态 `active`),颁发悲观锁。
  3. 同步创建 LangGraph thread:`checkpointer.put(thread_id=session_id, namespace="interview", state=initial_state)`。
- 每轮对话:
  1. 客户端 `POST /api/v1/agents/interview/{thread_id}/messages`(用户回答)。
  2. 后端驱动 `interview` 子图运行(`runtime.astream`)。
  3. 节点产出:
     - **Llm 节点**流式 token → WebSocket 推 `agent.{thread_id}/token.delta`。
     - **Tool 节点**调用结果 → 推 `agent.{thread_id}/tool.called` / `tool.returned`。
     - **节点切换** → 推 `agent.{thread_id}/node.started` / `node.finished`。
  4. 节点回调 `on_node_finished` → 同步写 `ai_messages`(与 checkpoint 同一事务,见 §17)。
- 结束:
  1. 触发 `next_or_finish` 节点判定题目数达到或用户主动结束。
  2. 进入 `report` 节点生成 `interview_reports`。
  3. 异步触发 `ability_diagnose` 子图,更新 `ability_dimensions` + `ability_history`。
  4. 释放悲观锁,WS 广播 `lock.released`。

**GraphState TypedDict**(interview 子图):
```python
class InterviewState(TypedDict):
    messages: list[BaseMessage]          # langchain 消息流
    position: str
    company: str
    jd: str                                # 来自 query_jd 工具
    current_dimension: str                 # 当前考察的能力维度
    questions_asked: list[Question]
    answers: list[Answer]
    per_question_score: list[float]
    elapsed_sec: int
    config: InterviewConfig                # 题目数 / 时长 / 模式
    resume_snapshot: dict | None            # 来自 query_resume_blocks
```

### 7.2 AI 对话流(双源持久化)

**双源架构**:
```
                    ┌────────────────────────────────────────────┐
                    │       LangGraph runtime.astream            │
                    └──────────────┬─────────────────────────────┘
                                   │
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
   ┌────────────────────────┐           ┌──────────────────────────┐
   │ PostgresCheckpointer   │           │   业务回调钩子            │
   │ (langgraph 库内管理)    │           │  on_node_finished /      │
   │                        │           │  on_llm_new_token        │
   └──────────┬─────────────┘           └──────────┬───────────────┘
              ▼                                     ▼
   ┌────────────────────────┐           ┌──────────────────────────┐
   │ checkpoints /          │           │ ai_messages              │
   │ checkpoint_blobs /     │           │  (含 thread_id,          │
   │ checkpoint_writes      │           │   checkpoint_id,         │
   │ (GraphState 序列化)    │           │   run_id, node_name)     │
   └────────────────────────┘           └──────────────────────────┘
              │                                     │
              └──────────────┬──────────────────────┘
                             ▼
                (thread_id, checkpoint_id) 双源对账
                        (见 §17)
```

**写入语义**:
- `ai_messages.content` AES-256-GCM 加密存储(见 §3.3)。
- 每条 `ai_messages` 必填:`thread_id` + `checkpoint_id` + `run_id` + `node_name`,缺一不可对账。
- `run_id` 是同一节点调用的唯一标识(LangGraph `config["run_id"]`)。
- 一个 checkpoint 周期内可能产生多条 `ai_messages`(LLM 节点 + tool 节点各算一条)。

**失败语义**:
- 业务表写失败 → 整个事务回滚 → checkpointer 状态保持上一致。
- checkpointer 写失败(库内异常)→ 业务事务已 commit → 进入 `orphan_state` 状态,次日对账 job 修复(见 §17.2 / §17.3)。

### 7.3 LangGraph 多 Agent 架构 ⭐

5 个子图各自独立,**不共享 GraphState**(避免状态污染)。`checkpoint_ns` 标识子图命名空间。

| 子图 | thread_id 来源 | 主要节点 | 调用的工具(见 §16) | 终止条件 | 关键中断点 |
|---|---|---|---|---|---|
| `interview` | `interview_session.id` | intake → question_gen → wait_user → evaluate → next_or_finish → report | query_resume, query_jd, record_score, evaluate_answer | 题目数达到 ∨ 用户主动结束 ∨ 超时 60min | (无,实时流) |
| `resume_optimize` | `resume_branch.id` | load_branch → diff_jd → suggest_blocks → apply_or_discard → snapshot | query_jd, query_branch_blocks, save_version | 用户确认 ∨ 用户取消 ∨ 30min 无活动 | **必须 `interrupt_after(apply_or_discard)`**(人工确认才能落盘) |
| `ability_diagnose` | `interview_session.id`(完成时触发) | aggregate_scores → compare_baseline → generate_insight | query_history, query_dimensions | 单次完成 | (无) |
| `error_coach` | `error_question.id` | fetch_question → hint_ladder → wait_user → evaluate | query_error_book | 答对 3 次 ∨ 用户退出 ∨ 超时 10min | (无) |
| `general_coach` | `ai_conversation.id`(无业务锚点) | intent → route → respond | 视意图分发到子图 | 用户关闭 | (无) |

**统一规范**:
- 每个子图独立 `checkpointer_ns`(与 graph_name 同名)。
- 每个子图独立 `GraphState`(集中在 `app/agents/state.py`,用 TypedDict 子类区分)。
- 节点函数返回 `Command(goto=...)` 显式路由,避免隐式边。
- 所有节点入口都接 `config["configurable"]["thread_id"]`,确保与业务锚点一致。
- LLM 节点统一接 streaming callback → WS 推 `token.delta`。
- 工具调用统一经 §16.1 的 `ToolNode`,记录 `tool_call_logs`。
- 支持 `interrupt_before` / `interrupt_after` 用于人类介入(仅 `resume_optimize` 强制启用)。
- 单 thread 节点跳转数 ≤ 50(防死循环,见 §16.3)。

### 7.4 能力画像更新
- 触发器:`interview_sessions.status` 变为 `finished`。
- 调度方式:ARQ job 入队 → 后台执行 `ability_diagnose` 子图。
- 子图产出 → 写 `ability_dimensions.actual` + 追加 `ability_history` 增量。
- 前端按月聚合 `ability_history` 渲染成长曲线(同 `growthTrajectory` 字段)。

### 7.5 旧 mockData 字段到 LangGraph 状态的映射
| 旧 mock 字段 | 位置 | 新归属 |
|---|---|---|
| `nextQuestions` (InterviewLive.tsx L56) | 静态数组 | 改为订阅 `agent.{thread_id}/node.started(question_gen)` 事件 |
| `interviewHistory` (mockData L182) | 静态历史 | 改为 `GET /api/v1/interview-sessions` 查询真实数据 |
| `errorBook` (mockData L286) | 静态错题 | 改为 `GET /api/v1/error-questions`,error_coach 子图用 `query_error_book` 工具读取 |
| `abilityDimensions` (mockData L335) | 静态画像 | 改为 `GET /api/v1/ability-dimensions`,ability_diagnose 子图定期重算 |
| `growthTrajectory` (mockData L414) | 静态曲线 | 改为 `GET /api/v1/ability-dimensions/history?aggregate=month` |
| `improvementSuggestions` (mockData L424) | 静态建议 | 改为 general_coach 子图运行时生成 |

---

## 8. 任务、活动与通知

### 8.1 任务 (tasks)
- 字段:title, type(resume/interview/review/general), due_at, priority, status(todo/doing/done/abandoned)。
- 客户端用 `react-query` 拉取 `due_at <= now() + 7d` 的任务,首页聚合展示。
- **触发器**:简历被标记 `submitted` → 自动创建「准备 X 公司面试」任务。

### 8.2 活动流 (activities)
- 写入:UI 行为、API 副作用 (面试完成、错题巩固、简历优化) → 通过领域事件统一发往 `activity_collector`。
- 读取:游标分页 `cursor + limit`,倒序展示,默认 7 天内。
- **保留**:90 天,过期归档到冷库。

### 8.3 通知 (notifications)
- v1.0 仅站内通知(v1.1 加邮件/短信/微信模板消息)。
- 字段:type, title, body, ref_url, read_at。
- WebSocket 实时推送 `notification.created`。

---

## 9. 数据生命周期与保留期

### 9.1 状态机
```
                ┌──────────┐
       create → │  active  │
                └────┬─────┘
                     │ soft_delete (T+0)
                     ▼
                ┌──────────┐
                │ trashed  │ ←─ restore (T+0~T+30)
                └────┬─────┘
                     │ cron @ T+30
                     ▼
                ┌──────────┐
                │  purged  │ (物理删除,无审计外暴露)
                └──────────┘
```

### 9.2 时间线
| 事件 | 触发 | 保留窗口 | 到期处理 |
|---|---|---|---|
| 单条数据软删除 | 用户操作 | 30 天 | 物理删除 + 加密擦除 (blkdiscard 不可恢复) |
| 账号注销 | 用户主动 / 违规 | 90 天 | 清除全部用户数据 + 凭证 + 解绑第三方 |
| 账号长期未登录 | 6 个月无登录 | 90 天宽限期 | 转为冻结态,需邮箱验证激活 |
| 面试报告 | 自动 | 永久 (个人档案) | 不主动清除 |
| 活动流 | 自动 | 90 天 | 归档到冷库 (S3 IA),仅管理员可查 |
| AI 对话 | 自动 | 6 个月热存 → 冷存 | 用户可手动全部清空 |
| 审计日志 | 自动 | 1 年 | 物理删除 |

### 9.3 导出与导入
- **导出**:用户可一键导出全量数据为 `.zip` (含 `data.json` + 资源 manifest),生成一次性签名 URL,24h 过期。
- **导入**:上传 `.zip` → 客户端解析 → diff 预览 → 确认合并或覆盖。
- **数据迁移**:同一账号不同设备首次登录 → 提示「检测到云端数据,是否拉取?」→ 拉取 + 合并本地 IndexedDB。

---

## 10. 接口契约

### 10.1 REST 风格
- 资源命名:`/api/v1/{resource}`,复数名词,小写连字符。
- HTTP 语义:`GET`(查)/ `POST`(建)/ `PUT`(全量替)/ `PATCH`(局部改)/ `DELETE`(删)。
- 响应包装:`{ data, meta: {request_id, pagination} }`,错误 `{ error: { code, message, details } }`。
- 状态码:200/201/204/400/401/403/404/409/422/423(锁冲突)/429/500。

### 10.2 鉴权
- `Authorization: Bearer <access_token>`。
- 写操作要求 `If-Match: <resource_version>`,并发更新返回 412。
- 锁相关接口 423 返回时携带 `current_holder` 信息。

### 10.3 分页与过滤
- **列表**:游标分页 `?cursor=...&limit=20`,最多 100。
- **过滤**:`?filter[field]=value`,支持 `in`、`gte`、`lte`。
- **排序**:`?sort=-updated_at,+title`。
- **稀疏字段**:`?fields=id,name,status` 减少流量。

### 10.4 幂等
- 所有 `POST` 接受 `Idempotency-Key: <uuid>`,24h 内同 key 重复请求返回首次结果。
- 客户端在 outbox 中固化该 key,保证重试不产生副作用。

### 10.5 关键端点 (摘录)

**业务域**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/auth/login` | 登录,返回 access/refresh |
| GET | `/api/v1/users/me` | 当前用户信息 |
| GET | `/api/v1/resume-branches` | 简历分支列表 |
| POST | `/api/v1/resume-branches` | 新建分支 |
| POST | `/api/v1/resume-branches/:id/lock` | 申请悲观锁 |
| DELETE | `/api/v1/resume-branches/:id/lock` | 释放锁 |
| GET | `/api/v1/resume-branches/:id/versions` | 历史版本 |
| POST | `/api/v1/resume-branches/:id/versions` | 创建快照 |
| GET | `/api/v1/interview-sessions` | 面试历史 |
| GET | `/api/v1/interview-sessions/:id` | 单场面试详情(消息流) |
| POST | `/api/v1/interview-sessions/:id/finish` | 结束并生成报告 |
| GET | `/api/v1/ability-dimensions` | 能力画像 |
| GET | `/api/v1/activities` | 动态流 |
| POST | `/api/v1/exports` | 申请全量导出 |
| POST | `/api/v1/imports` | 提交导入任务 |

**Agent 子图入口** (新增):
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/agents/interview/start` | 启动 interview 子图(创建 thread + 持锁) |
| POST | `/api/v1/agents/interview/{thread_id}/messages` | 追加用户回答(WS 同步流式响应) |
| POST | `/api/v1/agents/interview/{thread_id}/interrupt/resolve` | 解决中断点(预留,interview 暂不启用) |
| GET | `/api/v1/agents/interview/{thread_id}/state` | 查询图状态快照(断线恢复) |
| POST | `/api/v1/agents/resume-optimize/start` | 启动 resume_optimize 子图(持锁) |
| POST | `/api/v1/agents/resume-optimize/{thread_id}/confirm` | 解决 `apply_or_discard` 中断,落盘 / 取消 |
| POST | `/api/v1/agents/error-coach/start` | 启动 error_coach 子图(按错题 id) |
| POST | `/api/v1/agents/general-coach/start` | 启动 general_coach 子图(无业务锚点) |
| GET | `/api/v1/agents/{thread_id}/checkpoints` | 历史 checkpoint 列表(对账 / 调试) |

### 10.6 WebSocket 频道

**控制面** (与 LangGraph 解耦,沿用 v0.1 方案):
| Channel | 事件 | 触发 |
|---|---|---|
| `sync.{user_id}` | `lock.acquired` / `lock.released` | 锁状态变化 |
| `sync.{user_id}` | `resource.updated` | 推送增量变更(可选) |
| `sync.{user_id}` | `notification.created` | 站内通知 |

**Agent 数据面** (新增,与 LangGraph 强绑定):
| Channel | 事件 | 触发 |
|---|---|---|
| `agent.{thread_id}` | `node.started` | LangGraph runtime hook(节点开始) |
| `agent.{thread_id}` | `node.finished` | 节点结束(含 outputs 摘要) |
| `agent.{thread_id}` | `token.delta` | LLM 流式 callback(逐 token) |
| `agent.{thread_id}` | `tool.called` | ToolNode 钩子(入参 + 工具名) |
| `agent.{thread_id}` | `tool.returned` | ToolNode 钩子(出参 + 耗时) |
| `agent.{thread_id}` | `interrupt` | 等待人类决策(仅 resume_optimize) |
| `agent.{thread_id}` | `state.snapshot` | 周期性同步(用于客户端恢复) |
| `agent.{thread_id}` | `error` | 节点 / 工具 / LLM 失败(结构化错误) |
| `agent.{thread_id}` | `final` | thread 终止(成功 / 失败 / 中断) |

**事件 payload 通用结构**:
```json
{
  "event": "node.started",
  "thread_id": "uuid",
  "graph": "interview",
  "graph_version": "1.0.0",
  "run_id": "uuid",
  "node": "question_gen",
  "ts": "2026-06-12T10:23:45.123Z",
  "data": { ... }
}
```

---

## 11. 非功能性需求

### 11.1 性能
| 指标 | 目标 |
|---|---|
| API 平均响应 (P50) | ≤ 150ms |
| API 响应 (P95) | ≤ 500ms |
| API 响应 (P99) | ≤ 1.2s |
| 列表查询 (P95) | ≤ 300ms (1 万行表) |
| WebSocket 推送延迟 | ≤ 200ms (本区域内) |
| 首屏可交互 (TTI) | ≤ 2.0s (4G) |
| 离线→在线同步收敛 | ≤ 30s (普通 1k 操作队列) |
| **LangGraph 节点执行** (单节点,不含 LLM) P95 | ≤ 1.5s |
| **LangGraph 节点执行** (含 LLM 流) 首 token P95 | ≤ 800ms |
| **端到端对话 token 延迟** (P95) | ≤ 200ms / token |
| **并发 thread 数** (单 FastAPI 实例) | ≥ 200 |
| **PostgresCheckpointer 写** (单 checkpoint) P95 | ≤ 50ms |

### 11.2 可用性与扩展
- 服务可用性:99.9% (SLA)。
- FastAPI 异步无状态,横向扩展;PostgreSQL 主从 + 1 个 hot standby。
- ARQ Worker 与 FastAPI 同部署,Redis Sentinel 主备。
- WebSocket 横向扩展:uWSGI/uvicorn 集群 + Redis Pub/Sub 转发(同节点优先路由)。
- 客户端 outbox 限速:每秒 ≤ 10 次写回放,避免突发压垮服务端。

### 11.3 审计与可观测
- **审计日志**:登录、注销、敏感字段读写、软删/恢复、导出全部入库 `audit_logs`。
- **结构化日志**:JSON,字段含 `request_id` / `user_id` / `thread_id` / `run_id` / `graph` / `node`。
- **OpenTelemetry trace**:全链路 trace(FastAPI → SQLAlchemy → Redis → LangGraph → LLM)。
- **LangSmith / OpenInference**:LangGraph 子图级 trace,可逐 token / 逐节点重放。
- **可观测指标**:Prometheus + Grafana,关键 SLI:
  - API P50/P95/P99
  - Agent 节点耗时(按 graph + node 分桶)
  - LLM 调用成功率 / 延迟 / token 消耗
  - PostgresCheckpointer 写延迟
  - 锁等待时长
- **告警**:登录失败 > 5 次/分钟、API 错误率 > 1%、LLM 调用失败率 > 5%、checkpointer 写失败率 > 0.1%。

### 11.4 合规
- **PIPL / GDPR** 双适配:用户可一键导出/清除(「被遗忘权」)。
- Cookie 同意条 (v1.1)。
- 数据处理协议 (DPA) 模板,v1.1 出企业版时启用。
- **未成年人**:注册时校验 ≥ 16 岁 (PIPL)。

---

## 12. 迁移与上线

### 12.1 从 mock 到真实数据
- 在前端引入 `repository` 抽象层,所有数据访问走 `repository.xxx.xxx()`,内部再分 mock 实现与 HTTP 实现。
- 通过 `VITE_USE_MOCK` 环境变量一键切换,旧 `mockData.ts` 作为 dev 兜底保留。
- 渐进式替换:每完成一个 repository 跑一遍冒烟,全量替换 1 个 sprint。

### 12.2 灰度发布
- 后端先开 5% 流量,验证 7 天;再 25% → 50% → 100%。
- 数据库迁移用 Alembic(配合 SQLAlchemy 2.0 async),所有迁移脚本双跑(staging 与 prod 同步执行,人工对比)。
- **LangGraph checkpointer 表不纳入 Alembic**(由 langgraph-checkpoint-postgres 库内管理)。

### 12.3 回滚预案
- 客户端可通过开关回退到 mock (VITE_USE_MOCK=true)。
- 服务端保留最近 3 个版本 API 的兼容层,关键写操作保留 7 天幂等窗口。

---

## 13. 风险与未决项

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| R1 | 悲观锁导致长任务卡死 | 编辑体验差 | TTL 300s + 心跳 60s,超时自动释放 |
| R2 | AI 对话存储成本高 | 6 个月后冷存 | 月度归档 job + 限额策略 |
| R3 | 多端同步造成冲突时用户困惑 | 数据丢失感 | UI 明确提示「被其他端抢占」,支持 diff 合并视图 |
| R4 | 加密字段无法做服务端检索 | 功能受限 | 哈希索引 + 桶化字段(如薪资分桶) |
| R5 | 离线队列在弱网下膨胀 | 客户端卡顿 | IndexedDB 配额监控 + 提示用户联网 |
| R6 | 软删除 30 天误删后无法恢复 | 用户损失 | 「回收站」+ 二次确认 + 操作历史 |
| R7 | 合规要求 (PIPL/GDPR) 与产品便利冲突 | 法务风险 | 导出/清除功能 v1.0 即上线 |
| R8 | LangGraph checkpointer 表 schema 随 langgraph 主版本升级而变更 | 升级困难 | 锁定 langgraph 主版本,升级前跑对账 job 备份 |
| R9 | 双源(checkpoint ↔ ai_messages)分布式部署下数据漂移 | 数据不一致 | 业务事务优先 commit + 异步对账 job;极端回退到「业务表唯一源 + MemorySaver」 |
| R10 | Agent 死循环(如 LLM 反复触发同一 tool) | 资源耗尽 | Graph 节点跳转上限 50 + 工具调用频次限流 + 死循环检测中间件 |
| R11 | LLM 流式 token 在 WS 断线时丢失 | 客户端丢字 | 客户端携带 `last_seen_checkpoint_id` 重连,服务端从该点重放 |

### 13.1 未决项 (v0.2)

**产品/法务**:
- 国际化与多时区存储策略(UTC vs 本地)。
- 「团队版」/「企业版」是否在 v1.0 数据模型预留(推荐预留 `org_id`)。
- AI Token 计费是否纳入审计,以及是否对用户可见。
- 面试录音/视频的最终存储后端(自建 MinIO vs 阿里云 OSS vs 腾讯云 COS)。
- AI 对话内容的合规留存周期(目前 6 个月,需法务复核 GDPR / PIPL)。

**LangGraph / 后端技术选型** (新增):
- **LLM 提供商 v1.0**:OpenAI vs Anthropic(选定后写入 `config/llm.yaml`)。
- **ARQ vs Celery**:推荐 ARQ(异步友好、轻量),Celery 生态更熟,需最终决策。
- **鉴权方案**:`fastapi-users` 完整方案 vs 自研 JWT(更灵活)。
- **LangSmith / OpenInference**:是否启用,涉及 API KEY 申请与数据出境合规(关键决策点)。
- **GraphState 重建脚本**:checkpointer 写失败场景下,从 `ai_messages` 重建 GraphState 的具体策略(脚本待写)。
- **工具 IAM 模型**:细粒度到 tool 级鉴权 vs user 级鉴权。
- **多 Agent 路由方式**:Supervisor 图(动态路由) vs 业务侧显式分发(更可控)。
- **WebSocket 横向扩展**:uWSGI/uvicorn 集群下用 Redis Pub/Sub 转发,还是用专门的 Push 服务(Go/Pusher)。
- **ai_messages.content 加密**对查询的影响:全加密后无法做关键词搜索,是否预留明文索引列(独立于加密列)。

---

## 14. 附录

### 14.1 名词解释
- **悲观锁**:同一资源同一时刻仅允许一端编辑,其他端只读。
- **Outbox 模式**:写操作先入本地队列,联网后回放,保证至少一次投递。
- **RLS (Row Level Security)**:PostgreSQL 行级安全,数据库层做租户隔离。
- **CRDT**:Conflict-free Replicated Data Type,用于多人协作(本 MVP 不实现)。
- **LangGraph**:LangChain 生态的多 Agent 编排框架,以状态图为核心,支持 checkpoint / interrupt / streaming。
- **GraphState**:LangGraph 子图的状态 TypedDict,在 checkpoint 中序列化存储。
- **Checkpointer**:LangGraph 状态持久化器;`PostgresCheckpointer` 使用 PostgreSQL 后端。
- **Thread**:LangGraph 的执行上下文,一个 thread 对应一次会话(如一场面试)。
- **interrupt_before / interrupt_after**:LangGraph 的「人类介入」机制,在指定节点前后暂停,等待外部 Command 恢复。
- **PostgresCheckpointer 双源**:本项目特有的设计 —— LangGraph checkpointer(GraphState 序列化) + ai_messages 业务表(消息流展开)同时存储,通过 (thread_id, checkpoint_id) 关联。
- **Alembic**:SQLAlchemy 官方数据库迁移工具。
- **ARQ**:基于 Redis 的异步任务队列(类似 Celery,但与 asyncio 集成更紧密)。
- **uv**:Astral 推出的 Python 包管理器(替代 pip + venv)。

### 14.2 引用
- mockData: `src/data/mockData.ts`
- 页面: `src/pages/{Dashboard,ResumeList,ResumeEditor,InterviewList,InterviewLive,InterviewReport,Jobs,Resources,Settings,Profile}.tsx`
- 领域类型:`ResumeBranch`, `ResumeBlock`, `InterviewHistory`, `ErrorQuestion`, `AbilityDimension`
- 后端规划(本轮不做):`backend/app/agents/graphs/interview.py`(interview 子图首个实现)
- 计划文件:`C:\Users\30803\.claude\plans\structured-singing-crane.md`

### 14.3 变更记录
| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-06-12 | 初稿,基于 8 项核心决策(Node + NestJS + Prisma) |
| v0.2 | 2026-06-12 | 升级至 FastAPI + LangGraph 异步栈;新增 §7.3/§15/§16/§17;§3.2 实体新增 LangGraph 关联字段;§3.5 新增 checkpoint 内部表说明;§10.5/§10.6 扩展 Agent 端点与 WS 频道;§11.1/§11.3 扩展性能与可观测指标 |

---

## 15. LangGraph 多 Agent 架构(总览)

> 本节是 §7.3 的「前端视角」展开,主要给前端工程师与运维看;后端 / AI 工程师看 §7.3。

### 15.1 子图清单与入口
详见 §7.3,5 个子图:**interview** / **resume_optimize** / **ability_diagnose** / **error_coach** / **general_coach**。

### 15.2 前端订阅规范

**WS 频道命名**:`agent.{thread_id}`,其中 `thread_id` 对应业务锚点 id(`interview_session.id` / `resume_branch.id` / 等)。

**事件处理**:
| 事件 | 前端行为 |
|---|---|
| `node.started` | 渲染「正在思考:xxx」loading 状态 |
| `token.delta` | 流式追加 AI 文本(防抖 50ms 提交 React state) |
| `node.finished` | 移除对应 loading 状态 |
| `tool.called` | 渲染「正在调用工具:xxx」,可折叠 |
| `tool.returned` | 折叠展示工具返回(脱敏) |
| `interrupt` | 弹出确认对话框(resume_optimize 专用) |
| `state.snapshot` | 校对本地状态(防漂移) |
| `error` | 提示「面试官暂时离开」,允许重试 |
| `final` | 关闭流,跳转到报告页 / 完成态 |

**断线重连**:客户端重连时发送 `{type: "resume", last_seen_checkpoint_id: "..."}`,服务端基于 `checkpointer.get_state(history=...)` 从该点重放(见 §17.4)。

### 15.3 后端调用规范
**统一入口**:
```python
# app/agents/runtime.py
async def run_agent(
    graph_name: str,           # "interview" | "resume_optimize" | ...
    thread_id: str,
    input: dict | Command,
    config: RunnableConfig,
) -> AsyncIterator[StreamEvent]:
    compiled = get_compiled_graph(graph_name, config["graph_version"])
    async for event in compiled.astream(input, config={**config, "configurable": {"thread_id": thread_id, "checkpoint_ns": graph_name}}):
        await on_node_event(event)          # 推 WS
        await mirror_to_ai_messages(event)  # 双源写业务表
        yield event
```

**关键约束**:
- 入口唯一,业务服务不直接 import 各子图。
- graph_name + graph_version 决定具体编译的图(支持热加载新版本图)。
- `mirror_to_ai_messages` 与 checkpoint 写入在同一 SQLAlchemy session(共享事务)。

### 15.4 Graph 版本管理
- 每个子图文件有 `__version__` 常量,如 `"1.0.0"`。
- 启动时检查 `ai_conversations.graph_version` 与当前 `__version__`,不一致则:
  - 老 thread 仍跑老图(向后兼容,直到会话自然结束)
  - 新 thread 启用新图
- 灰度策略:通过 `LLMRouter.feature_flag["graph_version"]` 控制,允许 A/B。

---

## 16. 工具与外部服务注册

### 16.1 工具清单
所有 LangGraph ToolNode 调用的工具集中在 `app/agents/tools/`,通过 `@tool` 装饰器注册。

| 工具名 | 入参 (Pydantic) | 出参 | 鉴权 | 限流 | 调用方 |
|---|---|---|---|---|---|
| `query_resume_blocks` | `branch_id: uuid, include_inherited: bool = True` | `list[ResumeBlockOut]` | user_id 检查 | 100/min/user | interview, resume_optimize |
| `query_jd` | `company: str, position: str` | `JDText` | 公开 | 200/min/user | interview, resume_optimize |
| `query_error_book` | `user_id: uuid, category: str \| None, limit: int = 20` | `list[ErrorQOut]` | user_id 检查 | 50/min/user | error_coach |
| `query_branch_blocks` | `branch_id: uuid` | `list[ResumeBlockOut]` | user_id 检查 + 持锁校验 | 100/min/user | resume_optimize |
| `record_score` | `session_id: uuid, dimension: str, score: int, comment: str` | `{"ack": true}` | user_id 检查 + 持锁校验 | 同会话 | interview, ability_diagnose |
| `save_resume_version` | `branch_id: uuid, snapshot: dict, version_label: str` | `{"version_id": uuid}` | 持锁校验 | 10/min/user | resume_optimize |
| `evaluate_answer` | `answer: str, ref_answer: str \| None, dimension: str` | `EvalResult(score, strengths, improvements)` | LLM 调用 | 20/min/user | interview, error_coach |
| `query_history` | `user_id: uuid, dim: str \| None, days: int = 90` | `list[AbilityHistoryOut]` | user_id 检查 | 50/min/user | ability_diagnose |
| `query_dimensions` | `user_id: uuid` | `list[AbilityDimensionOut]` | user_id 检查 | 50/min/user | ability_diagnose |

**Tool 装饰器约定**:
```python
@tool(
    name="query_resume_blocks",
    rate_limit=RateLimit(times=100, per_seconds=60),
    requires_user=True,
    requires_lock=LockSpec(resource="resume_branch", key_arg="branch_id"),
)
async def query_resume_blocks(branch_id: uuid.UUID, include_inherited: bool = True) -> list[ResumeBlockOut]:
    ...
```

**错误传播**:
- 工具内部失败 → 返回 `ToolError(code, message, retryable, cause)`。
- ToolNode 捕获后转成 `tool.returned` 事件(状态 `failed`),不抛异常。
- 节点根据 `retryable` 决定是否重试或走降级分支。

### 16.2 LLM 提供商
- v1.0:OpenAI / Anthropic 二选一(写入 `config/llm.yaml`,需在 §13.1 决策)。
- v1.1:增加国内模型(DeepSeek / Qwen),通过 `LLMRouter` 抽象统一接口。
- 客户端不直接感知 provider,通过 `llm_provider_pref` 字段个性化推荐(可被风控覆写)。

### 16.3 限流与配额
**三层限流**:
| 层级 | 机制 | 桶 | 兜底 |
|---|---|---|---|
| 工具级 | Redis token bucket | `ratelimit:tool:{name}:{user_id}` | 抛 429 |
| LLM 级 | 月度 token 配额 | `users.monthly_token_used` | 暂停 LLM 调用,提示订阅升级 |
| Graph 级 | 单 thread 节点跳转数 | 进程内计数器 | 抛 `MaxStepsExceeded`,转 final 事件 |

**降级策略**:
- 工具调用失败 (retryable=true) → 自动重试 3 次(指数退避) → 仍失败则节点走降级分支。
- LLM 不可用 → 节点返回 `RetryableError`,前端显示「面试官暂时离开」,thread 状态保持,允许重连。
- LLM 月度配额耗尽 → 节点返回 `QuotaExceededError`,前端提示订阅升级,thread 状态保存。

---

## 17. 同步双源一致性策略

### 17.1 写入路径(单请求)
```
[1] FastAPI 接收请求(POST /agents/interview/{thread_id}/messages)
    ↓
[2] SQLAlchemy async session.begin()
    ↓
[3] runtime.astream(input, config={"configurable": {"thread_id": ..., "checkpoint_ns": "interview"}})
    ↓
[4] 节点 LlmNode 流式输出:
    ├── → LLM provider(外部)
    │     ├── token callback → 推 WS agent.{thread_id}/token.delta
    │     └── (LangChain 自动管理)
    └── → 节点结束回调 on_node_finished(event)
          └── → INSERT INTO ai_messages (共享 SQLAlchemy session)
    ↓
[5] LangGraph runtime 自动调用 checkpointer.put(state, ...)
    └── → 写入 checkpoints / checkpoint_blobs 表(库内事务,**独立于外层 session**)
    ↓
[6] session.commit()
```

**问题点**:Step 5 的 checkpointer 写是 LangGraph 库内事务,**与外层业务事务不同步**。可能的失败模式:
- 业务事务 commit 成功 + checkpoint 写失败 → `orphan_state`(业务表领先)。
- 业务事务失败回滚 + checkpoint 已写成功 → `orphan_checkpoint`(checkpoints 表领先)。

### 17.2 事务边界策略
- **业务事务优先**:业务表先 commit(checkpointer 写失败不影响业务可见性)。
- **checkpointer 内部事务**:`PostgresSaver` 默认独立事务,接受短期不一致。
- **重建策略**:
  - 启动时 scan `checkpoints` 表中无对应 `ai_messages` 行的 checkpoint → 标记 `orphan`。
  - 启动时 scan `ai_messages` 中无对应 `checkpoints` 行的记录 → 标记 `orphan`。
  - 重建脚本(待实现):以 `ai_messages` 为唯一源,按时间序列重放 GraphState。

### 17.3 对账 job
- 调度:每日 03:00 ARQ 定时任务。
- 算法:
  ```sql
  SELECT cm.thread_id, cm.checkpoint_id, am.checkpoint_id IS NOT NULL AS has_business
  FROM checkpoints cm
  LEFT JOIN ai_messages am ON cm.thread_id = am.thread_id AND cm.checkpoint_id = am.checkpoint_id
  WHERE cm.created_at > now() - interval '1 day'
    AND cm.checkpoint_ns = 'interview';
  ```
- 容差:< 1% 缺失视为正常抖动(部分节点无业务消息,如纯路由节点)。
- 告警:> 1% 缺失 → 钉钉/Slack 告警 + 触发修复脚本。

### 17.4 客户端重放
- 客户端断线时记录 `last_seen_checkpoint_id`(从最近一次 `state.snapshot` 事件取)。
- 重连时 WS 发送 `{type: "resume", last_seen_checkpoint_id}`。
- 服务端:
  ```python
  state = checkpointer.get_state(thread_id, checkpoint_ns, before=last_seen_checkpoint_id)
  async for event in compiled.astream(None, config=...):  # None = 从 checkpoint 继续
      yield event
  ```
- 兼容性:`last_seen_checkpoint_id` 不存在(如老客户端)→ 服务端从最新状态开始,前端丢弃旧消息。

