"""Artifact path helpers for REQ-045 eval evidence."""
from __future__ import annotations

from pathlib import Path

DEFAULT_EVIDENCE_ROOT = Path("docs/evidence/045-llm-ops-eval-workflow")


def safe_run_id(run_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in run_id)
    return cleaned.strip("-") or "run"


def eval_artifact_dir(
    run_id: str,
    *,
    evidence_root: Path | str = DEFAULT_EVIDENCE_ROOT,
) -> Path:
    return Path(evidence_root) / safe_run_id(run_id)


def eval_report_paths(
    run_id: str,
    *,
    evidence_root: Path | str = DEFAULT_EVIDENCE_ROOT,
) -> dict[str, Path]:
    base = eval_artifact_dir(run_id, evidence_root=evidence_root)
    return {
        "json": base / "eval-report.json",
        "markdown": base / "eval-report.md",
    }


__all__ = [
    "DEFAULT_EVIDENCE_ROOT",
    "eval_artifact_dir",
    "eval_report_paths",
    "safe_run_id",
]
