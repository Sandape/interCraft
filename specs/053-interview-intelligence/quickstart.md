# Quickstart: Interview Intelligence Engine

**Feature**: REQ-053 | **Date**: 2026-07-09

## Prerequisites

- [x] REQ-052 (Personal Agent + WeChat Channel) deployed
- [x] PostgreSQL + Redis running
- [x] ARQ worker process running (`uv run arq app.workers.main.WorkerSettings`)
- [x] Tavily API key configured (`TAVILY_API_KEY` in `backend/.env`)
- [x] DeepSeek API key configured (via `llm_client` config)

## Setup

```bash
# 1. Pull latest code + switch to branch
git checkout master && git pull
git checkout -b 053-interview-intelligence

# 2. Install dependencies (if new ones added)
cd backend && uv sync

# 3. Run database migration
cd backend
uv run alembic upgrade head

# 4. Verify migration (dry-run mode)
uv run python -m app.modules.jobs.cli migrate-status --dry-run

# 5. Restart ARQ worker (new cron job registered)
# Worker will auto-reload if --reload is on; otherwise restart
```

## Validation Scenarios

### VS-1: Status Model Migration (US7)

```bash
# Dry-run: preview what will change
uv run python -m app.modules.jobs.cli migrate-status --dry-run

# Expected: Lists all jobs that will be migrated, old→new status mapping

# Execute migration
uv run alembic upgrade head

# Verify via API
curl -s http://localhost:8000/api/v1/jobs/transitions | jq '.statuses'
# Expected: ["applied", "test", "interview_1", "interview_2", "interview_3", "failed", "passed"]

# Rollback test (in test environment only!)
uv run alembic downgrade -1
# Verify old statuses restored
uv run alembic upgrade head
```

### VS-2: New Job Status Flow with Interview Time (US1)

```bash
# Create a job
curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"company":"测试公司","position":"测试岗位"}' | jq '.id'

# Push to interview_1 (MUST include interview_time)
JOB_ID="<from above>"
curl -s -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"to\":\"interview_1\",\"interview_time\":\"$(date -u -d '+6 hours' +%Y-%m-%dT%H:%M:%SZ)\"}"

# Expected: 200 OK, status=interview_1, interview_time set

# Push to passed (NO interview_time required)
curl -s -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"to":"passed"}'
# Expected: 200 OK, status=passed

# Verify rejection of past interview_time
curl -s -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"to":"interview_2","interview_time":"2020-01-01T00:00:00Z"}'
# Expected: 422, "面试时间必须是将来时间"
```

### VS-3: Research Pipeline End-to-End (US2-US5)

```bash
# Step 1: Create job with interview in ~5 hours
FUTURE_TIME=$(date -u -d '+5 hours +2 minutes' +%Y-%m-%dT%H:%M:%SZ)
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"company\":\"字节跳动\",\"position\":\"AI应用开发工程师\"}" | jq -r '.id')

curl -s -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"to\":\"interview_1\",\"interview_time\":\"$FUTURE_TIME\"}"

# Step 2: Manually trigger research (bypass 5h wait for testing)
curl -s -X POST "http://localhost:8000/api/v1/internal/research/trigger" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"job_id\":\"$JOB_ID\"}"
# Expected: 202 Accepted, {"task_id": "..."}

# Or via CLI:
uv run python -m app.modules.research.cli trigger-research $JOB_ID

# Step 3: Wait for task completion (poll or check ARQ logs)
sleep 120  # Wait for search + LLM generation

# Step 4: Verify report
curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/research-reports" | jq '.data[0]'
# Expected: report with 6 chapters, 2000-3000 chars, quality_check_passed=true

# Step 5: Check report content
REPORT_ID=$(curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/research-reports" | jq -r '.data[0].id')
curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/research-reports/$REPORT_ID" | jq '.summary_md'
# Expected: Full markdown report with 📋 🏢 📝 🎯 ⚠️ 💡 chapter headings

# Step 6: Verify WeChat delivery (if bound) or notification (if not)
curl -s "http://localhost:8000/api/v1/account/notification-center" \
  -H "Authorization: Bearer $TOKEN" | jq '.notifications[0]'
# Expected if WeChat not bound: notification "面试备战报告已生成（微信未绑定，无法推送），点击查看"
```

### VS-4: Quality Check Retry (FR-018)

```bash
# This is automatically tested during VS-3 if the first report generation produces
# substandard output. The system will automatically retry once.
# Check research task logs:
uv run python -m app.modules.research.cli research-stats
# Expected: quality_failed count = 0 (or low); completed count matches expectations
```

### VS-5: Duplicate Prevention (SC-007)

```bash
# Trigger research twice for same job+interview_time
uv run python -m app.modules.research.cli trigger-research $JOB_ID
uv run python -m app.modules.research.cli trigger-research $JOB_ID
# Expected: 2nd call returns "该面试时间已存在调研任务" (409 or duplicate skipped)
```

### VS-6: Scheduling via ARQ Cron (US2)

```bash
# The ARQ cron runs every 10 minutes automatically.
# To verify manually, check worker logs:
# Look for: "scan_interview_research: matched=N, tasks_created=N"

# Force a scan (development only):
uv run python -c "
import asyncio
from app.workers.tasks.interview_research import scan_interview_research
asyncio.run(scan_interview_research({}))
"
```

### VS-7: Web Report Viewing (US6)

```bash
# After a report is generated (VS-3), access via browser:
# Open: http://localhost:5173/jobs/$JOB_ID
# Expected: "查看备战报告" button visible next to interview time
# Click: navigates to /research-reports/$REPORT_ID
# Expected: Full markdown-rendered report with 6 chapters
```

### VS-8: Report Rating (SC-009)

```bash
REPORT_ID="<from VS-3>"
curl -s -X PATCH "http://localhost:8000/api/v1/research-reports/$REPORT_ID/rating" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"rating":4}'
# Expected: 200 OK, {"id":"...","rating":4}

# Invalid rating test
curl -s -X PATCH "http://localhost:8000/api/v1/research-reports/$REPORT_ID/rating" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"rating":6}'
# Expected: 422, "评分必须为 1-5 的整数"
```

## E2E Playwright Tests

Run after all VS scenarios pass:

```bash
cd frontend
npx playwright test tests/e2e/053-interview-intelligence.spec.ts --project=chromium
```

Covers (SC-010):
- US1: Full status flow (applied → interview_1 with time → interview_2 → passed)
- US4: Web report viewing
- US7: Migration dry-run verification

## Running Tests

```bash
# Backend unit/integration tests
cd backend
uv run pytest tests/unit/modules/research/ -v
uv run pytest tests/integration/test_research_pipeline.py -v

# Frontend E2E
cd frontend
npx playwright test tests/e2e/053-interview-intelligence.spec.ts

# All tests
cd backend && uv run pytest -m "not slow" && cd ../frontend && npx playwright test
```
