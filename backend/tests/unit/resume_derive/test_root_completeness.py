"""Unit tests for root completeness hints (REQ-055 FR-005)."""
from __future__ import annotations

from app.modules.resume_derive.root_completeness import compute_root_completeness


def test_complete_project_has_no_gaps():
    data = {
        "sections": {
            "projects": {
                "items": [
                    {
                        "id": "p1",
                        "name": "Payment API",
                        "bullets": [
                            "背景：支付链路重构",
                            "负责核心模块与架构设计，Python/React 技术栈",
                            "结果上线后 QPS 提升 40%",
                        ],
                    }
                ]
            }
        }
    }
    report = compute_root_completeness(data)
    assert report["hint_only"] is True
    assert report["score_forced"] is False
    assert report["project_gaps"] == []


def test_incomplete_project_reports_missing_dims():
    data = {
        "sections": {
            "projects": {
                "items": [
                    {
                        "id": "p1",
                        "name": "Side tool",
                        "bullets": ["Built a small CLI"],
                    }
                ]
            }
        }
    }
    report = compute_root_completeness(data)
    assert len(report["project_gaps"]) == 1
    gap = report["project_gaps"][0]
    assert gap["index"] == 0
    assert gap["name"] == "Side tool"
    assert "background" in gap["missing"]
    assert "metrics" in gap["missing"]


def test_empty_data_is_non_blocking():
    report = compute_root_completeness({})
    assert report["project_gaps"] == []
    assert report["hint_only"] is True
