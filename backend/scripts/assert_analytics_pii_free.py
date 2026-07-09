"""[REQ-048 AC-19b / AC-19] Assert analytics_events payload has no PII.

Queries ``analytics_events`` for the given ``--event-type`` and
verifies the JSONB ``payload`` does NOT contain any of the
``--forbidden-keys`` (default: ``question_text, score, answer,
expected_points, interview_plan`` per FR-055).

Exit code:

- 0 when no forbidden keys are found in any matching row.
- 1 when at least one row contains a forbidden key.

Usage:

    cd backend && uv run python -m scripts.assert_analytics_pii_free \
        --event-type doubao_card_rendered \
        --forbidden-keys question_text,score,answer,expected_points,interview_plan
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from sqlalchemy import text

from app.core.db import _session_cm


DEFAULT_FORBIDDEN_KEYS = (
    "question_text",
    "score",
    "answer",
    "expected_points",
    "interview_plan",
)


def _payload_contains(payload: Any, forbidden: set[str]) -> list[str]:
    """Walk the payload looking for forbidden keys at any depth."""
    hits: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in forbidden:
                    hits.append(f"{path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(payload, "$")
    return hits


async def scan(
    event_type: str,
    forbidden: set[str],
    *,
    limit: int = 1000,
) -> dict:
    """Return a dict { event_type, scanned, hits: [{ id, payload_keys, path }] }."""
    async with _session_cm() as session:
        result = await session.execute(
            text(
                "SELECT id, payload FROM analytics_events "
                "WHERE event_type = :event_type "
                "ORDER BY created_at DESC LIMIT :limit"
            ),
            {"event_type": event_type, "limit": int(limit)},
        )
        rows = result.fetchall()
    hits: list[dict] = []
    for row in rows:
        rid, payload = row[0], row[1]
        paths = _payload_contains(payload, forbidden)
        if paths:
            hits.append({"id": str(rid), "forbidden_paths": paths})
    return {"event_type": event_type, "scanned": len(rows), "hits": hits}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assert analytics_events payload has no PII (FR-055 / AC-19b).",
    )
    parser.add_argument(
        "--event-type",
        required=True,
        help="analytics_events.event_type to scan",
    )
    parser.add_argument(
        "--forbidden-keys",
        default=",".join(DEFAULT_FORBIDDEN_KEYS),
        help=f"Comma-separated forbidden keys (default: {','.join(DEFAULT_FORBIDDEN_KEYS)})",
    )
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    forbidden = {k.strip() for k in args.forbidden_keys.split(",") if k.strip()}
    result = asyncio.run(scan(args.event_type, forbidden, limit=args.limit))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"event_type={args.event_type} scanned={result['scanned']} "
            f"hits={len(result['hits'])} forbidden_keys={sorted(forbidden)}"
        )
        for hit in result["hits"]:
            print(f"  - {hit['id']}: {hit['forbidden_paths']}")
    return 0 if not result["hits"] else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["scan", "DEFAULT_FORBIDDEN_KEYS"]