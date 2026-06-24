"""GoldenCase loader unit tests (Phase 3 TDD).

Validates `load_golden_cases` from `app.eval.golden_loader`:
- Loads 10 cases from the actual 026 spec golden/ directory
- Fault-tolerant: missing dir / malformed JSON / missing fields
- Duplicate case_id skipped with warning
- Range parsing: int vs float
- Source validation: only "manual" or "promoted"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.golden_loader import load_golden_cases

# Path to the real 026 spec golden/ directory — tests against actual cases.
_SPEC_DIR = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "026-agent-eval-loop"
)


@pytest.fixture
def spec_dir() -> Path:
    return _SPEC_DIR


@pytest.fixture
def tmp_spec_dir(tmp_path: Path) -> Path:
    """Empty spec dir for fault-tolerance tests."""
    return tmp_path / "spec"


class TestLoadGoldenCasesRealData:
    """Tests against the actual 026 spec golden/ directory."""

    def test_load_returns_10_cases(self, spec_dir: Path) -> None:
        cases = load_golden_cases(spec_dir)
        assert len(cases) == 10, f"expected 10 cases, got {len(cases)}: {[c.case_id for c in cases]}"

    def test_all_cases_have_required_fields(self, spec_dir: Path) -> None:
        cases = load_golden_cases(spec_dir)
        for case in cases:
            assert case.case_id, "case_id must be non-empty"
            assert case.node in {"interview.score", "interview.report"}, (
                f"unknown node: {case.node}"
            )
            assert case.label, "label must be non-empty"
            assert case.source in {"manual", "promoted"}, (
                f"invalid source: {case.source}"
            )
            assert isinstance(case.input_state, dict)
            assert isinstance(case.llm_response, str)
            assert case.expected_language == "zh-CN"

    def test_cases_split_5_and_5_per_node(self, spec_dir: Path) -> None:
        cases = load_golden_cases(spec_dir)
        score_cases = [c for c in cases if c.node == "interview.score"]
        report_cases = [c for c in cases if c.node == "interview.report"]
        assert len(score_cases) == 5
        assert len(report_cases) == 5

    def test_two_regression_cases_marked_expected_fidelity_false(
        self, spec_dir: Path
    ) -> None:
        """SC-003: 2 known-bad cases validate checker catches the regression."""
        cases = load_golden_cases(spec_dir)
        regression_cases = [c for c in cases if not c.expected_fidelity_pass]
        assert len(regression_cases) == 2, (
            f"expected 2 regression cases (1 score + 1 report), "
            f"got {len(regression_cases)}"
        )
        nodes = {c.node for c in regression_cases}
        assert nodes == {"interview.score", "interview.report"}, (
            f"regression cases should cover both nodes; got {nodes}"
        )

    def test_score_cases_have_score_range(self, spec_dir: Path) -> None:
        cases = load_golden_cases(spec_dir)
        score_cases = [c for c in cases if c.node == "interview.score"]
        for case in score_cases:
            assert case.expected_score_range is not None, (
                f"score case {case.case_id} should have expected_score_range"
            )
            lo, hi = case.expected_score_range
            assert 0 <= lo <= hi <= 10, (
                f"score range {case.expected_score_range} out of [0, 10]"
            )

    def test_report_cases_have_overall_score_range(self, spec_dir: Path) -> None:
        cases = load_golden_cases(spec_dir)
        report_cases = [c for c in cases if c.node == "interview.report"]
        for case in report_cases:
            assert case.expected_overall_score_range is not None, (
                f"report case {case.case_id} should have expected_overall_score_range"
            )


class TestLoadGoldenCasesFaultTolerance:
    """Loader must be fault-tolerant (FR edge cases)."""

    def test_missing_golden_dir_returns_empty(self, tmp_spec_dir: Path) -> None:
        """Missing `golden/` dir → empty list, no exception."""
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        cases = load_golden_cases(tmp_spec_dir)
        assert cases == []

    def test_case_with_missing_node_field_marked_stale(
        self, tmp_spec_dir: Path
    ) -> None:
        """A case missing required `node` field should be skipped entirely (can't identify)."""
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "bad.json").write_text(
            json.dumps({
                "case_id": "missing_node",
                "label": "missing node",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        # Case with no `node` cannot be built — should be skipped, not stale.
        assert len(cases) == 0

    def test_case_with_missing_label_marked_stale(self, tmp_spec_dir: Path) -> None:
        """A case missing `label` should be marked stale but still loaded."""
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "no_label.json").write_text(
            json.dumps({
                "case_id": "no_label_case",
                "node": "interview.score",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert len(cases) == 1
        assert cases[0].status == "stale"
        assert cases[0].case_id == "no_label_case"

    def test_duplicate_case_id_skipped(self, tmp_spec_dir: Path) -> None:
        """Duplicate case_id → second one skipped."""
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        case_data = {
            "case_id": "dup_case",
            "node": "interview.score",
            "label": "first",
            "source": "manual",
            "input_state": {},
            "llm_response": "",
        }
        (golden_dir / "a.json").write_text(json.dumps(case_data), encoding="utf-8")
        (golden_dir / "b.json").write_text(
            json.dumps({**case_data, "label": "second"}),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert len(cases) == 1
        assert cases[0].label == "first", "first-loaded case should win"

    def test_malformed_json_skipped(self, tmp_spec_dir: Path) -> None:
        """Malformed JSON file should be skipped without breaking other cases."""
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "broken.json").write_text("{ not valid json", encoding="utf-8")
        (golden_dir / "good.json").write_text(
            json.dumps({
                "case_id": "good_case",
                "node": "interview.score",
                "label": "good",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert len(cases) == 1
        assert cases[0].case_id == "good_case"

    def test_invalid_source_marks_stale(self, tmp_spec_dir: Path) -> None:
        """`source: "unknown"` → case marked stale, source reset to "manual"."""
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "bad_source.json").write_text(
            json.dumps({
                "case_id": "bad_source_case",
                "node": "interview.score",
                "label": "test",
                "source": "unknown_value",
                "input_state": {},
                "llm_response": "",
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert len(cases) == 1
        assert cases[0].status == "stale"
        assert cases[0].source == "manual"  # reset to default


class TestGoldenCaseShape:
    """GoldenCase dataclass field parsing."""

    def test_expected_score_range_parsed_as_tuple(
        self, tmp_spec_dir: Path
    ) -> None:
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "case.json").write_text(
            json.dumps({
                "case_id": "range_test",
                "node": "interview.score",
                "label": "test",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
                "expected_score_range": [9, 10],
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert len(cases) == 1
        assert cases[0].expected_score_range == (9, 10)
        assert isinstance(cases[0].expected_score_range, tuple)

    def test_expected_overall_score_range_parsed_as_float_tuple(
        self, tmp_spec_dir: Path
    ) -> None:
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_report"
        golden_dir.mkdir(parents=True)
        (golden_dir / "case.json").write_text(
            json.dumps({
                "case_id": "overall_range_test",
                "node": "interview.report",
                "label": "test",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
                "expected_overall_score_range": [7.5, 8.5],
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert len(cases) == 1
        assert cases[0].expected_overall_score_range == (7.5, 8.5)

    def test_expected_contains_parsed_as_list(self, tmp_spec_dir: Path) -> None:
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "case.json").write_text(
            json.dumps({
                "case_id": "contains_test",
                "node": "interview.score",
                "label": "test",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
                "expected_contains": ["React", "diff"],
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert cases[0].expected_contains == ["React", "diff"]

    def test_default_expected_fidelity_pass_is_true(
        self, tmp_spec_dir: Path
    ) -> None:
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "case.json").write_text(
            json.dumps({
                "case_id": "default_fid_test",
                "node": "interview.score",
                "label": "test",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert cases[0].expected_fidelity_pass is True

    def test_default_status_is_active(self, tmp_spec_dir: Path) -> None:
        tmp_spec_dir.mkdir(parents=True, exist_ok=True)
        golden_dir = tmp_spec_dir / "golden" / "interview_score"
        golden_dir.mkdir(parents=True)
        (golden_dir / "case.json").write_text(
            json.dumps({
                "case_id": "default_status_test",
                "node": "interview.score",
                "label": "test",
                "source": "manual",
                "input_state": {},
                "llm_response": "",
            }),
            encoding="utf-8",
        )
        cases = load_golden_cases(tmp_spec_dir)
        assert cases[0].status == "active"


class TestCaseIdStability:
    """Test case IDs are stable across loads (deterministic ordering)."""

    def test_case_ids_match_expected_set(self, spec_dir: Path) -> None:
        cases = load_golden_cases(spec_dir)
        case_ids = {c.case_id for c in cases}
        expected_ids = {
            "interview_score_01_high_chinese",
            "interview_score_02_mid_chinese",
            "interview_score_03_low_chinese",
            "interview_score_04_english_regression",
            "interview_score_05_short_answer",
            "interview_report_01_strong_chinese",
            "interview_report_02_weak_chinese",
            "interview_report_03_mixed_chinese",
            "interview_report_04_english_regression",
            "interview_report_05_minimal_scores",
        }
        assert case_ids == expected_ids, (
            f"missing: {expected_ids - case_ids}; "
            f"extra: {case_ids - expected_ids}"
        )
