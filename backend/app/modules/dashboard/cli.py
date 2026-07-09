"""CLI: dump dashboard summary for a user (REQ-057)."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from uuid import UUID

from app.core.db import get_session_factory, set_rls_user_id
from app.modules.dashboard.service import DEFAULT_TZ, DashboardService


async def _run(user_id: UUID, tz: str, as_json: bool) -> int:
    factory = get_session_factory()
    async with factory() as session:
        try:
            await set_rls_user_id(session, user_id)
        except Exception:  # noqa: BLE001
            pass
        summary = await DashboardService(session).build_summary(user_id, tz=tz)
    if as_json:
        print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0
    print(f"local_date={summary.local_date} tz={summary.tz}")
    print(f"greeting={summary.l0.greeting_context}")
    print(f"today_interviews={len(summary.l0.today_interviews)}")
    print(f"primary_cta={summary.l0.primary_cta.label} -> {summary.l0.primary_cta.href}")
    if summary.l1.next_action:
        print(f"next_action={summary.l1.next_action.id} tier={summary.l1.next_action.tier}")
    for seg in summary.l1.job_funnel:
        print(f"funnel.{seg.key}={seg.count}")
    print(f"activities={len(summary.l2.recent_activities)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dashboard.cli")
    parser.add_argument("--user-id", required=True, help="User UUID")
    parser.add_argument("--tz", default=DEFAULT_TZ)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        uid = UUID(args.user_id)
    except ValueError:
        print("invalid --user-id", file=sys.stderr)
        return 2
    try:
        ZoneInfo = __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo
        ZoneInfo(args.tz)
    except Exception:
        print(f"invalid --tz {args.tz}", file=sys.stderr)
        return 2
    return asyncio.run(_run(uid, args.tz, args.json))


if __name__ == "__main__":
    raise SystemExit(main())
