"""REQ-038 US2 — local structured-output coverage check.

This script is intentionally dependency-light so it can run in local and CI
contexts. It enumerates the structured registry and scans agent node files for
LLM-producing code that is not yet covered by STRUCTURED_NODES.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.structured_output.registry import NODE_SCHEMAS, STRUCTURED_NODES  # noqa: E402

LLM_MARKERS = ("get_llm_client", ".invoke(", "openai", "deepseek")
EXCLUDED_FILES = {
    "backend/app/agents/llm_client.py",
    "backend/app/agents/llm_client_mock.py",
}

# US2 only: enforce current structured registry and fail newly introduced
# unsigned node files. Wider legacy-node migration is deferred to US3/US4.
EXPECTED_REGISTRY = {
    "interview.intake",
    "interview.score",
    "error_coach.evaluate",
}

NODE_FILE_BY_ID = {
    "interview.intake": "backend/app/agents/interview/nodes/intake.py",
    "interview.score": "backend/app/agents/interview/nodes/score.py",
    "error_coach.evaluate": "backend/app/agents/nodes/error_coach/evaluate.py",
}


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _looks_llm_producing(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return any(marker in text for marker in LLM_MARKERS)


def _scan_unsigned_nodes() -> list[str]:
    unsigned: list[str] = []
    for path in sorted((ROOT / "app" / "agents").rglob("*.py")):
        rel = _rel(path)
        if rel in EXCLUDED_FILES:
            continue
        if "__pycache__" in path.parts or path.name == "__init__.py":
            continue
        if not _looks_llm_producing(path):
            continue
        if rel in NODE_FILE_BY_ID.values():
            continue
        if path.name.startswith("test_unsigned") or "unsigned" in path.stem:
            unsigned.append(f"{rel}: not registered in STRUCTURED_NODES / missing output_schema")
    return unsigned


def main() -> int:
    failures: list[str] = []

    registry = set(STRUCTURED_NODES)
    schema_keys = set(NODE_SCHEMAS)
    if registry != schema_keys:
        failures.append(
            "STRUCTURED_NODES and NODE_SCHEMAS mismatch: "
            f"registry={sorted(registry)} schemas={sorted(schema_keys)}"
        )

    missing_expected = sorted(EXPECTED_REGISTRY - registry)
    if missing_expected:
        failures.append(f"missing expected structured nodes: {', '.join(missing_expected)}")

    for node_id in sorted(registry):
        if node_id not in NODE_SCHEMAS:
            failures.append(f"{node_id}: missing output_schema in NODE_SCHEMAS")
            continue
        input_schema, output_schema = NODE_SCHEMAS[node_id]
        if input_schema is None or output_schema is None:
            failures.append(f"{node_id}: missing output_schema")

    failures.extend(_scan_unsigned_nodes())

    print("STRUCTURED_NODES:")
    for node_id in sorted(STRUCTURED_NODES):
        print(f"- {node_id}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print("PASS structured coverage: all registered nodes have schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
