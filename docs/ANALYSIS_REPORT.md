# InterCraft 持久化需求 · 逻辑一致性审视报告

> 版本: v1.0 · 2026-06-12
> 对应原文档: [PERSISTENCE_REQUIREMENTS.md](./PERSISTENCE_REQUIREMENTS.md) v0.2
> 用途: 供原文档 v0.3 修订使用,各模块文档在「§7 待澄清」段会反链回本文中的 A{n} 编号

---

## 摘要

对 `PERSISTENCE_REQUIREMENTS.md` v0.2(893 行)做了逐章逐表的交叉对照,共识别 **17 项** 一致性问题:

- 🔴 **阻塞性**(5 项):必须修订才能开工
- 🟡 **重要**(8 项):可开工但易留坑,模块设计阶段需最终拍板
- 🔵 **建议级**(4 项):允许后置到 v0.4

按主题分布:**LangGraph / 双源持久化** 占 7 项(A1/A2/A4/A5/A6/A7/A14),**离线 & 同步** 占 1 项(A3),**数据模型字段缺失** 占 5 项(A9/A11/A13/A16),**业务流程衔接** 占 4 项(A8/A10/A12/A15/A17)。

---

## 🔴 阻塞性问题(5 项)

### A1. 三源消息流关系未明确

**现象**:
- §3.2 同时定义 `interview_messages`(注释:供前端展示,与 ai_messages 互补)与 `ai_messages`(LLM 消息流)
- §17 双源对账只覆盖 `ai_messages` ↔ `checkpoints`

**矛盾**:
- `interview_messages` 是否参与对账?
- 三者写入顺序与一致性策略缺失
- 前端展示读哪张表?

**建议修复**(二选一):
1. **方案 A(推荐)**:删除 `interview_messages` 表,前端直接读 `ai_messages`(解密后),`ai_messages` 是唯一权威源
2. **方案 B**:把 `interview_messages` 改为 `ai_messages` 的 PostgreSQL 视图(View 或物化视图),自动同步且无需对账

**影响模块**: M11(面试历史)、M14(LangGraph 基建)、M15(Interview 子图)、M22(对账)

---

### A2. LangGraph checkpoints 表的 RLS / 跨用户隔离缺失

**现象**:
- §4.3 所有业务表开 RLS:`USING (user_id = current_setting('app.user_id')::uuid)`
- §3.5 checkpoints 由 `langgraph-checkpoint-postgres` 库自动创建,**不纳入 Alembic**(库内自管 schema)

**矛盾**: checkpoints / checkpoint_blobs / checkpoint_writes 表的列没有 user_id;若不能加 RLS,如何防止用户 A 通过伪造 thread_id 读到用户 B 的 GraphState?

**建议修复**(任选,推荐组合 ①+②):
1. **应用层强制校验**:每次 `checkpointer.put/get` 前先查 `ai_conversations WHERE thread_id=? AND user_id=current_user` 是否存在
2. **thread_id 编码用户前缀**:`thread_id = f"{user_id_short}:{session_id}"`,所有读取强制 prefix 匹配
3. **手工启 RLS**:升级 langgraph 时手动注入 `ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY`,通过 thread_id 关联校验(脆弱,不推荐)

**影响模块**: M14(LangGraph 基建)、M22(审计)

---

### A3. 离线编辑 + 悲观锁 + 长会话的语义冲突

**现象**:
- §5.4 「离线下继续编辑,联网后 outbox 批量回放」
- §5.3 「持锁期间拒绝其他端写」+「心跳每 60s 续期」+「锁 TTL 300s」

**矛盾**: 离线时无法续期 → 300s 后锁自动释放 → 其他端可抢占;回放时遭遇 423,即使「强制抢锁」也会覆盖他人改动。

**建议修复**:
- **明确边界**:离线优先**仅适用于** ① 无悲观锁要求的资源(错题本、个人设置、活动流) ② 短时间断网(< 锁 TTL)
- **长时间离线 + 锁资源场景**:UI 显式告警「检测到 60s 无心跳,锁可能已被他人抢占,继续编辑可能产生冲突」,并在恢复联网时强制走「diff 合并视图」而非覆盖
- **可选兜底**:引入「乐观追加 + 服务端合并」(只对 resume_blocks 这类块级数据生效)

**影响模块**: M12(锁/WS 控制面)、M13(客户端 Outbox)

---

### A4. AI 流式 token 在 WS 断线时的重放策略不可执行

**现象**:
- §13.1 R11 + §17.4 表示客户端携带 `last_seen_checkpoint_id` 重连,服务端「从该点重放」

**矛盾**: `token.delta` 是 LLM provider 流式回调,checkpoint 通常**仅在节点结束时**写入。节点执行**中途**断线时:
- 该节点的 partial tokens **已发** 到前端但 **未 checkpoint**
- 重连后该节点要 **重跑** → 产生重复 token
- 前端无法去重(没有 token 级 id)

**建议修复**:
1. **节点级粒度重放**:重连后从 `last_seen_checkpoint_id` 之后的**下一个节点**开始重跑,丢弃断线节点的 partial tokens
2. **前端显式 drop**:断线时丢弃当前节点的所有 `token.delta`,直至下一个 `node.started` 事件
3. **协议补充**:`state.snapshot` 事件应包含 `current_node` 字段,前端可据此判断是否完成

**影响模块**: M14(LangGraph 基建)、M15(Interview 子图)、M23(前端迁移)

---

### A5. interview ↔ ability_diagnose 子图间数据传递缺失

**现象**:
- §7.3 强调「5 个子图各自独立,**不共享 GraphState**」
- §7.1 「面试结束时异步触发 ability_diagnose」

**矛盾**: ability_diagnose 子图怎样获取 interview 的评分(`per_question_score`、`questions_asked`)?

**建议修复**:
- **触发方式**:ARQ job 仅传 `interview_session.id`,**不传任何业务数据**
- **数据获取**:ability_diagnose 子图通过 `query_interview_score(session_id)` 工具从业务表读取
- **补充工具**(§16.1 缺失):新增 `query_interview_score`、`query_session_dimensions` 等工具
- **缓存优化**(可选):ability_diagnose 入口节点 `aggregate_scores` 先全量加载到 GraphState,避免后续节点重复查询

**影响模块**: M14(工具系统)、M15(Interview 子图)、M18(Ability Diagnose 子图)

---

## 🟡 重要问题(8 项)

### A6. `interview_sessions.thread_id` 与 `checkpoint_ns` 命名空间约束未规范化

**现象**:
- §3.2 thread_id 为 text
- §7.3 每个子图独立 `checkpoint_ns`(与 graph_name 同名)
- 但 interview 结束时触发 ability_diagnose,使用同一个 session_id 派生新 thread_id 还是续用?未明示

**建议修复**:
- 在 §7.3 表格新增一列「thread_id 派生规则」:
  - `interview`: `session_id`(直接复用业务 id)
  - `ability_diagnose`: `f"{session_id}::diagnose"`
  - `resume_optimize`: `branch_id`
  - `error_coach`: `f"{user_id}:{error_question_id}:{started_at_ms}"`(参见 A7)
  - `general_coach`: `conversation_id`(uuid 新生成)
- 在 `ai_conversations.thread_id` 列建立**唯一索引**:`UNIQUE (thread_id, checkpoint_ns)`

**影响模块**: M14(LangGraph 基建)、M15-M19(各 Agent 子图)

---

### A7. `error_coach` 的 thread_id 重复练习冲突

**现象**:
- §7.3 error_coach 的 thread_id 来源 `error_question.id`
- 但同一题目多次练习需要不同 thread 还是续用?未明示

**建议修复**:
- **决议**:每次启动 error_coach 创建新 thread_id = `f"{user_id}:{error_question_id}:{started_at_ms}"`
- **理由**:① 每次练习是独立指导会话,GraphState 不需续接 ② 历史练习需要独立留痕 ③ 避免悲观锁(同题目两端同时练习)

**影响模块**: M14、M17(Error Coach 子图)

---

### A8. `monthly_token_quota` 重置机制缺失

**现象**:
- §3.2 `users` 表有 `monthly_token_quota` / `monthly_token_used`
- 无重置时间、跨月超限降级策略

**建议修复**:
- **重置时间**:每月 1 日 00:00 UTC ARQ 定时任务 → `UPDATE users SET monthly_token_used=0`
- **超限行为**:`LLMRouter` 在调用前预扣 token,超限抛 `QuotaExceededError`,Agent 节点捕获 → 推 WS `error` 事件 → 前端提示订阅升级
- **预留**:`users` 表加 `quota_reset_at timestamptz`,跟踪上次重置时间,便于按订阅日定制(而非自然月)

**影响模块**: M04(账号)、M14(工具/限流)、M22(可观测)

---

### A9. `resume_versions` 的 diff 存储字段缺失

**现象**:
- §6.3 「重要版本存完整快照,自动版本存 diff(JSON Patch RFC 6902)」
- §3.2 表 `resume_versions(snapshot_json, version_no, author_type)` **未体现 diff 字段**

**建议修复**:补字段:
```
is_full_snapshot BOOL NOT NULL DEFAULT false,
base_version_id UUID NULL REFERENCES resume_versions(id),
diff_patch JSONB NULL,
trigger TEXT NOT NULL  -- manual / auto / ai
```
- 重要版本:`is_full_snapshot=true, snapshot_json=完整, diff_patch=NULL`
- 自动版本:`is_full_snapshot=false, snapshot_json=NULL, diff_patch=JSON Patch, base_version_id=指向最近完整版本`
- 查询时:遇 diff 版本,递归找到 base 后应用 patch 还原

**影响模块**: M07(版本管理)

---

### A10. 导出 / 导入时加密字段的处理未明确

**现象**:
- §9.3 用户可一键导出全量数据为 zip
- §3.3 身份证 / 真实姓名 / 薪资 / AI 对话 AES-256-GCM 加密

**矛盾**: 导出 zip 中加密字段是「解密后的明文」还是「带加密上下文的密文」?导入到新账号时如何处理?

**建议修复**:
- **导出**:zip 中存**明文**(已经过用户身份二次验证 + 24h 一次性签名 URL),用户对自己的数据有完整可读权
- **导入**:按导入用户的加密密钥重新加密;同一账号导入则直接覆盖,跨账号导入(场景:账号注销重建)走「确认提示 + 字段映射」流程
- **安全**:zip 文件本身可选支持密码保护(用户在导出时设置),导入时输入密码解压
- **审计**:导出 / 导入操作必入 `audit_logs`,记录 `target_type='full_export'` + 字段清单

**影响模块**: M21(导入导出)、M22(审计)

---

### A11. 设备管理实体缺失

**现象**:
- §4.2 限制 5 个活跃设备 + 设备指纹(UA + 屏幕 + 时区)
- §3.2 仅 `auth_sessions(user_id, device_id, refresh_token_hash, expires_at, last_seen_at)`
- 无 `devices` 表

**建议修复**(任选):
1. **方案 A(轻量,推荐)**:把设备元数据合入 `auth_sessions`,加字段:
   ```
   device_name TEXT NULL,         -- 用户自定义名(如 "MacBook")
   device_fingerprint TEXT NOT NULL,
   last_seen_ip INET NULL,
   trusted_at TIMESTAMPTZ NULL    -- 信任设备(免 MFA)
   ```
2. **方案 B(规范)**:新增 `devices` 表 + `auth_sessions.device_uuid` 外键,设备列表与会话解耦(支持「设备失而复得」场景)

**影响模块**: M04(账号)、M05(会话设备)

---

### A12. `tasks` 自动触发器实现位置不明 + 状态值需校对

**现象**:
- §8.1「简历被标记 submitted → 自动创建准备 X 公司面试任务」
- §3.2 `resume_branches.status` 字段含 `status` 但未列出枚举值(mockData.ts 中实际是 draft/optimizing/ready/submitted)
- 触发机制(DB trigger / 应用层服务 / 事件总线)未明示

**建议修复**:
- **实现位置**:应用层 `ResumeBranchService.mark_submitted()` 显式调 `TaskService.create_interview_prep_task()`,**不使用 DB trigger**(便于测试、审计、补偿)
- **状态枚举**:明确 `resume_branches.status` 枚举:`draft | optimizing | ready | submitted | archived`
- **幂等**:同一 branch 多次 mark_submitted 仅创建一次任务(以 branch_id + task.type='interview_prep' 唯一)
- **审计**:写 `activities` 记录「触发了任务创建」

**影响模块**: M06(简历分支)、M10(任务活动流)

---

### A13. 软删除标识与隐含约定矛盾

**现象**:
- §3.4「所有业务表包含 `deleted_at (timestamptz nullable)`」
- §3.2 实体清单的「关键字段」列**没有体现** deleted_at / created_at / updated_at

**建议修复**:
- §3.2 表头加显式标注:「(所有业务表隐含 `id (uuid)` + `user_id` + `created_at` + `updated_at` + `deleted_at`)」
- 各模块文档的「§4 数据模型」段也需补全这些字段
- 提供 SQLAlchemy Mixin:`TimestampedMixin`、`SoftDeletableMixin`、`TenantScopedMixin`,所有领域模型继承

**影响模块**: M02(数据库)、所有领域模块(M06-M11)

---

### A14. WebSocket 频道事件文档冗余

**现象**:
- §10.6 与 §15.2 重复列出 `agent.{thread_id}` 频道的 9 个事件
- 但前者侧重「频道清单」,后者侧重「前端如何处理」

**建议修复**:
- §10.6 保留「频道与事件清单」(后端契约面)
- §15.2 改为「前端事件处理对照表」(消除字段重复,只描述 UI 反应)
- 模块文档中:M14 引用 §10.6;M23(前端迁移)引用 §15.2

**影响模块**: M14(数据面)、M23(前端迁移)

---

## 🔵 建议级问题(4 项)

### A15. `interview_reports` 与 `ability_dimensions` 写入时序竞争

**现象**:
- §7.1 结束面试时既写 `interview_reports`(同步),又异步触发 `ability_diagnose`(写 `ability_dimensions`)

**建议**:
- **明确语义**:面试报告必须在面试 thread 同一事务中写入(用户可立即看到报告)
- **能力画像**:通过独立 ARQ job 异步更新,失败可重试(可容忍延迟)
- 前端展示「能力维度更新中…」骨架,完成后由 WS 推 `ability.updated` 触发刷新

**影响模块**: M15(Interview 子图)、M18(Ability Diagnose 子图)

---

### A16. `audit_logs` 字段粒度过浅

**现象**:
- §3.2 `audit_logs(actor_id, action, target_type, target_id, ip, ua, occurred_at)`
- §11.3 要求记录「敏感字段读写 + 上下文」

**建议**:补字段:
```
request_id UUID NOT NULL,
endpoint TEXT NULL,              -- e.g. "POST /api/v1/users/me"
changed_fields JSONB NULL,       -- 读取时为 NULL;写入时为 {"field": [old, new]}
result TEXT NULL,                -- success / failed / forbidden
duration_ms INT NULL
```

**影响模块**: M22(审计)

---

### A17. LangSmith 启用与未决项冲突

**现象**:
- §11.3 将 LangSmith 描述为「默认接入」
- §13.1 未决项列出「LangSmith 是否启用涉及合规决策」

**建议**:
- §11.3 改为「**可选接入**,通过 `config/observability.yaml` 开关控制,需经合规评审」
- 若启用,必须在 `LANGSMITH_API_KEY` 缺失时 graceful degrade(不报错,仅警告)

**影响模块**: M22(可观测)

---

## 修复策略

| 优先级 | 修复时间 | 模块开发影响 |
|---|---|---|
| 🔴 阻塞性 (A1-A5) | **必须** 在任何模块开工前完成 v0.3 修订 | 不修订则后端 / Agent 子图大概率返工 |
| 🟡 重要 (A6-A14) | 模块设计阶段(技术评审会)最终拍板 | 允许平行开工,模块文档「§7 待澄清」段标注假设 |
| 🔵 建议 (A15-A17) | 允许后置到 v0.4 | 不影响 MVP 上线 |

## 与模块文档的反链关系

每份 `docs/modules/M{NN}-*.md` 的「§7 待澄清」段会按 `[A{n}]` 格式反链回本文档,允许快速跳转。修订完成的项,建议在本文档的对应小节加 `> ✅ v0.3 已修订 (2026-MM-DD)` 标注,而非删除小节(保留历史决策上下文)。
