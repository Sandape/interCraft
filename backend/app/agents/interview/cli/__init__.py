"""[REQ-048 US2] ``select_drill`` CLI surface (T024) — manual drill selection verification.

Run from backend/ root:

    uv run python -m app.agents.interview.cli.select_drill \
        --user-id <uuid> --job-id <uuid> [--no-cache]

Phase 1+2 skeleton — body filled in during Phase 4 / US2.
"""
from __future__ import annotations

import argparse


def main() -> None:
    """CLI entry point — argparse stub."""
    p = argparse.ArgumentParser(description="Manual drill selection verification")
    p.add_argument("--user-id", required=True)
    p.add_argument("--job-id", default=None)
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args()
    print(
        f"# skeleton — Phase 4 / US2 body. user_id={args.user_id} "
        f"job_id={args.job_id} no_cache={args.no_cache}"
    )


if __name__ == "__main__":
    main()