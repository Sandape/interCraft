"""CLI for deterministic scoring, validation and fixture replay."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.modules.resume_intelligence.schemas import (
    DraftOutput,
    EvidenceMapOutput,
    JobParseOutput,
    SuggestionListOutput,
)
from app.modules.resume_intelligence.scoring import (
    Coverage,
    RequirementScoreInput,
    ScoringInput,
    calculate_job_fit,
)
from app.modules.resume_intelligence.validation import StructuredOutputError, parse_strict_output

CONTRACTS: dict[str, type[BaseModel]] = {
    "job_parse": JobParseOutput,
    "evidence_map": EvidenceMapOutput,
    "draft": DraftOutput,
    "suggestions": SuggestionListOutput,
}


def _envelope(command: str, *, result: Any = None, errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "ok": not errors,
        "command": command,
        "version": "resume-intelligence-cli.v1",
        "result": result,
        "errors": errors or [],
        "artifacts": [],
    }


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _score_payload(raw: dict[str, Any]) -> dict[str, Any]:
    requirements = [
        RequirementScoreInput(
            requirement_id=str(item["requirement_id"]),
            priority=str(item["priority"]),
            dimension=str(item["dimension"]),
            coverage=Coverage(str(item["coverage"])),
        )
        for item in raw.get("requirements", [])
    ]
    result = calculate_job_fit(
        ScoringInput(
            requirements=requirements,
            outcomes_quantification=float(raw.get("outcomes_quantification", 0)),
            expression_readability=float(raw.get("expression_readability", 0)),
            jd_completeness=float(raw.get("jd_completeness", 0)),
            evidence_trace_coverage=float(raw.get("evidence_trace_coverage", 0)),
            schema_validation_quality=float(raw.get("schema_validation_quality", 0)),
        )
    )
    return {
        "overall_score": result.overall_score,
        "confidence_score": result.confidence_score,
        "confidence_band": result.confidence_band,
        "dimensions": [item.__dict__ for item in result.dimensions],
        "hard_blockers": result.hard_blockers,
        "scoring_version": result.scoring_version,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="resume-intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    derive = sub.add_parser("derive")
    derive.add_argument("--fixture")
    derive.add_argument("--provider", choices=["mock", "real"], default="mock")
    derive.add_argument("--user-id")
    derive.add_argument("--job-id")
    derive.add_argument("--pages", type=int, choices=[1, 2, 3], default=1)
    derive.add_argument("--idempotency-key")
    derive.add_argument("--async", dest="async_mode", action="store_true")
    derive.add_argument("--json", action="store_true")

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--fixture")
    analyze.add_argument("--mode", choices=["general", "job_fit"], required=True)
    analyze.add_argument("--provider", choices=["mock", "real"], default="mock")
    analyze.add_argument("--user-id")
    analyze.add_argument("--resume-id")
    analyze.add_argument("--job-id")
    analyze.add_argument("--force", action="store_true")
    analyze.add_argument("--json", action="store_true")

    score = sub.add_parser("score")
    score.add_argument("--classification", required=True)
    score.add_argument("--scoring-version", default="scoring.v1")
    score.add_argument("--json", action="store_true")

    validate = sub.add_parser("validate-output")
    validate.add_argument("--contract", required=True, choices=sorted(CONTRACTS))
    validate.add_argument("--input", required=True)
    validate.add_argument("--source-manifest")
    validate.add_argument("--json", action="store_true")

    replay = sub.add_parser("replay")
    replay.add_argument("--fixture", required=True)
    replay.add_argument("--mode", choices=["mock", "real"], default="mock")
    replay.add_argument("--repeat", type=int, default=5)
    replay.add_argument("--report-out")
    replay.add_argument("--json", action="store_true")

    compare = sub.add_parser("compare")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "derive":
            if args.provider == "real":
                raise ValueError("real derive requires service/worker runtime")
            if args.fixture:
                fixture = Path(args.fixture)
                manifest = _load(str(fixture / "manifest.json")) if (fixture / "manifest.json").exists() else {}
                envelope = _envelope(
                    "derive",
                    result={
                        "mode": "mock",
                        "status": "succeeded",
                        "fixture": str(fixture),
                        "target_page_count": args.pages,
                        "case_id": manifest.get("case_id"),
                    },
                )
            elif args.user_id and args.job_id and args.idempotency_key:
                envelope = _envelope(
                    "derive",
                    result={
                        "mode": "mock",
                        "status": "queued" if args.async_mode else "succeeded",
                        "user_id": args.user_id,
                        "job_id": args.job_id,
                        "target_page_count": args.pages,
                    },
                )
            else:
                raise ValueError("derive requires --fixture or --user-id/--job-id/--idempotency-key")
        elif args.command == "analyze":
            if args.provider == "real":
                raise ValueError("real analyze requires service/worker runtime")
            if args.mode == "job_fit" and not (args.job_id or args.fixture):
                raise ValueError("job_fit analysis requires --job-id or fixture job snapshot")
            if args.fixture:
                fixture = Path(args.fixture)
                classification = fixture / "classification.json"
                result = _score_payload(_load(str(classification))) if classification.exists() else {}
                envelope = _envelope(
                    "analyze",
                    result={"mode": args.mode, "status": "complete", **result},
                )
            elif args.user_id and args.resume_id:
                envelope = _envelope(
                    "analyze",
                    result={
                        "mode": args.mode,
                        "status": "queued",
                        "user_id": args.user_id,
                        "resume_id": args.resume_id,
                        "job_id": args.job_id,
                    },
                )
            else:
                raise ValueError("analyze requires --fixture or --user-id/--resume-id")
        elif args.command == "score":
            if args.scoring_version != "scoring.v1":
                raise ValueError("unsupported scoring version")
            envelope = _envelope("score", result=_score_payload(_load(args.classification)))
        elif args.command == "validate-output":
            raw = Path(args.input).read_text(encoding="utf-8")
            parsed = parse_strict_output(raw, CONTRACTS[args.contract], contract=f"{args.contract}.v1")
            envelope = _envelope("validate-output", result={"contract": args.contract, "valid": True, "item_count": len(parsed.model_dump())})
        elif args.command == "replay":
            fixture = Path(args.fixture)
            classification = fixture / "classification.json"
            if args.mode == "real":
                raise ValueError("real replay requires the async live-eval runner")
            runs = [_score_payload(_load(str(classification))) for _ in range(max(1, args.repeat))]
            scores = [run["overall_score"] for run in runs]
            report = {"mode": "mock", "repeat": len(runs), "scores": scores, "max_min": max(scores) - min(scores), "stable": max(scores) - min(scores) <= 5}
            if args.report_out:
                Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.report_out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            envelope = _envelope("replay", result=report)
        else:
            baseline = _load(args.baseline)
            candidate = _load(args.candidate)
            envelope = _envelope("compare", result={"baseline_stable": bool(baseline.get("stable")), "candidate_stable": bool(candidate.get("stable")), "score_range_delta": float(candidate.get("max_min", 0)) - float(baseline.get("max_min", 0))})
    except StructuredOutputError as exc:
        print(json.dumps(_envelope(args.command, errors=[{"code": exc.code, "message": str(exc)}]), ensure_ascii=False))
        return 4
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps(_envelope(args.command, errors=[{"code": "INVALID_INPUT", "message": str(exc)}]), ensure_ascii=False))
        return 2
    print(json.dumps(envelope, ensure_ascii=False) if getattr(args, "json", False) else json.dumps(envelope["result"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
