# REQ-055 — 简历中心提升：根简历、派生简历、一键派生与 AI 优化建议

| Field | Value |
|---|---|
| Requirement ID | REQ-055 |
| Spec directory | `specs/055-resume-root-derive` |
| Status | draft (planned) |
| Spec | [spec.md](./spec.md) |
| Plan | [plan.md](./plan.md) |
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Quickstart | [quickstart.md](./quickstart.md) |
| Contracts | [contracts/](./contracts/) |
| Quality checklist | [checklists/requirements.md](./checklists/requirements.md) |

## Summary

将简历中心升级为「长期职业素材库（根简历）+ 岗位定向派生简历 + 严格页数控制 + AI 优化建议 + 求职追踪联动」。技术路径：扩展 `resumes_v2`、新增 `resume_derive` 模块与 LangGraph/ARQ 派生流水线，导出时 PDF 页数硬门禁。

## Next

1. `/speckit-tasks` — 拆分实现任务
2. （可选）`/speckit-agent-context-update` — 刷新 agent 上下文
3. （可选）`/speckit-clarify` — 若需锁定版本回滚/对比是否进 MVP
