# REQ-057 — Requirements Status

| Field | Value |
|---|---|
| Feature | 求职训练指挥台（工作台首页） |
| Spec directory | `specs/057-dashboard-home-optimize` |
| Overall status | **in_progress** (MVP implemented; browser-harness accepted) |
| Plan | [plan.md](./plan.md) |
| Tasks | [tasks.md](./tasks.md) (66/66 checked) |
| Evidence | [docs/evidence/057-dashboard-home-optimize/](../../docs/evidence/057-dashboard-home-optimize/) |
| Last updated | 2026-07-10 |

## Summary

Implemented `GET /api/v1/me/dashboard-summary` + Redis cache + Dashboard command-center rewrite. Browser-harness verified render, navigation, today-interview logic, and Chinese activity titles on demo account.

## User Story Status

| Story | Scope | Priority | Status |
|---|---|---|---|
| US1 | 今日指挥台 | P1 | done |
| US2 | 今日面试列表 | P1 | done |
| US3 | 简历区对齐简历中心 | P1 | done |
| US4 | 单一「下一步」建议 | P1 | done |
| US5 | 首屏预算与摘要缓存 | P1 | done |
| US6 | 求职漏斗 | P2 | done |
| US7 | 面试准备包 | P2 | done |
| US8 | 新用户三步冷启动 | P2 | done (code; empty when onboarded) |
| US9 | 继续未完成 | P2 | done (code; empty without in-progress) |
| US10 | 最近活动可读 | P2 | done |

## Verification

| Layer | Result |
|---|---|
| Unit/contract (labels/funnel/schema) | 7 passed |
| API summary (demo) | 200; today/funnel/resumes/activities populated |
| Browser-harness | See `docs/evidence/057-dashboard-home-optimize/browser-harness-acceptance.md` |

## Follow-ups

1. Align sidebar resume badge with summary `resume_counts.total` if filters differ
2. Optional JobRepository.stats old-key fix (T066)
3. Full Playwright suite under `tests/e2e/057-dashboard-command-center/` when CI time allows
