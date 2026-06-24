"""CLI entry point for the eval suite (T040).

Usage:
    uv run python -m app.eval.cli run --mode mock
    uv run python -m app.eval.cli run --mode mock --node interview.score
    uv run python -m app.eval.cli run --mode mock --report-out /tmp/eval.json

Exit codes:
    0 — all active cases pass
    1 — at least one active case failed (regression detected, or checker missed a known-bad case)
    2 — invocation error (no cases found, etc.)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import structlog

from app.eval.golden_loader import load_golden_cases
from app.eval.runner import EvalRunner

logger = structlog.get_logger("eval.cli")

# Default location of golden cases — version-controlled alongside spec.
_DEFAULT_SPEC_DIR = (
    Path(__file__).resolve().parents[3] / "specs" / "026-agent-eval-loop"
)


def cmd_run(args: argparse.Namespace) -> int:
    spec_dir = Path(args.spec_dir) if args.spec_dir else _DEFAULT_SPEC_DIR
    cases = load_golden_cases(spec_dir)

    if not cases:
        print(f"[eval] no golden cases found under {spec_dir}/golden/", file=sys.stderr)
        return 2

    if args.node:
        cases = [c for c in cases if c.node == args.node]
        if not cases:
            print(
                f"[eval] no cases match --node={args.node}", file=sys.stderr
            )
            return 2

    active_cases = [c for c in cases if c.status == "active"]
    print(f"[eval] loaded {len(cases)} cases ({len(active_cases)} active, "
          f"{len(cases) - len(active_cases)} stale)")

    runner = EvalRunner(cases=cases, mode=args.mode, model_name=args.model_name)
    report = asyncio.run(runner.run_all())

    print()
    print("=== Eval Report ===")
    print(f"  timestamp: {report.timestamp}")
    print(f"  git_sha:   {report.git_sha}")
    print(f"  model:     {report.model}")
    print(f"  total:     {report.total_cases}")
    print(f"  passed:    {report.passed_cases}")
    print(f"  failed:    {report.failed_cases}")
    print(f"  skipped:   {report.skipped_cases}")
    print()
    print("Per-node:")
    for node, stats in report.per_node.items():
        print(f"  {node}: pass_rate={stats['pass_rate']:.2%} "
              f"avg_fidelity={stats['avg_chinese_fidelity']:.3f}")

    print()
    print("Per-case verdicts:")
    for cr in report.case_results:
        status = "PASS" if cr.passed else "FAIL"
        print(f"  [{status}] {cr.case_id} ({cr.node}) — {cr.label}")
        if not cr.passed:
            for reason in cr.failure_reasons:
                print(f"          reason: {reason}")

    if args.report_out:
        out_path = Path(args.report_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report.to_json(), encoding="utf-8")
        print(f"\n[eval] report written to {out_path}")

    return 0 if report.failed_cases == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.eval.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run the eval suite against golden cases")
    run_p.add_argument(
        "--mode",
        choices=["mock", "real"],
        default="mock",
        help="mock = use stub LLM (deterministic, default); real = call DeepSeek (burns quota)",
    )
    run_p.add_argument(
        "--node",
        default=None,
        help="filter cases by node id (e.g. interview.score)",
    )
    run_p.add_argument(
        "--spec-dir",
        default=None,
        help=f"path to spec dir (default: {_DEFAULT_SPEC_DIR})",
    )
    run_p.add_argument(
        "--report-out",
        default=None,
        help="path to write JSON report",
    )
    run_p.add_argument(
        "--model-name",
        default=None,
        help="override model name in report (default: mock-llm / deepseek-v4-pro)",
    )
    run_p.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    # Default model name based on mode
    if not args.model_name:
        args.model_name = "deepseek-v4-pro" if args.mode == "real" else "mock-llm"

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
