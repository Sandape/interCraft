"""GoldenCase loader for feature 026 — US2 (T020/T021).

Loads golden cases from `specs/026-agent-eval-loop/golden/**/*.json`. Each
case describes one (node, input_state, llm_response, expected) tuple. The
eval runner replays the case through the real node function (with the LLM
client stubbed to yield `llm_response`).

Case schema (see specs/026-agent-eval-loop/golden/README.md):
{
  "case_id": "interview_score_01_high_chinese",
  "node": "interview.score",
  "label": "description of what this case tests",
  "source": "manual" | "promoted",
  "input_state": { ... graph state to feed node ... },
  "llm_response": "raw LLM output content (the JSON string the node parses)",
  "expected_language": "zh-CN",                 # optional, default "zh-CN"
  "expected_contains": ["React", "diff"],       # optional keywords
  "expected_score_range": [9, 10],               # optional, for score node
  "expected_overall_score_range": [7.0, 8.0],   # optional, for report node
  "expected_fidelity_pass": true,               # optional, default true
  "status": "active"                             # optional, default "active"
}

Loader is fault-tolerant: a malformed or duplicate case is flagged `stale`
or skipped, but other cases still load. This satisfies FR's "stale case is
flagged, not silently dropped" requirement.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("eval.golden_loader")

# Valid `source` values per spec FR-007.
_VALID_SOURCES: frozenset[str] = frozenset({"manual", "promoted"})

# Valid `status` values.
_VALID_STATUS: frozenset[str] = frozenset({"active", "stale"})
_VALID_LIFECYCLES: frozenset[str] = frozenset(
    {"GOLDEN", "CANDIDATE", "REPORT_ONLY", "DEPRECATED", "REJECTED"}
)


@dataclass
class GoldenCase:
    """A labeled input→expected-output pair for one graph node.

    Fields per FR-007:
    - case_id: unique identifier (used for dedup + pytest parametrize)
    - node: graph.node identifier (e.g. "interview.score")
    - label: human-readable description of what aspect this case tests
    - source: "manual" (authored) or "promoted" (from production trace)
    - input_state: state dict fed to the node function
    - llm_response: the raw LLM output content (stub response in mock mode)
    - expected_language: prompt's required language (default "zh-CN")
    - expected_contains: keywords that should appear in the parsed output
    - expected_score_range: [low, high] inclusive — for score node
    - expected_overall_score_range: [low, high] — for report node
    - expected_fidelity_pass: True if LLM response should pass fidelity check.
        Set False for regression cases where the LLM produces English output
        — the eval suite validates that the checker correctly flags it.
    - status: "active" (run) or "stale" (skip, schema mismatch)
    """

    case_id: str
    node: str
    label: str
    source: str
    input_state: dict[str, Any]
    llm_response: str
    expected_language: str = "zh-CN"
    expected_contains: list[str] = field(default_factory=list)
    expected_score_range: tuple[int, int] | None = None
    expected_overall_score_range: tuple[float, float] | None = None
    expected_fidelity_pass: bool = True
    status: str = "active"
    lifecycle: str = "GOLDEN"
    dataset_version: str = "golden-v1"
    file_path: str = ""  # for diagnostics — where this case was loaded from


def load_golden_cases(spec_dir: Path | str) -> list[GoldenCase]:
    """Load all golden cases from `spec_dir/golden/**/*.json`.

    Fault-tolerant:
    - Missing `golden/` dir → return []
    - Malformed JSON → log warning, skip that file
    - Missing required fields → case loaded with `status="stale"`
    - Duplicate `case_id` → log warning, skip the later one
    - Invalid `source` / `status` → case marked `stale`

    Returns only `status="active"` cases? No — returns ALL loaded cases
    (including stale) so the runner can report stale cases in the aggregate
    report (per spec edge case "stale case is flagged and excluded from
    metrics, not silently dropped").
    """
    spec_path = Path(spec_dir)
    golden_root = spec_path / "golden"

    if not golden_root.exists():
        logger.warning("eval.golden_dir_missing", spec_dir=str(spec_path))
        return []

    cases: list[GoldenCase] = []
    seen_ids: set[str] = set()

    # Sort files for deterministic load order (matters for duplicate-id warnings).
    case_files = sorted(golden_root.rglob("*.json"))
    logger.info(
        "eval.golden_load_start",
        spec_dir=str(spec_path),
        file_count=len(case_files),
    )
    for case_file in case_files:
        try:
            raw = case_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "eval.golden_case_parse_error",
                file=str(case_file),
                error=str(exc),
            )
            continue

        if not isinstance(data, dict):
            logger.warning("eval.golden_case_not_object", file=str(case_file))
            continue

        case = _build_case(data, str(case_file))
        if case is None:
            continue

        if case.case_id in seen_ids:
            logger.warning(
                "eval.golden_case_duplicate_id_skipped",
                case_id=case.case_id,
                file=str(case_file),
            )
            continue

        seen_ids.add(case.case_id)
        cases.append(case)

    active_count = sum(1 for c in cases if c.status == "active")
    stale_count = sum(1 for c in cases if c.status == "stale")
    logger.info(
        "eval.golden_load_done",
        total=len(cases),
        active=active_count,
        stale=stale_count,
    )
    return cases


def _build_case(data: dict[str, Any], file_path: str) -> GoldenCase | None:
    """Build a GoldenCase from a parsed JSON dict.

    Returns None if `case_id` or `node` is missing (can't even identify the
    case). Returns a `status="stale"` case if other required fields are
    missing or invalid (so the runner can report it).
    """
    case_id = data.get("case_id")
    node = data.get("node")

    if not case_id or not isinstance(case_id, str):
        logger.warning("eval.golden_case_missing_id", file=file_path)
        return None
    if not node or not isinstance(node, str):
        logger.warning("eval.golden_case_missing_node", file=file_path, case_id=case_id)
        return None

    source = data.get("source", "manual")
    if source not in _VALID_SOURCES:
        logger.warning(
            "eval.golden_case_invalid_source",
            case_id=case_id,
            source=source,
        )
        source = "manual"
        status = "stale"
    else:
        status = data.get("status", "active")
        if status not in _VALID_STATUS:
            logger.warning(
                "eval.golden_case_invalid_status",
                case_id=case_id,
                status=status,
            )
            status = "stale"

    input_state = data.get("input_state", {})
    if not isinstance(input_state, dict):
        logger.warning(
            "eval.golden_case_input_state_not_object",
            case_id=case_id,
        )
        input_state = {}
        status = "stale"

    llm_response = data.get("llm_response", "")
    if not isinstance(llm_response, str):
        logger.warning(
            "eval.golden_case_llm_response_not_string",
            case_id=case_id,
        )
        llm_response = ""
        status = "stale"

    # Missing required descriptive fields → stale (case is structurally broken)
    label = data.get("label", "")
    if not label:
        status = "stale"

    expected_contains = data.get("expected_contains", [])
    if not isinstance(expected_contains, list):
        expected_contains = []

    expected_score_range = _parse_int_range(
        data.get("expected_score_range"), case_id, "expected_score_range"
    )
    expected_overall_score_range = _parse_float_range(
        data.get("expected_overall_score_range"),
        case_id,
        "expected_overall_score_range",
    )
    lifecycle = str(data.get("lifecycle", "GOLDEN")).upper()
    if lifecycle not in _VALID_LIFECYCLES:
        logger.warning(
            "eval.golden_case_invalid_lifecycle",
            case_id=case_id,
            lifecycle=lifecycle,
        )
        lifecycle = "REJECTED"
        status = "stale"

    return GoldenCase(
        case_id=case_id,
        node=node,
        label=label,
        source=source,
        input_state=input_state,
        llm_response=llm_response,
        expected_language=data.get("expected_language", "zh-CN"),
        expected_contains=list(expected_contains),
        expected_score_range=expected_score_range,
        expected_overall_score_range=expected_overall_score_range,
        expected_fidelity_pass=bool(data.get("expected_fidelity_pass", True)),
        status=status,
        lifecycle=lifecycle,
        dataset_version=str(data.get("dataset_version", "golden-v1")),
        file_path=file_path,
    )


def _parse_int_range(
    raw: Any, case_id: str, field_name: str
) -> tuple[int, int] | None:
    """Parse [low, high] list into tuple. None if missing or malformed."""
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 2:
        logger.warning(
            "eval.golden_case_range_malformed",
            case_id=case_id,
            field=field_name,
            value=raw,
        )
        return None
    try:
        return (int(raw[0]), int(raw[1]))
    except (TypeError, ValueError):
        logger.warning(
            "eval.golden_case_range_not_numeric",
            case_id=case_id,
            field=field_name,
            value=raw,
        )
        return None


def _parse_float_range(
    raw: Any, case_id: str, field_name: str
) -> tuple[float, float] | None:
    """Parse [low, high] list into tuple of floats."""
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 2:
        logger.warning(
            "eval.golden_case_range_malformed",
            case_id=case_id,
            field=field_name,
            value=raw,
        )
        return None
    try:
        return (float(raw[0]), float(raw[1]))
    except (TypeError, ValueError):
        logger.warning(
            "eval.golden_case_range_not_numeric",
            case_id=case_id,
            field=field_name,
            value=raw,
        )
        return None


__all__ = ["GoldenCase", "load_golden_cases"]
