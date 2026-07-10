"""CLI: select questions from a plan JSON (REQ-058 T052)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.agents.interview.plan_questions import select_next_question_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select questions from interview plan")
    parser.add_argument("--plan", required=True, help="Path to plan JSON")
    parser.add_argument("--max", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    asked: list[dict] = []
    rows = []
    for _ in range(args.max):
        spec = select_next_question_spec(
            interview_plan=plan,
            plan_status="ready",
            degraded=False,
            questions=asked,
            max_questions=args.max,
        )
        row = {
            "question_no": spec.question_no,
            "source": spec.source,
            "dimension_or_focus": spec.focus,
            "question": spec.question,
        }
        rows.append(row)
        asked.append(
            {
                "question": spec.question or f"generated-{spec.question_no}",
                "source": spec.source,
            }
        )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['question_no']}\t{r['source']}\t{r['dimension_or_focus']}\t{r['question']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
