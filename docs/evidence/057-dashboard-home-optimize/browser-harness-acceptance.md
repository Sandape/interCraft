# REQ-057 Browser-Harness Acceptance (2026-07-10)

## Environment

- Frontend: `http://localhost:5173`
- Backend: `http://127.0.0.1:8000` (restarted with `APP_ENV=development` after route add)
- Account: `demo@intercraft.io`
- Tool: `browser-harness` 0.1.4 (local Chrome CDP)

## 1. Render

| Check | Result |
|---|---|
| Command-center shell (`data-testid=dashboard-command-center`) | Pass |
| Title「我的简历」not「我的简历分支」 | Pass (source + UI) |
| Single「下一步」panel, no「实时」badge | Pass |
| Today interview card + funnel + resumes + activities | Pass |
| Populated state after seeding today interview | Pass — greeting「今天有 1 场面试 · 下一场：frontend-verify-co」 |

## 2. Interaction

| Action | Result |
|---|---|
| Click funnel「投递中」 | Navigated to `/jobs?status=applied` |
| Click resume summary「Demo Root」 | Navigated to `/resume/{id}` |
| Click today interview row | Navigated to `/jobs/{id}` |
| Primary CTA / next-action CTA | Present and clickable |

## 3. Business logic

| Rule | Evidence |
|---|---|
| Today list = jobs with `interview_time` on local date | After PATCH job → `interview_1` + time in ~2h: `today_interviews.length === 1` |
| Activities Chinese titles | UI titles: `岗位状态更新`, `新增投递` — no `job_created` |
| Resume summaries from v2 | Shows root「Demo Root」+ standard items; counts from summary API |
| Funnel counts | applying/interviewing/awaiting_feedback non-zero for demo |
| Auth non-reblock | Dashboard stayed mounted across summary refetch (no full-screen「正在校验」) |

## API spot-check

```
GET /api/v1/me/dashboard-summary?tz=Asia/Shanghai
→ 200, l0/l1/l2 populated for demo user
```

## Unit/contract

```
pytest tests/unit/test_activity_labels.py tests/unit/test_dashboard_funnel.py tests/contract/test_dashboard_summary_schema.py --noconftest
→ 7 passed
```

## Notes

- Backend must run with `APP_ENV=development` (or set `WECHAT_TOKEN_ENCRYPTION_KEY`) so agent module imports.
- Vite HMR may need hard refresh after first deploy of Dashboard rewrite.
- Resume `total` via GROUP BY may differ from sidebar badge if badge uses a different list filter; summaries themselves are correct.
