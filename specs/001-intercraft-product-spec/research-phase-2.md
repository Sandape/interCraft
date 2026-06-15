# Phase 2 Research: P1 业务实体上线

**Status**: Phase 0 output · **Date**: 2026-06-13 · **Spec**: [spec.md](./spec.md) | **Phase 1 Research**: [research.md](./research.md) | **Phase 2 Plan**: [phase-2.md](./phase-2.md)

> 本文档记录 Phase 2 中**仍然存在的不确定点**与最终决议;不再讨论已经写进模块文档(M08-M11)且无歧义的「默认选择」。所有决议都在 spec §6 假设的延展 + 2026-06-13 澄清 5 项决议之内,**没有**违反宪法(Constitution)。

## 0. 上下文

Phase 2 目标(参见 spec §5.2):「Profile / Jobs / 错题本(无 Agent)的纯 CRUD 部分上线,前端 mock 切换到真实 API」。澄清 5 项(2026-06-13)已对范围做收敛:A8 月度配额 = UTC cron,A12 任务幂等 = UNIQUE + find_or_create,M11 = 只读 list/get,M08 数据源 = 仅手动创建,Settings 基础 = 资料 tab。

需要落地的能力:后端 4 模块(M08/M09/M10/M11)+ M04 user_credentials 开放 + M22 scheduler + 1 个 ARQ cron + 1 个 Alembic 迁移(7 张表);前端 4 块(Profile / Jobs / ErrorBook / Settings 资料 tab)+ 6 个 Repository + 13 个 hook(query × 6 + mutation × 7)。

**Phase 2 不涉及**:LangGraph(M14+)、悲观锁(M12)、离线/Outbox(M13)、Agent 子图(M16/M17/M18/M19)、WS 业务端点、Settings 其余 3 tab、Dashboard 切真实。

## 1. 已知决策(从 spec §6 + Phase 1 research + 澄清 5 项继承)

| # | 决策 | 来源 | Phase 2 是否需要进一步研究 |
|---|---|---|---|
| D-1 | 后端 = FastAPI (Python 3.11+) + SQLAlchemy 2.0 async + asyncpg | spec §6 A5 / Phase 1 research D-1 | 否 |
| D-2 | DB = PostgreSQL 15(在线托管,T008b 2026-06-12 解封)| Phase 1 research D-2 | 否 |
| D-3 | 队列 = ARQ(非 Celery) | spec §6 A10 / Phase 1 research D-3 | 否 |
| D-4 | 缓存/Pub-Sub = Redis 7 | Phase 1 research D-4 | 否 |
| D-5 | 加密 = AES-256-GCM,密钥从环境变量读 | spec §6 A11 / Phase 1 research D-5 | 否 |
| D-6 | 鉴权 = JWT(access 15min + refresh 7d) | Phase 1 research D-6 | 否 |
| D-7 | RLS = `SET LOCAL app.user_id = :uuid` + 所有业务表启用 | Phase 1 research D-10 | **是**:7 张新表必须遵循 |
| D-8 | 月度 token 配额 = ARQ cron 每月 1 日 00:00 UTC 批量重置 | 澄清 Q1(2026-06-13)| **是**:cron 注册细节 |
| D-9 | 任务幂等 = DB `UNIQUE (user_id, type, related_entity_id)` + service `find_or_create` | 澄清 Q2(2026-06-13)| 否 |
| D-10 | M11 面试历史 = 只读 list/get,无 create/update/delete | 澄清 Q3(2026-06-13)| 否 |
| D-11 | 错题 Phase 2 数据源 = 仅手动创建(FR-042),无 seed | 澄清 Q4(2026-06-13)| 否 |
| D-12 | Settings 基础部分 = 「资料」tab,其他 tab 留 mock | 澄清 Q5(2026-06-13)| 否 |
| D-13 | 前端 = TypeScript strict + React 18 + Vite + TailwindCSS + Zustand + React Query + openapi-typescript | Phase 1 research D-15~D-19 | 否 |
| D-14 | 错题状态机 = `fresh / practicing / mastered` + `frequency (0-3)` | spec FR-041 | **是**:状态转换合法性矩阵 |
| D-15 | 6 维度能力画像 = 技术深度/架构能力/工程实践/沟通表达/算法能力/业务理解 | spec §3.2 + mockData `abilityDimensions.ts` | **是**:子项 sub_keys 命名锁定 |
| D-16 | Jobs 状态 = `applied / test / oa / hr / offer / rejected / withdrawn` | spec §3.2 `jobs.status` | **是**:触发 task 的 status 集合 |
| D-17 | 任务 `type` 枚举 = `interview_prep / branch_optimize / application_followup / manual` | spec FR-050 延伸 | **是**:枚举清单 |
| D-18 | 活动流分页 = 游标分页(forward-only,base64 opaque)| spec FR-051 | **是**:cursor 编码格式 |

## 2. Phase 2 需要进一步研究的不确定点

### R-1:游标分页的 cursor 编码方案

**问题**:activities / 后续其他长列表(Phase 4 消息流、Phase 5 资源)需要稳定、可调试、跨端一致的游标格式。简单方案 = base64(JSON) ;严谨方案 = base64(`occurred_at|id`,签名);最简方案 = 明文(不推荐)。

**研究范围**:
- 评估 base64(JSON.stringify({occurred_at, id})) 的可读性、调试便利性、安全影响
- 评估「游标不可伪造」需求 — 游标仅用于断点续读,无需抗篡改(用户可改 token 即可读到任意 cursor,无安全风险)
- 评估跨端 parity:Python `base64.urlsafe_b64encode(json.dumps(...).encode())` ↔ TS `btoa(JSON.stringify(...))` 等价
- 评估 limit 边界:1-50,默认 20

**评估结论**:
- 选 **base64url(JSON({ts, id}))** + `sort=desc` 固定为时间倒序;cursor 不签名
- 库沿用 Python stdlib `base64` + `json`,无新增依赖
- 前端沿用 `btoa(JSON.stringify(...))` 或 `URLSafeBase64` 库;TS 端复用 `btoa`

**理由**:
- 简单:零依赖,跨端实现可读
- 稳定:游标包含复合主键,新增/删除行不会导致「跳过」或「重复」
- 性能:游标是 `occurred_at` + `id` 复合索引扫描,P95 ≤ 50ms(本地 DB,小数据集)
- 演进:若 Phase 4 引入「乱序插入」场景(如 WS 异步消息),可平滑升级到「cursor 含 sequence_no」

**被拒方案**:
- **HMAC 签名 cursor**:安全上不必要(RLS 已强制 user_id 隔离),徒增复杂度
- **明文 cursor**:可读但易被前端误以为是 id,跨端序列化麻烦
- **`page=2` 偏移分页**:不抗插入/删除,Phase 4 消息流会出 bug

**产出**:`app/core/pagination.py`(`encode_cursor / decode_cursor`)+ `app/domain/pagination.py`(`CursorPage[T]` 泛型)+ `src/lib/cursor.ts`(TS 端对称)。

### R-2:AbilityDimension 6 维度的子项(sub_keys)定义

**问题**:spec §3.2 写「每个维度包含 3-5 个子项」但未枚举。mockData `src/data/mockData.ts:abilityDimensions` 已锁定 18 个子项(6 维 × 3 子项)。Phase 2 DB 设计有两条路:
- **方案 A**:子项存 JSONB 列(单表 `ability_dimensions`,每行 `sub_scores: {sub_key: score}`)
- **方案 B**:子项独立表(`ability_sub_items`)

**研究范围**:
- 评估方案 A vs B 的演进成本:Phase 5 用户能否禁用某维度(spec Q-9-1)、Phase 6 历史快照粒度
- 评估 mockData 字段 `sub_scores` 命名与 spec FR-030 的 `sub_key` 对齐

**评估结论**:
- 选 **方案 A(JSONB)** — 与 spec §3.2 `ability_dimensions` 实体表的「`sub_key`」字段保持一致(子项作为 `sub_key` 字符串存 JSONB,非独立行)
- 子项命名以 mockData 为准,锁定为:
  - `tech_depth`:`fundamentals / system_design / depth_specialty`
  - `architecture`:`decomposition / tradeoffs / scalability`
  - `engineering_practice`:`code_quality / testing / observability`
  - `communication`:`clarity / structure / conciseness`
  - `algorithm`:`data_structures / complexity / edge_cases`
  - `business`:`domain_knowledge / product_sense / user_empathy`
- 字段名:`sub_scores JSONB NOT NULL DEFAULT '{}'::jsonb`(结构 `{sub_key: {actual: 0-10, ideal: 0-10}}`)
- 新用户注册时 seed 6 行,所有 `actual=0, ideal=10`(空态),前端展示 0 雷达图

**理由**:
- JSONB 灵活:Phase 5 可加新子项不改 schema
- 与 mockData 对齐:前端不需重新适配
- 单表查询:`SELECT * FROM ability_dimensions WHERE user_id=:u`,O(6) 行

**被拒方案**:
- **方案 B(独立表)**:Phase 1 决议「v1.1 再独立」(M09 §7);Phase 2 没必要前置
- **完全 JSON 化(无主表)**:失去 6 维度 enum 校验,前端的 `dimension_key` 弱类型

**Phase 2 写路径范围**:仅注册时 seed + 用户手动 PATCH `sub_scores`(`PATCH /ability-dimensions/{dimension_key}`)开放供用户校正;Phase 4 M18 异步聚合再叠加。

### R-3:任务触发器位置 — 单独 `triggers.py` vs service 内调用

**问题**:Job status 变更 → 创建 task。两种实现:
- **方案 A**:`JobService.update_status` 内显式 `await TaskService.find_or_create(...)`
- **方案 B**:`app/modules/jobs/triggers.py` 集中注册钩子,JobService 触发事件,TaskService 监听

**研究范围**:
- 评估「显式调用」的可读性与测试便利性
- 评估「事件监听」在 Phase 3 outbox 重放场景的契合度
- 评估 spec M10 §7 决议(`M06 显式调用 TaskService.create_interview_prep_task`)

**评估结论**:
- 选 **方案 A(显式调用)** + 抽 `app/modules/tasks/service.py::create_or_get_task()` 静态方法
- JobService 持 TaskService 引用(DI 注入),update_status 成功后调用:
  ```python
  await TaskService.create_or_get_task(
      user_id=job.user_id,
      type=TaskType.INTERVIEW_PREP,
      related_entity_id=job.id,
      title=f"准备 {job.company} · {job.position} 面试",
  )
  ```
- `tasks/triggers.py` 留空(占位),Phase 3 outbox 引入后再启用

**理由**:
- 简单,显式优于隐式(spec M10 §7 决议)
- 易于测试:JobService 单测可 mock TaskService
- Phase 3 outbox 重放:同一 outbox 事件触发 JobService → TaskService;幂等键已就位
- 不引入事件总线(Phase 5 子图触发会引入,Phase 2 不必)

**被拒方案**:
- **事件总线 / signals**:Phase 2 价值密度低,徒增调试成本
- **DB trigger(PG trigger)**:违反 Constitution(不允许即兴 SQL,业务逻辑必须在 app 层)

### R-4:ARQ cron 月度配额重置的时钟漂移

**问题**:本地 Windows 开发机时钟可能漂移,`quota_reset_at` 字段是按 `func.now()`(PostgreSQL 端时间)写入。cron 由 ARQ worker 进程触发,worker 进程时钟与 PG 端时钟可能不一致。

**研究范围**:
- ARQ cron 配置:从 `app/workers/main.py` `cron_jobs` 列表注册
- 时间源:用 `datetime.now(timezone.utc)`(应用层 UTC)还是 `func.now()`(DB 端)
- 漂移检测:每次重置前后 `SELECT now()` 与 `app.current_utc` 对比

**评估结论**:
- 选 **应用层 UTC**(`datetime.now(timezone.utc)`)作为 cron 触发条件
- 任务函数 `monthly_quota_reset(ctx)`:
  ```python
  async def monthly_quota_reset(ctx):
      now = datetime.now(timezone.utc)
      if now.day != 1 or now.hour != 0 or now.minute < 5:
          # 容错窗口:每月 1 日 00:00-00:05 触发
          return {"skipped": True, "reason": "outside window"}
      result = await ctx["db"].execute(
          update(User)
          .where(User.subscription.in_(["free", "pro"]))
          .values(monthly_token_used=0, quota_reset_at=now)
      )
      logger.info("monthly_quota_reset.completed", count=result.rowcount)
  ```
- ARQ cron 配置:`cron_jobs=[{"name": "monthly_quota_reset", "cron": "0 0 1 * *", "coroutine": monthly_quota_reset}]`

**理由**:
- 简单,应用层 UTC 显式
- 容错窗口(00:00-00:05)避免 ARQ tick 漂移导致漏触发
- `quota_reset_at` 字段保留(M04 已就位),便于 Phase 6 按订阅日定制

**被拒方案**:
- **DB 端 trigger**:不允许即兴 SQL
- **每秒级 check 任务**:浪费 worker 资源
- **Phase 4 才落地**:违背澄清 Q1 决议(Phase 2 落地占位)

### R-5:错题状态机转换矩阵

**问题**:`fresh → practicing → mastered` 简化版不够。Phase 5 Error Coach 子图会改 frequency 和 status。需要 Phase 2 锁定 Phase 2 范围的状态转换,Phase 5 兼容演进。

**研究范围**:
- 评估 frequency 字段的「谁可改」:Phase 2 手动 + Phase 5 Error Coach 自动
- 评估 status 与 frequency 的一致性:`mastered` 必须 `frequency=0`,`practicing` 必须 `1 <= frequency <= 2`,`fresh` 必须 `frequency=3`
- 评估软删(归档)是否独立维度:`status` 字段已有 `archived` 吗?(答案:否,归档 = `deleted_at`)

**评估结论**:
- 状态机合法转换(Phase 2):
  ```
  fresh(freq=3) ─手动 edit/practice─► practicing(freq=1..2) ─手动 mark_mastered─► mastered(freq=0)
                                                                                  │
                                                                                  └─反悔: mastered ─手动 reset─► fresh(freq=3)
  ```
- 任意状态可 `soft_delete(archived)`:`deleted_at` 字段就位(SoftDeletableMixin),Repository 默认过滤
- `errors/service.py::reduce_status(current, target, frequency)` 纯函数封装合法转换,非法抛 `InvalidStateTransitionError`
- 字段:`status enum('fresh','practicing','mastered','archived')` + `frequency int CHECK (frequency BETWEEN 0 AND 3)`
- 一致性:`status='mastered'` MUST `frequency=0`;Repository save 校验
- Phase 5 Error Coach:沿用 `reduce_status`,只是 trigger 来源是 Agent 评分而非手动

**理由**:
- 状态机封装纯函数,易测试
- 一致性约束在 save 校验,DB 兜底
- 兼容 Phase 5:同一函数,不同 trigger

**被拒方案**:
- **不校验一致性**:会出现 `mastered` + `frequency=2` 的脏数据
- **无 archived 终态**:软删走 `deleted_at` 更一致(Spec A13)

### R-6:Jobs 状态触发的「准备面试」任务

**问题**:Job 创建/状态变更时,哪些状态触发任务创建?`applied` only?还是任何 status 变更?

**研究范围**:
- 评估 `applied` 是初始态(Jobs 表创建时默认 `applied`),还是用户显式设置
- 评估 `withdrawn` / `rejected` 是否需要任务清理
- 评估幂等键:`UNIQUE (user_id, type, related_entity_id)` 中 `related_entity_id=job.id`,`type=interview_prep` — 同一 job 仅一条任务

**评估结论**:
- `Jobs.status` 默认 `'applied'`(schema 层面)
- 触发条件:**创建时**(`status='applied'` 立即触发 1 次)+ **`applied` 状态下状态推进到 `test`/`oa`/`hr`/`offer` 时**(每次推进更新任务 `title` 提示阶段,不改 status)
- `withdrawn` / `rejected` → 不创建任务;若有「准备面试」任务,状态置 `archived`
- 幂等键:`(user_id, 'interview_prep', job.id)` 唯一;同一 job 多次状态推进只更新 title,不再 insert

**理由**:
- 任务生命周期与 job 强绑定,符合 spec FR-050 语义
- `withdrawn` 任务归档不物理删(用户回看历史需要)
- 推进时更新 title(`准备字节·高级前端 · 一面`)提示用户当前阶段

**被拒方案**:
- **创建时才触发**:`applied` → `test` 用户无感知,任务标题不变
- **任何状态变更都创建新任务**:任务列表爆炸,违反 FR-053 幂等原则

### R-7:Settings「资料」tab 的 PATCH 字段范围

**问题**:Phase 1 已有 `PATCH /users/me` 端点(M04,部分字段)。Phase 2 资料 tab 需要写哪些字段?

**研究范围**:
- mockData `userProfile.ts` 字段:`name / title / yearsOfExperience / targetRole / email(只读)/ subscription(只读)`
- spec FR-005 设备指纹 = 不写到 User 表,AuthSession 已有
- M04 §4 schema:`display_name / title / years_of_experience / target_role`

**评估结论**:
- `PATCH /users/me` 开放字段:`display_name / title / years_of_experience / target_role`(4 个)
- 不开放:`email`(鉴权凭据,M04 不允许改)、`subscription`(Phase 6)、`monthly_token_*`(系统管)、`llm_provider_pref`(Phase 4)
- 字段校验:`display_name` 长度 1-32,`title` 长度 1-64,`years_of_experience` 0-50,`target_role` 长度 1-64

**理由**:
- 与 mockData 字段对齐,前端不需重写
- 与宪法 A11 一致:敏感字段走单独 endpoint(M04 §4 user_credentials)

**被拒方案**:
- **全部字段开放**:会暴露鉴权/订阅内部字段,违反单一职责

### R-8:错题 `dimension` 字段是否可选

**问题**:Phase 2 用户手动创建错题时,可能不知道归到哪个 6 维度。

**研究范围**:
- 评估「必填 dimension」:强制用户归类,数据更干净
- 评估「可选 dimension」:降低创建门槛,数据有缺失
- 评估 M08 §7 决议:`MVP 用受控词表 + 自由文本兜底`

**评估结论**:
- `dimension` 字段**可选**(`dimension TEXT NULL, CHECK (dimension IN ('tech_depth','architecture','engineering_practice','communication','algorithm','business') OR dimension IS NULL)`)
- 列表页显示「未归类」徽章
- Phase 4 FR-040 自动入库时,dimension 必填(从面试报告来)

**理由**:
- Phase 2 手动创建门槛低
- 列表可按 dimension 过滤
- 软约束而非硬约束,符合 M08 §7 决议

## 3. 阶段依赖与产出

Phase 2 任务依赖(简化版):

```
R-1 (cursor 编码) ─► 阶段 1.1 工具
R-2 (维度子项)   ─► 阶段 2C M09 seed
R-3 (任务触发)   ─► 阶段 2D M10 jobs ↔ tasks
R-4 (ARQ cron)   ─► 阶段 1.4 scheduler + 1.5 monthly_quota_reset
R-5 (错题 FSM)   ─► 阶段 2B M08 service
R-6 (Jobs 触发)  ─► 阶段 2D M10
R-7 (Settings)   ─► 阶段 4.4 Settings 资料 tab
R-8 (dimension)  ─► 阶段 2B M08
```

无循环依赖;R-1 须先于 R-3;R-2 须先于 R-3(任务 type 枚举含 `branch_optimize` 不依赖 R-2,实际无依赖)。

## 4. 决议汇总(本 Phase 2)

| # | 决议 | 落地位置 |
|---|---|---|
| DEC-P2-1 | 游标分页 = base64url(JSON({ts,id})),forward-only,limit 1-50 | `app/core/pagination.py` + `src/lib/cursor.ts` |
| DEC-P2-2 | AbilityDimension 子项 = 18 个 sub_keys(JSONB),命名锁定见 R-2 | `app/modules/abilities/models.py` + fixtures |
| DEC-P2-3 | 任务触发 = 显式调用 TaskService.find_or_create,JobService 注入依赖 | `app/modules/jobs/service.py` + `app/modules/tasks/service.py` |
| DEC-P2-4 | 月度配额重置 = ARQ cron `0 0 1 * *` UTC,容错窗口 00:00-00:05 | `app/workers/main.py` + `app/workers/tasks/monthly_quota_reset.py` |
| DEC-P2-5 | 错题状态机 = `reduce_status(current, target, frequency)` 纯函数;mastered 必 frequency=0;archived 走 soft_delete | `app/modules/errors/service.py` |
| DEC-P2-6 | Jobs 触发任务 = 创建时 + applied→test/oa/hr/offer 推进时;withdrawn/rejected 归档旧任务;幂等键 (user_id, 'interview_prep', job.id) | `app/modules/jobs/service.py` |
| DEC-P2-7 | Settings 资料 tab PATCH 字段 = display_name / title / years_of_experience / target_role;其他字段不改 | `app/modules/auth/api.py` + `app/modules/auth/schemas.py` |
| DEC-P2-8 | 错题 dimension 字段 = NULLABLE,列表显示「未归类」 | `app/modules/errors/models.py` |

## 5. 与 Phase 1 DEC-* 的衔接

| Phase 1 决议 | Phase 2 是否复用 | 说明 |
|---|---|---|
| DEC-1 fastapi-users | 复用,无改动 | M04 鉴权不变 |
| DEC-2 uuidv7 | 复用,无改动 | 7 张新表全部用 uuidv7 PK |
| DEC-3 fractional-indexing | 不适用 | Phase 2 无拖拽排序需求 |
| DEC-4 JSON Patch | 不适用 | Phase 2 无版本快照需求 |
| DEC-5 AES-256-GCM | 复用,user_credentials Phase 2 开放 | M03 crypto 模块不变 |
| DEC-6 Vitest + MSW + Playwright | 复用 | 4 块前端迁移都用同一栈 |
| DEC-7 js-sha256 | 不适用 | 设备指纹 Phase 1 已用,Phase 2 无新需求 |
| DEC-8 (Phase 1 无对应) | — | — |
| DEC-9 openapi-typescript | 复用,Phase 2 重建 | 端点 23 → 30+ |
| DEC-10 WS 客户端骨架 | 复用,无业务 | Phase 2 不引入新 WS 端点 |
| DEC-11 (Phase 1 无对应) | — | — |
| DEC-12 (Phase 1 无对应) | — | — |

无 Phase 1 决议被推翻;全部沿用。
