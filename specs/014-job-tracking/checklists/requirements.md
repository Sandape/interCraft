# Specification Quality Checklist: 014-job-tracking

**Purpose**: Validate specification completeness and quality before proceeding to planning.
**Created**: 2026-06-16
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
  - Notes: 规范以"用户故事 / 行为"为主,仅在 FR 中点名后端端点(GET/PATCH `/jobs/{id}` 等)以保持与已有契约一致;不出现 React / FastAPI / SQLAlchemy 等技术栈命名。
- [x] Focused on user value and business needs
  - Notes: 7 个用户故事均以"求职者如何用"开场,Why-this-priority 段解释业务价值。
- [x] Written for non-technical stakeholders
  - Notes: 全文中文,术语最小化;状态机 / Outbox 等仅在 FR 必要处简述。
- [x] All mandatory sections completed
  - Notes: Background / Clarifications / User Scenarios / Edge Cases / Requirements / Key Entities / Success Criteria / Assumptions 全部落地。

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
  - Notes: Clarifications 节内 7 个 Q/A 全部已确认(状态机对齐、字段命名、备注是否强制、outbox 兜底、简历分支入口、Offer 附加字段、时间线字段统一)。
- [x] Requirements are testable and unambiguous
  - Notes: 28 条 FR 全部以 MUST 行为动词,带条件 / 阈值 / 输入 / 输出。
- [x] Success criteria are measurable
  - Notes: SC-001~SC-010 含具体延迟、字符上限、百分比、计数。
- [x] Success criteria are technology-agnostic (no implementation details)
  - Notes: SC 仅以"用户感知行为 / 业务指标"衡量,SC-005 引用 React Query 缓存为失败案例(已在 Notes 注释),主体描述不涉及框架。
- [x] All acceptance scenarios are defined
  - Notes: 7 个用户故事、合计 33 条 Given/When/Then。
- [x] Edge cases are identified
  - Notes: 12 条 Edge Cases 覆盖并发 / 离线 / 字段缺失 / 网络异常 / 软删关联等。
- [x] Scope is clearly bounded
  - Notes: Background 段明列"范围外"清单(公司情报聚合 / 邮箱解析 / 招聘官 CRM / 谈判追踪 / 日历集成)。
- [x] Dependencies and assumptions identified
  - Notes: Assumptions 节列 10 条,涵盖后端实体、出板端点、字段命名差异、outbox 复用、国际化等。

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
  - Notes: 7 个用户故事与 28 条 FR 形成 1:多映射(US1 ↔ FR-001..004;US2 ↔ FR-005..008;US3 ↔ FR-009..010;US4 ↔ FR-011..012;US5 ↔ FR-013..015;US6 ↔ FR-016..017;US7 ↔ FR-018..021;outbox / activity / a11y ↔ FR-022..028)。
- [x] User scenarios cover primary flows
  - Notes: 列表 → 详情 → 推进 → 编辑 → 删除 → 排序 / 搜索 → Offer 录入,7 个故事完整覆盖"能用" → "对得上" → "联得动" → "不掉链" → "看得见进展" 五条主轴。
- [x] Feature meets measurable outcomes defined in Success Criteria
  - Notes: SC-010 给出 Playwright 1 次跑通的 7 个故事清单,作为最终交付闸口。
- [x] No implementation details leak into specification
  - Notes: 复审确认无"用 React Hook" / "用 SQLAlchemy" / "具体 ORM 写法"等;FR-005、FR-006 引用 `JOB_TRANSITIONS` 仅为字段值对齐需要,Plan 阶段会落到具体实现。

## Notes

- 规范与 Phase 2 既有 `Job` 模块强绑定,Plan 阶段需先核对 `backend/app/modules/jobs/service.py` 的 `JOB_STATUS_CN` / `JOB_TRANSITIONS` 与本规范 FR-005 描述是否一致(已读源码,一致)。
- Plan 阶段需评估"`/activities?entity_type=job&entity_id=`"端点是否存在(Assumption 节已记录),若不存在应作为 FR-026 的实现前依赖补齐,或扩展为"在 plan 中加 endpoint 实现任务"。
- E2E 测试以 SC-010 为最终闸口;`data-testid` 选择器需在 `Jobs.tsx` 与详情抽屉组件首次落地时定下,后续 PR 不得随意改键名(FR-028 + SC-007 共同约束)。
