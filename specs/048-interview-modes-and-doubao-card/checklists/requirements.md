# Specification Quality Checklist: REQ-048 Interview Mode Split + Doubao Card

**Purpose**: Validate REQ-048 spec completeness and quality before proceeding to planning
**Created**: 2026-07-07
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — spec 提到了 `@vercel/og` 等技术是经用户 Q1/A 决策确认的工具选择，且写进了 Assumptions；US/FR 全部用业务语言表达
- [x] Focused on user value and business needs — 6 个 US 都从用户视角写
- [x] Written for non-technical stakeholders — 业务方能理解「快速补漏」「豆包面试」价值
- [x] All mandatory sections completed — User Scenarios & Testing、Requirements、Success Criteria、Assumptions、Key Entities 全部填充

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — 8 个 drill-down 全部通过 Q1-Q8 收集
- [x] Requirements are testable and unambiguous — 每条 FR 都写明具体动作 + 输入 + 输出
- [x] Success criteria are measurable — 22 条 SC 全部含数值（% / p95 / 数字）
- [x] Success criteria are technology-agnostic — SC 全部是用户感知维度（耗时、命中率、文件大小、字号），不绑死框架
- [x] All acceptance scenarios are defined — US-1 到 US-6 各 2-4 个 Given/When/Then
- [x] Edge cases are identified — 8 个 Edge Cases 涵盖错题集空、embedding 故障、超时、降级等
- [x] Scope is clearly bounded — Out of Scope 节列出 11 项明确不做
- [x] Dependencies and assumptions identified — Assumptions 节列出 12 条，含 pgvector/BGE/Noto 字体等关键依赖

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria — 每条 FR 都对应 US 的 Acceptance Scenario
- [x] User scenarios cover primary flows — 6 个 US 覆盖：模式入口选择、错题筛选、完整面试、豆包卡片、变体切换、错题本联动
- [x] Feature meets measurable outcomes defined in Success Criteria — SC 字段分布到 4 个能力域（可用性 / 筛选质量 / 体验 / 联动）
- [x] No implementation details leak into specification — 技术栈出现在 A-001/A-002 等 Assumption 而非 FR 中；FR-051 引用 `@vercel/og` 是经 Q1 决策的"用户批准的工具"，非开发自选

## Notes

- 调研沉淀：基于 15+ 一手/二手来源（论文 + 官方文档 + 产品对比 + 工程博客）得出 Hybrid 检索 + 卡片化双版决策
- 用户决策点全部进入 spec：Q1=A Hybrid / Q2=D 选完岗位再问 / Q3=A 4:3+9:16 双版 / Q4=B 仅埋点 / Q5=B 软区间 / Q6=C 默认原题可切变体 / Q7=B 置灰提示 / Q8=A 复用 sink_error
- 风险点（错题集噪声、embedding 冷启动、rerank 退化）已在 Edge Cases 列出，未进入 [NEEDS CLARIFICATION]
- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
- All items pass — ready for `/speckit-plan` 阶段
- **Clarify session 2026-07-07 (round 1)**: 修复 BGE embedding 维度冲突（512 vs 1024），明确「快速补漏」为「在线 AI 面试」下二级选项（澄清前 spec 表述模糊），明确 BGE 模型本地部署形态；clarify 后 checklist 16/16 仍全 PASS，无 regression
- **Clarify session 2026-07-07 (round 2) — 用户实查本机已下载 bge-reranker-v2-m3（cross-encoder reranker，2.27 GB）**：发现本机已下好的不是 embedding 而是 reranker，据此改写 spec：(1) Hybrid 精排阶段改用 cross-encoder reranker 替代 LLM listwise rerank（节省 LLM 配额 + 利用本机已有模型）；(2) FR-012/013/014 + US-2/AC + Edge Cases + SC-010 全部对齐；(3) 修复 5 处内部矛盾：US-2/AC 残留 "LLM listwise rerank" 描述、Edge Cases 降级路径过时、SC-010 "LLM rerank" 时延口径不准、FR-021 "MAX_QUESTIONS - 3" 在软上限 10/15 场景下边界模糊 → 新增 FR-023 定义 `effective_max` 计算逻辑与硬下限 7；(4) A-007 补充 regression 反向迁移代码 review 风险说明；clarify 后 checklist 仍 16/16 全 PASS，无 regression