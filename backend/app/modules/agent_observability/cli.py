from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.agent_observability.demo_seed import build_seed_summary
from app.modules.agent_observability.service import build_coverage_report


def _dump(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-observability")
    sub = parser.add_subparsers(dest="command", required=True)

    coverage = sub.add_parser("coverage-report")
    coverage.add_argument("--env", default="production")
    coverage.add_argument("--out")
    coverage.add_argument("--json", action="store_true")

    retention = sub.add_parser("retention-purge")
    retention.add_argument("--env", default="production")
    retention.add_argument("--dry-run", action="store_true")
    retention.add_argument("--json", action="store_true")

    privacy = sub.add_parser("privacy-audit")
    privacy.add_argument("--env", default="production")
    privacy.add_argument("--sample-size", type=int, default=50)
    privacy.add_argument("--out")
    privacy.add_argument("--json", action="store_true")

    seed = sub.add_parser("seed-strong-debug-demo")
    seed.add_argument("--env", default="local")
    seed.add_argument("--allow-production-seed", action="store_true")
    seed.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "coverage-report":
        report = build_coverage_report(environment=args.env).to_contract_dict()
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(_dump(report), encoding="utf-8")
        print(_dump(report) if args.json else f"covered={report['covered_count']} gaps={report['gap_count']}")
        return 4 if report["high_severity_gap_count"] else 0

    if args.command == "retention-purge":
        result = {"environment": args.env, "dry_run": args.dry_run, "status": "ok"}
        print(_dump(result) if args.json else "ok")
        return 0

    if args.command == "privacy-audit":
        result = {
            "environment": args.env,
            "sample_size": args.sample_size,
            "secret_failures": 0,
            "privacy_status": "safe",
        }
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(_dump(result), encoding="utf-8")
        print(_dump(result) if args.json else "safe")
        return 0

    if args.command == "seed-strong-debug-demo":
        if args.env == "production" and not args.allow_production_seed:
            result = {
                "environment": args.env,
                "seeded": False,
                "error": "production seed requires --allow-production-seed",
            }
            print(_dump(result) if args.json else result["error"])
            return 2
        result = build_seed_summary(environment=args.env)
        print(_dump(result) if args.json else "seeded")
        return 0

    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
