# 018 Requirement Status

This file tracks the 8 user stories and 22 FR / 10 SC of feature 018
(`specs/018-fix-product-defects`). Status reconciled against code on
2026-06-22. All 14 product defects are fixed in code; 6 E2E specs cover
the high-priority user stories.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | 新建简历可以直接编辑并导出 | done | `src/pages/ResumeEditor.tsx` (可编辑 + `未找到该简历` 文案); `src/api/export.ts` + `ExportError`; `tests/e2e/018-fix-product-defects/` (缺 resume/ 子目录 E2E) | — |
| US2 | 注册深链直达注册态 | done | `src/pages/Register.tsx` (独立组件, `<Login initialMode="register" />`); `tests/e2e/018-fix-product-defects/auth/register-deep-link.spec.ts` | — |
| US3 | Dashboard 智能建议基于真实数据 | done | `src/hooks/useDashboardSuggestions.ts` (tier 0/1/2 selector, 真实 useResumeBranches/useErrorQuestions/useJobs/useInterviewSessions) | — |
| US4 | 面试评分与能力画像口径一致 | done | `backend/app/modules/interviews/service.py:21,304` `sync_ability_dimensions`; `backend/tests/integration/test_interview_to_ability_sync.py`; `backend/app/workers/tasks/diagnose_after_interview.py` | — |
| US5 | 面试启动关联简历、恢复状态友好 | done | `backend/app/modules/interviews/models.py:28` `branch_id`; `src/lib/i18n/zh-CN.ts:4` `restore: '面试已恢复，继续你的回答'`; `src/pages/InterviewLive.tsx:94,102,234` `resume_error` phase; `tests/e2e/018-fix-product-defects/interview/restore-zh-text.spec.ts` + `setup-resume-pick.spec.ts` | — |
| US6 | 错题 Coach 启动有反馈、错题自动选中 | done | `src/hooks/useErrorCoach.ts:9,33,39-43` useQuery + `refetchInterval`; `src/pages/ErrorBook.tsx:94,131` `setSelectedId(created.id)` in create onSuccess; `tests/e2e/018-fix-product-defects/error-book/auto-select-new.spec.ts` | — |
| US7 | 求职记录备注可保存可展示 | done | `backend/app/modules/jobs/models.py:36` `notes_md`; `backend/app/modules/jobs/schemas.py:18,32,62`; `tests/e2e/018-fix-product-defects/jobs/notes-roundtrip.spec.ts` | — |
| US8 | 生产级 Console 与无障碍 | done | `src/App.tsx:129-131` `future={{ v7_startTransition, v7_relativeSplatPath, ... }}`; `src/components/layout/Topbar.tsx:275-276` `topbar-menu-logout` menuitem; `tests/e2e/018-fix-product-defects/auth/logout-menu-semantics.spec.ts` | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | `/login` 与 `/register` 入口态分离 | done | `src/pages/Register.tsx` 独立组件; `src/pages/Login.tsx` `initialMode` prop | — |
| FR-002 | 已登录访问 `/login` / `/register` 跳主页 | done | `src/App.tsx` AuthGuard + 已登录重定向逻辑 | — |
| FR-003 | Dashboard 建议区仅基于真实数据,无占位文案 | done | `src/hooks/useDashboardSuggestions.ts` 无任何硬编码公司 / 简历 / 失分字面量 | — |
| FR-004 | Dashboard 按档位 0/1/2 渐进式披露 | done | `src/hooks/useDashboardSuggestions.ts` `Tier = 0\|1\|2` | — |
| FR-005 | Dashboard 数据源可注入(单测/Storybook) | done | `useDashboardSuggestions` 使用 React Query hooks,可在测试中通过 MSW 注入 | — |
| FR-006 | 新建简历默认可编辑 + 「+ 添加块」入口 | done | `src/pages/ResumeEditor.tsx:401,488` `createBlock` 入口; `disabled={createBlock.isPending}` 仅在 pending 时禁用 | — |
| FR-007 | 不可写时显示具体原因(鉴权/网络/锁) | done | `src/pages/ResumeEditor.tsx:303` 「未找到该简历」; `useLock` 区分 conflict / unauthorized | — |
| FR-008 | PDF 导出走 /api/v1/export/render 契约 | done | `backend/app/api/v1/export.py`; `src/api/export.ts:exportResume()` | 与 Feature 012 一致 |
| FR-009 | 导出失败给可读错误 + 结构化错误码 | done | `src/lib/apiErrorToMessage.ts` `ExportError` class; `src/api/export.ts:35,45,53` | — |
| FR-010 | 空简历时 AI 面板显示空态,无硬编码数字 | done | `src/components/resume/editor/EditorSidebar.tsx` (无 `MOCK_AI_SUMMARY` / `+14` / `原始 72` / `当前 86` 字面量) | — |
| FR-011 | 新建面试表单可选简历,无简历时给跳转入口 | done | `src/pages/InterviewLive.tsx:135` resume branches picker; `tests/e2e/018-fix-product-defects/interview/setup-resume-pick.spec.ts` | — |
| FR-012 | 面试恢复 UI 中文友好文案,不泄露技术日志 | done | `src/lib/i18n/zh-CN.ts:4` `restore: '面试已恢复，继续你的回答'`; `tests/e2e/018-fix-product-defects/interview/restore-zh-text.spec.ts` | — |
| FR-013 | 面试评分使用 0-10 量纲,禁止 0-100 展示 | done | `backend/app/agents/interview/nodes/score.py` 0-10 评分; UI 报告页未出现 /100 表达 | — |
| FR-014 | 完成卡「满分」文案与量纲一致 | done | 报告页使用「满分 10」文案 | — |
| FR-015 | 面试完成后能力画像同步反映维度均分 | done | `backend/app/modules/interviews/service.py:21,304` `sync_ability_dimensions`; `backend/tests/integration/test_interview_to_ability_sync.py` | — |
| FR-016 | 错题 Coach 启动给 loading/error/first-question 状态 | done | `src/hooks/useErrorCoach.ts:39-43` useQuery + refetchInterval | — |
| FR-017 | Coach 启动失败保留重试入口 + 可读错误 | done | `src/hooks/useErrorCoach.ts` 重试逻辑 | — |
| FR-018 | 新增错题后自动定位到该错题 | done | `src/pages/ErrorBook.tsx` create mutation onSuccess `setSelectedId(created.id)` | — |
| FR-019 | 求职记录备注字段前端正确读写展示 | done | `backend/app/modules/jobs/schemas.py:18,32,62` `notes_md`; `tests/e2e/018-fix-product-defects/jobs/notes-roundtrip.spec.ts` | — |
| FR-020 | 编辑投递记录时备注字段被回填 + 可保存 | done | `tests/e2e/018-fix-product-defects/jobs/notes-roundtrip.spec.ts` | — |
| FR-021 | 显式接受 React Router v7 future flag | done | `src/App.tsx:129-131` `v7_startTransition` + `v7_relativeSplatPath` (及其他 4 项) | — |
| FR-022 | 「退出登录」a11y role + 可见 name + 可触发 | done | `src/components/layout/Topbar.tsx:275-276` `<MenuItem testId="topbar-menu-logout">` + `tests/e2e/018-fix-product-defects/auth/logout-menu-semantics.spec.ts` | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | 新建简历后 1 次点击进入可编辑 + 「+ 添加块」可见 | done | `src/pages/ResumeEditor.tsx:401,488`; `tests/e2e/018-fix-product-defects/` | — |
| SC-002 | 100% PDF 导出按 012 契约返回 2xx 或结构化 4xx/5xx | done | `backend/app/api/v1/export.py` + `src/api/export.ts` + `src/lib/apiErrorToMessage.ts` | — |
| SC-003 | 未登录访问 `/register` 100% 显示创建账号表单 | done | `src/pages/Register.tsx`; `tests/e2e/018-fix-product-defects/auth/register-deep-link.spec.ts` | — |
| SC-004 | 完成面试后能力画像至少 1 项维度 > 0 | done | `backend/app/modules/interviews/service.py:21` `sync_ability_dimensions`; `backend/tests/integration/test_interview_to_ability_sync.py` | — |
| SC-011 | Dashboard 三档位渐进式建议命中预期 | done | `src/hooks/useDashboardSuggestions.ts` Tier 0/1/2 实现 | — |
| SC-005 | 面试报告总分 0-10 量纲,全应用无 /100 表达 | done | UI 报告页使用 0-10 量纲 | — |
| SC-006 | 100% 启动 Coach 在 5 秒内观察到 loading/error/first-question | done | `src/hooks/useErrorCoach.ts:39-43` refetchInterval | — |
| SC-007 | 主流程页面 Console 无 React Router Future Flag Warning | done | `src/App.tsx:129-131` future flags 显式设置 | — |
| SC-008 | 「退出登录」可被 Playwright 稳定定位触发 | done | `tests/e2e/018-fix-product-defects/auth/logout-menu-semantics.spec.ts` | — |
| SC-009 | 新增错题/投递记录后列表+详情自动定位新建项 | done | `src/pages/ErrorBook.tsx` `setSelectedId(created.id)`; `tests/e2e/018-fix-product-defects/error-book/auto-select-new.spec.ts` + `jobs/notes-roundtrip.spec.ts` | — |
| SC-010 | 投递记录备注 100% 创建/编辑路径正确写入展示 | done | `backend/app/modules/jobs/schemas.py` `notes_md`; `tests/e2e/018-fix-product-defects/jobs/notes-roundtrip.spec.ts` | — |

## Status Roll-up

- Total: 8 US + 22 FR + 11 SC = 41 rows (SC-011 renumbered, original SC-011 is unique).
- `done`: 41 rows.
- All 14 defects from the original input list are closed in code.
- E2E coverage: 6 spec files under `tests/e2e/018-fix-product-defects/` (auth × 2, error-book × 1, interview × 2, jobs × 1).
- Not yet covered by E2E: US1 resume-editor subdirectory (PDF export flow, empty-resume no-fake-AI, new-resume-editable). Implementation is complete; E2E specs from tasks.md T014-T016 are not yet authored.
