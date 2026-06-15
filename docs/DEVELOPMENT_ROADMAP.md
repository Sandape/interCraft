# InterCraft 持久化 · 最优开发路线图

> 版本: v1.0 · 2026-06-12
> 对应原文档: [PERSISTENCE_REQUIREMENTS.md](./PERSISTENCE_REQUIREMENTS.md) v0.2
> 模块详情: [docs/modules/](./modules/README.md)
> 一致性说明: [ANALYSIS_REPORT.md](./ANALYSIS_REPORT.md)

---

## 全景图

将 23 个模块拆分到 **7 个领域**,通过依赖拓扑排序得到一条 **11 步关键路径** 与多个并行机会。建议 **2 周/Sprint** 推进,共 **8 个 Sprint** 完成 MVP。

---

## 1. 模块依赖拓扑

```
┌─────────────────────────────────────────────────────────────────────────┐
│  A. 后端基础 (P0,必须串行)                                              │
│   M01 项目骨架  →  M02 数据库 & ORM  →  M03 缓存/队列/加密              │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  B. 账号 & 权限 (P0,串行)                                               │
│   M04 账号 & 认证  →  M05 会话 & 设备 & RLS 启用                        │
└────────────────────┬───────────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬─────────────────┐
        ▼            ▼            ▼                 ▼
┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│ C. 业务实体  │ │ D. 同步  │ │ E. AI    │ │ F. 全局能力  │
│ (并行开发)   │ │ & 离线   │ │ 编排     │ │              │
└──────┬───────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘
       │              │            │              │
       ▼              ▼            ▼              │
M06 简历分支&块   M12 锁&WS    M14 LangGraph     M20 生命周期
M07 版本管理      M13 客户端   基建(超核心)     M21 导入导出
M08 错题本                     ─┬─               M22 审计&对账
M09 能力画像                    │
M10 任务&活动流                 ├─ M15 Interview
M11 面试历史                    ├─ M16 ResumeOpt
       │                        ├─ M17 ErrCoach
       │                        ├─ M18 AbilDiag
       │                        └─ M19 GenCoach
       │
       └───── 任一就绪后 ───────► M23 前端迁移
                                    (Repository + 状态层 + 页面替换)
```

**符号约定**:
- `→` 强依赖(下游必须等上游完成所有验收)
- `─┬─` 一对多依赖(上游为下游们提供共同基础)
- `⇢`(下文使用)弱依赖,可并行启动但需要协调接口契约

---

## 2. 关键路径(11 步串行)

> 任何一步延迟都会推迟 MVP demo

```
M01 项目骨架
  └► M02 数据库 & ORM
       └► M03 缓存/队列/加密
            └► M04 账号 & 认证
                 └► M05 会话 & RLS 启用
                      └► M06 简历分支 & 块
                           └► M11 面试历史(纯 CRUD)
                                └► M14 LangGraph 基建
                                     └► M15 Interview 子图
                                          └► M22 审计 / 对账
                                               └► M23 前端 Demo(关键演示)
```

**总估时**(乐观,假设 2 名后端 + 1 名前端 + 0.5 DevOps): 约 **14-16 周**

---

## 3. 并行机会矩阵

| 时点 | 上游就绪 | 可并行开工模块 | 协调要点 |
|---|---|---|---|
| T0 | M02 完成 | M04(账号)+ M06(简历)+ M08(错题本) | 共用 `TenantScopedMixin`,提前约定 Repository 接口规范 |
| T1 | M03 完成 | M22(前端 Repository 抽象层 P1) | 前端可先用 mock 实现 Repository 接口,等后端 API 就绪再切换 |
| T2 | M11 完成 | M12(锁/WS)+ M13(客户端 Outbox) | 前后端联调,需对 WS 事件格式达成共识 |
| T3 | M14 完成 | M16 / M17 / M18 / M19 四个 Agent 子图 | 共享工具(§16.1)注册需先冻结 schema |
| T4 | M05 完成 | M20(生命周期)+ M21(导入导出) | 都依赖 user 与 audit 框架,约定 ARQ job 命名 |

---

## 4. 8 Sprint 里程碑(2 周/Sprint)

### Sprint 1 · 后端骨架可启动 (M01-M03)

**目标**: 一键 `docker-compose up` 起 PostgreSQL + Redis + FastAPI;Alembic 可跑迁移;ARQ Worker 可跑 dummy 任务;加密层可加解密 demo 字段。

**演示**:
- `curl http://localhost:8000/healthz` → 200
- 跑 `alembic upgrade head` 成功
- 调用 `crypto.encrypt("test") / crypto.decrypt(...)` 往返一致

**关键风险**: docker-compose 与开发机端口冲突、密钥管理(用 .env vs Vault)

---

### Sprint 2 · 账号可注册登录 (M04-M05)

**目标**: 邮箱+密码注册、登录、JWT 颁发、refresh 静默续签;5 设备限制可踢出;RLS 在所有业务表生效。

**演示**:
- 注册用户 A,登录 → 拿到 access+refresh token
- 用 token 调 `/api/v1/users/me` → 200
- 用 token 调 `/api/v1/users/{B_id}/...` → RLS 阻断
- 在 5 个浏览器登录同一账号 → 第 6 个登录踢出最早设备

**关键风险**: 第三方 OAuth(GitHub/Google)在 MVP 是否实装;`fastapi-users` vs 自研 JWT 决策(参见 §13.1)

---

### Sprint 3 · 简历可写可读 (M06-M07)

**目标**: 用户可创建/编辑/查看/删除简历分支与块,可保存版本快照,可回滚到任意历史版本。

**演示**:
- 创建核心简历(blocks ×7)
- 创建分支「应聘 A 公司」→ 浅拷贝 → 修改某块 → 深拷贝
- 手动「保存版本」→ 生成 snapshot;再连改 5 次 → 生成 diff
- 选择 v3 「回滚」→ 创建新分支指向 v3 状态

**关键风险**: 分支继承的「浅拷贝→深拷贝」语义需在 UI 与后端达成一致(参见 A9)

---

### Sprint 4 · 其余业务实体上线 (M08-M11)

**目标**: 错题本 / 能力画像 / 任务 / 活动流 / 面试历史(纯 CRUD,无 Agent)全上线,前端 mock 可切到真实 API。

**演示**:
- 调 `/api/v1/error-questions` → 返回错题列表
- 调 `/api/v1/ability-dimensions` → 返回 6 维度 + 子项
- 调 `/api/v1/ability-dimensions/history?aggregate=month` → 时序数据
- 调 `/api/v1/tasks` → 任务列表
- 调 `/api/v1/activities?cursor=&limit=20` → 游标分页

**关键风险**: 任务自动触发器(简历 submitted → 创建任务)的位置与幂等(参见 A12)

---

### Sprint 5 · 同步与离线打通 (M12-M13)

**目标**: 多端编辑触发悲观锁;离线编辑 → 联网后自动回放;WS 实时推送锁状态。

**演示**:
- 浏览器 A 进入简历编辑器 → 后端发锁 → 浏览器 B 看到「只读」UI
- 浏览器 A 关 Tab 30s → 后端自动释放锁 → B 端 WS 收到 `lock.released`
- 浏览器 A 断网 → 编辑 3 个块 → 联网 → outbox 回放 → 服务端确认

**关键风险**: 离线 + 悲观锁的语义边界(参见 A3)

---

### Sprint 6 · Interview Agent 跑通 (M14-M15)

**目标**: 全流程面试(start → 5 轮对话 → 生成报告);WS 流式 token;双源持久化 + 对账。

**演示**:
- 启动一场面试 → 收到 `node.started(intake)` → 后续 `node.started(question_gen)` → 流式 `token.delta`
- 用户回答 → 节点循环 → 5 题后触发 `report` 节点
- 查 `ai_messages` 与 `checkpoints` → (thread_id, checkpoint_id) 配对一致
- 模拟 WS 断线 → 重连携带 `last_seen_checkpoint_id` → 服务端从下一节点开始

**关键风险**: 流式 token 重放策略(A4);双源 hooks 的事务一致性(A1)

---

### Sprint 7 · 其余 Agent 上线 (M16-M19)

**目标**: 简历优化(含人类介入 interrupt)/ 错题强化 / 能力诊断(异步触发)/ 通用辅导 四子图上线。

**演示**:
- 简历优化:运行子图 → 节点暂停在 `apply_or_discard` → 前端收到 `interrupt` → 用户确认 → 落盘
- 错题强化:启动子图 → 三次答对结束 → 错题 frequency 减 1
- 能力诊断:S6 的面试结束后,自动触发 → 几秒后 `ability_dimensions` 更新
- 通用辅导:无业务锚点的问答场景

**关键风险**: 子图间数据传递(A5);工具共享时的 schema 冻结

---

### Sprint 8 · 全局能力 + 前端切换 (M20-M23)

**目标**: 软删除 30 天 / 注销 90 天清除上线;全量导出/导入;审计 + 双源对账日报;前端从 mock 完全切到真实 API。

**演示**:
- 软删除一份简历 → 进回收站 → 30 天后(模拟时间)→ 物理删除
- 一键导出 → 拿到 zip 签名 URL → 24h 后过期
- 跑对账 job → 收到 0 缺失告警(健康)
- 前端 `VITE_USE_MOCK=false` → 所有页面正常工作

**关键风险**: 加密字段在导入导出中的处理(A10);LangSmith 启用决策(A17)

---

## 5. 资源建议

| 角色 | 人数 | 投入区间 | 主要负责模块 |
|---|---|---|---|
| 后端工程师 #1 | 1 | S1-S8 全程 | A / B / C / F 域:M01-M11, M20-M22 |
| 后端工程师 #2(熟 LangGraph) | 1 | S3-S8 | D / E 域:M12-M19 |
| 前端工程师 | 1 | S5-S8 | G 域:M23 + 各 Sprint 前端集成 |
| DevOps | 0.5 | S1, S6, S8 | 容器化 / 可观测 / 灰度发布 |
| 产品 / 法务 | 0.2 | S1, S8 | §13.1 未决项决策(LLM 选型 / LangSmith 合规) |

**单人全栈兜底**: 若团队只有 1-2 人,Sprint 数延长到 12-14 个,关键路径不变。

---

## 6. 关键决策时点

| 时点 | 决策项 | 影响 | 默认建议 |
|---|---|---|---|
| Sprint 1 启动前 | LLM 提供商(OpenAI / Anthropic) | 影响整个 E 域 | Claude(参考原项目使用的 `langchain-anthropic`) |
| Sprint 1 启动前 | 鉴权方案(fastapi-users / 自研 JWT) | 影响 M04 实现细节 | fastapi-users(快速起步) |
| Sprint 1 启动前 | 队列方案(ARQ / Celery) | 影响 M03 / 异步任务 | ARQ(异步原生) |
| Sprint 4 完成前 | A1-A5 阻塞性问题修订 | 影响 M11 / M14 / M15 设计 | 见 ANALYSIS_REPORT |
| Sprint 6 启动前 | LangSmith 启用与否 | 影响可观测体验 | 启用(若数据未出境敏感) |
| Sprint 8 完成前 | 灰度发布策略(流量百分比 / Feature Flag) | 影响上线节奏 | 5% → 25% → 50% → 100% |

---

## 7. 验收门控(每个 Sprint 必过)

每个 Sprint 结束需满足:

1. **功能验收**: 上面演示场景全过
2. **测试覆盖**: 单元 ≥ 70%、集成 ≥ 50%、关键路径 E2E
3. **性能基线**: API P95 ≤ 500ms;关键 WS 推送 ≤ 200ms;LangGraph 单节点 P95 ≤ 1.5s
4. **安全检查**: 无 OWASP Top10 已知漏洞;敏感字段加密;RLS 实测不可越权
5. **文档同步**: 对应模块 .md 标注 `状态: completed` + 验收时间

---

## 8. 与一致性审视的对齐

ANALYSIS_REPORT.md 中的 17 项发现都映射到本路线图的某个 Sprint:

| 阻塞项 | 修订建议截止 | 涉及 Sprint |
|---|---|---|
| A1 三源消息流 | Sprint 4 启动前 | S4 / S6 |
| A2 checkpoints RLS | Sprint 6 启动前 | S6 |
| A3 离线 + 锁语义 | Sprint 5 启动前 | S5 |
| A4 token 流重放 | Sprint 6 启动前 | S6 |
| A5 子图间数据传递 | Sprint 7 启动前 | S6 / S7 |

🟡 重要项(A6-A14):各对应 Sprint 设计阶段拍板。

🔵 建议项(A15-A17):允许后置到 v0.4 文档优化。

---

## 9. 用法

- **PM / Tech Lead**: 用本文档制定 Sprint 计划与排期
- **工程师**: 选定模块后跳转到 `docs/modules/M{NN}-*.md` 查看详细需求
- **QA**: 用每个 Sprint 的「演示」清单做验收测试
- **新人 Onboarding**: 先读 `PERSISTENCE_REQUIREMENTS.md`(总览)→ 本路线图 → 模块文档
