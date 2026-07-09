"""[REQ-048 T094] eval_drill_accuracy.py — AC-05 eval-set gate.

Reads the hand-labeled drill-eval-set.md and computes top-5 overlap
accuracy against a real (or simulated) drill selection.

Usage:
    uv run python -m scripts.eval_drill_accuracy \
        --eval-set docs/evidence/048-interview-modes-and-doubao-card/drill-eval-set.md \
        --error-counts 100,500

Exit codes:
    0: all scenarios passed (accuracy >= 70%)
    1: at least one scenario failed
    2: eval-set file missing (caller should rely on inline fixture AC-04c)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_eval_set(path: Path) -> list[dict]:
    """Parse the eval-set markdown into a list of test cases.

    Format: each case starts with ``#### Case N — <title>`` followed by
    ``- **scenario**: <bucket>`` etc. We extract the structured fields.
    """
    if not path.exists():
        print(f"ERROR: eval-set file not found: {path}", file=sys.stderr)
        sys.exit(2)

    text = path.read_text(encoding="utf-8")
    cases: list[dict] = []
    current: dict | None = None

    for line in text.splitlines():
        line_stripped = line.strip()
        if line_stripped.startswith("#### Case"):
            if current is not None:
                cases.append(current)
            current = {"title": line_stripped}
        elif current is not None and ":" in line_stripped:
            key, _, value = line_stripped.partition(":")
            # Strip surrounding asterisks (markdown bold) and dashes.
            key = key.lstrip("- ").strip().strip("*").strip()
            value = value.strip()
            current[key] = value

    if current is not None:
        cases.append(current)

    return cases


def compute_accuracy(case: dict, predicted_ids: list[str]) -> float:
    """Compute top-5 overlap between predicted and expected error_question_ids."""
    expected_str = case.get("expected_error_question_ids", "")
    if not expected_str:
        return 0.0
    # The eval-set uses a markdown list; for simplicity we extract UUID-like tokens.
    import re

    expected_ids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", expected_str)
    if not expected_ids:
        return 0.0
    overlap = sum(1 for eid in expected_ids[:5] if eid in predicted_ids[:5])
    return overlap / min(5, len(expected_ids))


def main() -> int:
    parser = argparse.ArgumentParser(description="Drill selection accuracy gate")
    parser.add_argument("--eval-set", type=Path, required=True, help="Path to drill-eval-set.md")
    parser.add_argument("--error-counts", type=str, default="100,500", help="Comma-separated error counts")
    parser.add_argument("--scenario", type=str, default=None, help="Filter to a single scenario bucket")
    parser.add_argument("--threshold", type=float, default=0.70, help="Min accuracy threshold (AC-05: 0.70)")
    args = parser.parse_args()

    cases = parse_eval_set(args.eval_set)
    if args.scenario:
        cases = [c for c in cases if c.get("scenario") == args.scenario]

    if not cases:
        print(f"No cases matched (scenario={args.scenario!r})", file=sys.stderr)
        return 2

    print(f"Eval set: {args.eval_set} ({len(cases)} cases)")

    all_pass = True
    for case in cases:
        # When run without live backend, we report an indicative accuracy
        # based on whether the expected_dimensions are present (placeholder
        # until T049 wires a real drill selector probe).
        predicted_ids: list[str] = []
        accuracy = compute_accuracy(case, predicted_ids)

        verdict = "PASS" if accuracy >= args.threshold else "FAIL"
        if verdict == "FAIL":
            all_pass = False
        print(
            f"  [{verdict}] {case.get('title', '?')[:60]} "
            f"accuracy={accuracy:.2f} threshold={args.threshold:.2f}",
        )

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())