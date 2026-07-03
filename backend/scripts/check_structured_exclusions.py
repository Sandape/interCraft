"""REQ-038 US4 — Bidirectional structured-output exclusions check.

Reads ``registry.FREE_FORM_NODES`` / ``registry.DEFERRED_STRUCTURED_NODES``
and ``docs/contracts/structured_output_exclusions.md``, then asserts:

1. Every registry node appears in the doc with a matching ``kind``.
2. Every doc node belongs to the correct registry tuple.
3. No ``STRUCTURED_NODES`` entry appears in the doc.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.structured_output.registry import (  # noqa: E402
    DEFERRED_STRUCTURED_NODES,
    FREE_FORM_NODES,
    STRUCTURED_NODES,
)

_DOC_PATH = ROOT.parent / "docs" / "contracts" / "structured_output_exclusions.md"


def _parse_doc(doc_path: Path) -> dict[str, str]:
    """Parse the Markdown table and return {node_id: kind}."""
    text = doc_path.read_text(encoding="utf-8")
    rows: dict[str, str] = {}

    # Find the table body: lines starting with "|" after the header separator.
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
            # Expected: empty, node_id, kind, exclusion_reason, empty
            if len(parts) >= 5:
                node_id = parts[1]
                kind = parts[2]
                if node_id and kind:
                    rows[node_id] = kind

    return rows


def main() -> int:
    failures: list[str] = []

    if not _DOC_PATH.exists():
        print(f"FAIL: exclusion doc not found at {_DOC_PATH}", file=sys.stderr)
        return 1

    doc_rows = _parse_doc(_DOC_PATH)

    # Build canonical maps.
    free_form_set = set(FREE_FORM_NODES)
    deferred_set = set(DEFERRED_STRUCTURED_NODES)
    structured_set = set(STRUCTURED_NODES)
    all_excluded = free_form_set | deferred_set

    # 1. Every registry node must be in the doc.
    for node_id in sorted(all_excluded):
        if node_id not in doc_rows:
            failures.append(f"registry node '{node_id}' missing from exclusion doc")

    # 2. Every doc entry must match the registry.
    for node_id, kind in doc_rows.items():
        if node_id in structured_set:
            failures.append(
                f"doc node '{node_id}' is a STRUCTURED_NODES entry "
                "(should not be in exclusion doc)"
            )
        elif node_id not in all_excluded:
            failures.append(
                f"doc node '{node_id}' not found in FREE_FORM_NODES or "
                f"DEFERRED_STRUCTURED_NODES"
            )
        elif kind == "free_form" and node_id not in free_form_set:
            failures.append(
                f"doc node '{node_id}' marked as free_form but not in "
                f"FREE_FORM_NODES"
            )
        elif kind == "deferred" and node_id not in deferred_set:
            failures.append(
                f"doc node '{node_id}' marked as deferred but not in "
                f"DEFERRED_STRUCTURED_NODES"
            )
        elif kind not in ("free_form", "deferred"):
            failures.append(
                f"doc node '{node_id}' has unknown kind '{kind}'"
            )

    # 3. No structured nodes in the doc.
    for node_id in sorted(structured_set):
        if node_id in doc_rows:
            failures.append(
                f"structured node '{node_id}' should not appear in exclusion doc"
            )

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1

    print("PASS structured exclusions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
