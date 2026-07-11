# REQ-055 — 简历中心提升：根简历、派生简历、一键派生与 AI 优化建议

| Field | Value |
|---|---|
| Requirement ID | REQ-055 |
| Spec directory | `specs/055-resume-root-derive` |
| Status | done (MVP + US4–US7; MVP+ T034/T097 deferred) |
| Spec | [spec.md](./spec.md) |
| Plan | [plan.md](./plan.md) |
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Quickstart | [quickstart.md](./quickstart.md) |
| Contracts | [contracts/](./contracts/) |
| Quality checklist | [checklists/requirements.md](./checklists/requirements.md) |
| Tasks | [tasks.md](./tasks.md) |
| Requirements status | [requirements-status.md](./requirements-status.md) |

## Summary

将简历中心升级为「长期职业素材库（根简历）+ 岗位定向派生简历 + 严格页数控制 + AI 优化建议 + 求职追踪联动」。技术路径：扩展 `resumes_v2`、新增 `resume_derive` 模块与 LangGraph/ARQ 派生流水线，导出时 PDF 页数硬门禁。

## Implementation status (2026-07-09)

**Landed:**
- Migration `0049_055_resume_root_derive`
- Module `backend/app/modules/resume_derive/` + agent pipeline + ARQ `execute_resume_derive` (trace_ctx / RLS / FK flush fixes)
- Root/derive/suggestion preview-apply/supplements APIs, export page gate, jobs derived-resumes list
- Frontend: RootResumeCard, PromoteRootDialog, DeriveWizard/Progress/Workbench, panels, ResumeList derived section, Jobs detail binding
- Tests: backend resume_derive suites, Vitest derive module, Playwright A/A2/B/C/G/H
- Evidence: `docs/evidence/055-resume-root-derive/`

**Deferred MVP+:** T034 merge-draft AI; T097 side-by-side diff/rollback — see [requirements-status.md](./requirements-status.md).

## Next

1. Optional: `/speckit-agent-context-update`
2. Optional: manual PDF reader spot-check pages=2/3 artifacts into evidence folder
3. Ship / demo MVP
