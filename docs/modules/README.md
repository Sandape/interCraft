# InterCraft 模块化需求文档索引

> 23 个模块的需求文档总入口。每份模块对应 `PERSISTENCE_REQUIREMENTS.md` 中的若干章节,可独立开发。

---

## 快速导航

| 类别 | 模块 |
|---|---|
| **总览** | [PERSISTENCE_REQUIREMENTS.md](../PERSISTENCE_REQUIREMENTS.md) |
| **路线图** | [DEVELOPMENT_ROADMAP.md](../DEVELOPMENT_ROADMAP.md) |
| **一致性审视** | [ANALYSIS_REPORT.md](../ANALYSIS_REPORT.md) |

---

## 模块清单(按领域)

### 领域 A · 后端基础(P0,必须串行)
| # | 模块 | 文档 | 状态 |
|---|---|---|---|
| M01 | 项目骨架 & 基础设施 | [01-infrastructure.md](./01-infrastructure.md) | draft |
| M02 | 数据库 & ORM | [02-database-orm.md](./02-database-orm.md) | draft |
| M03 | 缓存 / 队列 / 加密 | [03-cache-queue-crypto.md](./03-cache-queue-crypto.md) | draft |

### 领域 B · 账号与权限(P0,串行)
| # | 模块 | 文档 | 状态 |
|---|---|---|---|
| M04 | 账号 & 认证 | [04-account-auth.md](./04-account-auth.md) | draft |
| M05 | 会话 & 设备 & RLS 启用 | [05-session-device-rls.md](./05-session-device-rls.md) | draft |

### 领域 C · 业务实体(并行)
| # | 模块 | 文档 | 状态 |
|---|---|---|---|
| M06 | 简历分支 & 块 | [06-resume-branch-block.md](./06-resume-branch-block.md) | draft |
| M07 | 简历版本管理 | [07-resume-versioning.md](./07-resume-versioning.md) | draft |
| M08 | 错题本 | [08-error-book.md](./08-error-book.md) | draft |
| M09 | 能力画像 | [09-ability-profile.md](./09-ability-profile.md) | draft |
| M10 | 任务 & 活动流 | [10-task-activity.md](./10-task-activity.md) | draft |
| M11 | 面试历史(无 Agent) | [11-interview-history.md](./11-interview-history.md) | draft |

### 领域 D · 同步与离线
| # | 模块 | 文档 | 状态 |
|---|---|---|---|
| M12 | 悲观锁 + WS 控制面 | [12-pessimistic-lock-ws-control.md](./12-pessimistic-lock-ws-control.md) | draft |
| M13 | 客户端 IndexedDB + Outbox | [13-client-offline-sync.md](./13-client-offline-sync.md) | draft |

### 领域 E · AI 编排(LangGraph)
| # | 模块 | 文档 | 状态 |
|---|---|---|---|
| M14 | LangGraph 基础设施(超核心) | [14-langgraph-foundation.md](./14-langgraph-foundation.md) | draft |
| M15 | Interview 子图 | [15-interview-agent.md](./15-interview-agent.md) | draft |
| M16 | Resume Optimize 子图 | [16-resume-optimize-agent.md](./16-resume-optimize-agent.md) | draft |
| M17 | Error Coach 子图 | [17-error-coach-agent.md](./17-error-coach-agent.md) | draft |
| M18 | Ability Diagnose 子图(异步) | [18-ability-diagnose-agent.md](./18-ability-diagnose-agent.md) | draft |
| M19 | General Coach 子图 | [19-general-coach-agent.md](./19-general-coach-agent.md) | draft |

### 领域 F · 全局能力
| # | 模块 | 文档 | 状态 |
|---|---|---|---|
| M20 | 生命周期 / 注销 / 保留期 | [20-lifecycle-deletion-retention.md](./20-lifecycle-deletion-retention.md) | draft |
| M21 | 导入导出 | [21-import-export.md](./21-import-export.md) | draft |
| M22 | 审计 / 可观测 / 对账 | [22-audit-observability-reconciliation.md](./22-audit-observability-reconciliation.md) | draft |

### 领域 G · 前端迁移
| # | 模块 | 文档 | 状态 |
|---|---|---|---|
| M23 | 前端迁移 | [23-frontend-migration.md](./23-frontend-migration.md) | draft |

---

## 依赖关系总览

```
A: M01 → M02 → M03
B: M03 → M04 → M05
C: M05 → {M06 → M07, M08, M09, M10, M11}
D: M11 → M12 ; M12 → M13
E: M11 ∧ M03 → M14 → {M15, M16, M17, M18, M19}
F: M05 → {M20, M21} ; M14 → M22
G: 任一就绪 → M23
```

详细图见 [DEVELOPMENT_ROADMAP.md §1](../DEVELOPMENT_ROADMAP.md#1-模块依赖拓扑)。

---

## 模块文档统一骨架

```markdown
# M{NN} · {模块名}

> 状态: draft | in_progress | completed
> 所属领域: A/B/C/D/E/F/G
> 优先级: P0/P1/P2
> 引用原文档: §{x.y}

## 1. 需求摘要
## 2. 验收标准
## 3. 依赖与被依赖关系
## 4. 数据模型
## 5. 接口契约(REST / WS / 工具)
## 6. 关键设计点
## 7. 待澄清(反链 ANALYSIS_REPORT.md 的 A{n})
## 8. 实现提示(可选)
```

---

## 状态跟踪表

> 「需求文档」状态(本表)≠「代码实现」状态。需求文档完成(drafted)意味着可以分派给开发,代码实现需独立跟踪。

| 模块 | 文档状态 | 开发者 | 实现状态 | 备注 |
|---|---|---|---|---|
| M01 | drafted | — | 待启动 | 关键路径第一步 |
| M02 | drafted | — | 待启动 | |
| M03 | drafted | — | 待启动 | |
| M04 | drafted | — | 待启动 | |
| M05 | drafted | — | 待启动 | 所有业务表 RLS 启用点 |
| M06 | drafted | — | 待启动 | |
| M07 | drafted | — | 待启动 | [A9] 字段已补 |
| M08 | drafted | — | 待启动 | |
| M09 | drafted | — | 待启动 | |
| M10 | drafted | — | 待启动 | |
| M11 | drafted | — | 待启动 | [A1] interview_messages 改为 VIEW |
| M12 | drafted | — | 待启动 | |
| M13 | drafted | — | 待启动 | [A3] 离线 + 锁语义已澄清 |
| M14 | drafted | — | 待启动 | 超核心模块,所有 Agent 依赖 |
| M15 | drafted | — | 待启动 | 关键路径节点 |
| M16 | drafted | — | 待启动 | 唯一启用 interrupt 的子图 |
| M17 | drafted | — | 待启动 | [A7] 每次新建 thread |
| M18 | drafted | — | 待启动 | [A5] 通过 query 工具读跨图数据 |
| M19 | drafted | — | 待启动 | |
| M20 | drafted | — | 待启动 | |
| M21 | drafted | — | 待启动 | [A10] 加密字段处理已说明 |
| M22 | drafted | — | 待启动 | [A4] 重连重放 [A16] 字段 [A17] LangSmith 可选 |
| M23 | drafted | — | 待启动 | 依赖所有后端模块 |

---

## 用法

1. **选定模块**: 查路线图 → 确认依赖均完成 → 打开本目录对应 .md
2. **更新状态**: 模块开工时改顶部「状态: in_progress」并填入「开发者」;完成时改 「状态: completed」并填「完成日期」
3. **跨模块协调**: 模块文档「§3 依赖关系」会列出需要协调的兄弟模块,提前对接接口契约
4. **遇到原文档矛盾**: 模块文档「§7 待澄清」会反链回 [ANALYSIS_REPORT.md](../ANALYSIS_REPORT.md) 的具体 A{n} 项,按修订建议处理
