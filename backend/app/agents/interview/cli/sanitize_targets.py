"""CLI: sanitize interview targets (REQ-058 T052)."""
from __future__ import annotations

import argparse
import json
import sys

from app.agents.interview.placeholders import sanitize_interview_target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sanitize company/position targets")
    parser.add_argument("--company", default="")
    parser.add_argument("--position", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    company, company_ok = sanitize_interview_target(args.company, kind="company")
    position, position_ok = sanitize_interview_target(args.position, kind="position")
    payload = {
        "company_valid": company_ok,
        "position_valid": position_ok,
        "display_company": company,
        "display_position": position,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
