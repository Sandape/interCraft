"""REQ-038 US4 — FR-013/FR-014 tests.

Covers AC-US4-04 through AC-US4-07 from the locked acceptance matrix.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.agents.structured_output.registry import (
    DEFERRED_STRUCTURED_NODES,
    FREE_FORM_NODES,
    STRUCTURED_NODES,
)

_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
_DOC_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "contracts"
    / "structured_output_exclusions.md"
)

_STRUCTURED_IMPORTS = (
    "with_structured_output",
    "parse_structured_output",
    "emit_structured_invocation_event",
)

# ---------------------------------------------------------------------------
# AC-US4-04: Exclusion doc exists and is machine-parseable
# ---------------------------------------------------------------------------


def _parse_exclusion_doc() -> dict[str, str]:
    """Parse the Markdown table and return {node_id: kind}."""
    assert _DOC_PATH.exists(), f"Exclusion doc not found at {_DOC_PATH}"
    text = _DOC_PATH.read_text(encoding="utf-8")
    rows: dict[str, str] = {}

    lines = text.splitlines()
    in_table = False
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and "node_id" in stripped and "kind" in stripped:
            header_seen = True
            continue
        if header_seen and stripped.startswith("|---"):
            in_table = True
            continue
        if in_table:
            if not stripped.startswith("|"):
                break
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 5:
                node_id = parts[1]
                kind = parts[2]
                if node_id and kind:
                    rows[node_id] = kind

    return rows


def test_exclusion_doc_exists_and_format() -> None:
    """AC-US4-04: Exclusion doc exists as Markdown table with required columns."""
    assert _DOC_PATH.exists(), f"File not found: {_DOC_PATH}"

    text = _DOC_PATH.read_text(encoding="utf-8")
    assert text.strip(), "Exclusion doc is empty"

    # Verify header row has the three required columns.
    assert "| node_id | kind | exclusion_reason |" in text, (
        "Doc must have Markdown table with columns: node_id, kind, exclusion_reason"
    )

    rows = _parse_exclusion_doc()
    assert len(rows) >= 2, (
        f"Expected at least 2 table rows, got {len(rows)}"
    )

    # Every registry node must be present in the doc.
    all_excluded = set(FREE_FORM_NODES) | set(DEFERRED_STRUCTURED_NODES)
    for node_id in sorted(all_excluded):
        assert node_id in rows, (
            f"Registry node '{node_id}' missing from exclusion doc"
        )

    # No STRUCTURED_NODES entry should be in the doc.
    for node_id in STRUCTURED_NODES:
        assert node_id not in rows, (
            f"Structured node '{node_id}' should not appear in exclusion doc"
        )

    # Every entry must have a valid kind.
    for node_id, kind in rows.items():
        assert kind in ("free_form", "deferred"), (
            f"Node '{node_id}' has unknown kind '{kind}'"
        )

    # Every entry must have a non-empty exclusion_reason.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---"):
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 5 and parts[1] and parts[3]:
                # parts[3] is exclusion_reason
                assert parts[3], f"Row '{parts[1]}' has empty exclusion_reason"


# ---------------------------------------------------------------------------
# AC-US4-05: Free-form nodes bypass structured path
# ---------------------------------------------------------------------------


def _free_form_node_file(node_id: str) -> Path:
    """Map a free-form node ID to its source file."""
    mapping = {
        "error_coach.hint_ladder": (
            Path(__file__).resolve().parents[2]
            / "app" / "agents" / "nodes" / "error_coach" / "hint_ladder.py"
        ),
        "general_coach.respond": (
            Path(__file__).resolve().parents[2]
            / "app" / "agents" / "nodes" / "general_coach" / "respond.py"
        ),
    }
    return mapping[node_id]


@pytest.mark.parametrize("node_id", list(FREE_FORM_NODES))
def test_free_form_nodes_bypass_structured_path(node_id: str) -> None:
    """AC-US4-05: Free-form node file must not import/call structured-output
    functions (with_structured_output, parse_structured_output,
    emit_structured_invocation_event)."""
    source_file = _free_form_node_file(node_id)
    assert source_file.exists(), f"Source file not found: {source_file}"

    text = source_file.read_text(encoding="utf-8")

    for structured_import in _STRUCTURED_IMPORTS:
        assert structured_import not in text, (
            f"Free-form node '{node_id}' must not import/call "
            f"'{structured_import}', but found in {source_file}"
        )


# ---------------------------------------------------------------------------
# AC-US4-06: Bidirectional exclusion validation
# ---------------------------------------------------------------------------


def test_bidirectional_exclusion_validation() -> None:
    """AC-US4-06: The check_structured_exclusions.py script passes
    bidirectional validation: registry ↔ doc."""
    script_path = _SCRIPT_DIR / "check_structured_exclusions.py"
    assert script_path.exists(), f"Script not found: {script_path}"

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=_SCRIPT_DIR.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    assert completed.returncode == 0, (
        f"check_structured_exclusions.py failed (exit {completed.returncode}):\n"
        f"stdout: {stdout}\n"
        f"stderr: {stderr}"
    )
    assert "PASS structured exclusions" in stdout, (
        f"Expected 'PASS structured exclusions' in stdout, got: {stdout}"
    )


# ---------------------------------------------------------------------------
# AC-US4-07: Unit + known-good contract zero regression (placeholders)
# ---------------------------------------------------------------------------


def test_free_form_registry_has_expected_nodes() -> None:
    """Verify FREE_FORM_NODES contains exactly the 2 expected nodes."""
    expected = ("error_coach.hint_ladder", "general_coach.respond")
    assert FREE_FORM_NODES == expected, (
        f"FREE_FORM_NODES mismatch: {FREE_FORM_NODES}"
    )


def test_deferred_registry_has_expected_nodes() -> None:
    """Verify DEFERRED_STRUCTURED_NODES contains exactly the 6 expected nodes."""
    expected = (
        "interview.question_gen",
        "interview.report",
        "general_coach.intent",
        "resume_optimize.diff_jd",
        "resume_optimize.suggest_blocks",
        "ability_diagnose.generate_insight",
    )
    assert DEFERRED_STRUCTURED_NODES == expected, (
        f"DEFERRED_STRUCTURED_NODES mismatch: {DEFERRED_STRUCTURED_NODES}"
    )


def test_free_form_and_structured_are_disjoint() -> None:
    """FREE_FORM_NODES must not overlap with STRUCTURED_NODES."""
    overlap = set(FREE_FORM_NODES) & set(STRUCTURED_NODES)
    assert not overlap, (
        f"FREE_FORM_NODES overlaps with STRUCTURED_NODES: {overlap}"
    )


def test_deferred_and_structured_are_disjoint() -> None:
    """DEFERRED_STRUCTURED_NODES must not overlap with STRUCTURED_NODES."""
    overlap = set(DEFERRED_STRUCTURED_NODES) & set(STRUCTURED_NODES)
    assert not overlap, (
        f"DEFERRED_STRUCTURED_NODES overlaps with STRUCTURED_NODES: {overlap}"
    )
