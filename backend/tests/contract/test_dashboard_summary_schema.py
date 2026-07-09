"""Contract tests for DashboardSummary schema (REQ-057)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from app.modules.dashboard.schemas import DashboardSummaryOut


def test_summary_schema_roundtrip_minimal():
    payload = {
        "generated_at": datetime.now(timezone.utc),
        "cache_ttl_sec": 60,
        "tz": "Asia/Shanghai",
        "local_date": date(2026, 7, 10),
        "l0": {
            "greeting_context": "今天没有安排面试",
            "next_interview": None,
            "today_interviews": [],
            "primary_cta": {"label": "开始模拟面试", "href": "/interview/mode"},
            "onboarding": None,
            "resumable_sessions": [],
        },
        "l1": {
            "resume_summaries": [],
            "resume_counts": {"root": 0, "derived": 0, "standard": 0, "total": 0},
            "next_action": {
                "id": "start-first-interview",
                "title_zh": "完成首场模拟面试，获取能力画像",
                "body_zh": "…",
                "cta": {"label": "开始面试", "href": "/interview/mode"},
                "tier": 0,
            },
            "job_funnel": [
                {
                    "key": "applying",
                    "label_zh": "投递中",
                    "count": 0,
                    "filter_statuses": ["applied"],
                    "href": "/jobs?status=applied",
                },
                {
                    "key": "interviewing",
                    "label_zh": "面试中",
                    "count": 0,
                    "filter_statuses": ["test", "interview_1", "interview_2", "interview_3"],
                    "href": "/jobs",
                },
                {
                    "key": "awaiting_feedback",
                    "label_zh": "待反馈",
                    "count": 0,
                    "filter_statuses": [],
                    "href": "/jobs",
                },
            ],
            "prep_pack": None,
        },
        "l2": {
            "ability_snapshot": None,
            "recent_activities": [
                {
                    "id": uuid4(),
                    "type": "job_created",
                    "title_zh": "新增投递",
                    "detail_zh": "A · B",
                    "occurred_at": datetime.now(timezone.utc),
                    "href": "/jobs/x",
                }
            ],
            "interview_trend": None,
        },
    }
    model = DashboardSummaryOut.model_validate(payload)
    assert model.l2.recent_activities[0].title_zh == "新增投递"
    assert model.l2.recent_activities[0].title_zh != model.l2.recent_activities[0].type
