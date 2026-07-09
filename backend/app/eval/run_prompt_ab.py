"""Run the REQ-053 prompt A/B experiment with REAL LLM calls.

For each of the 5 fixtures in `prompts_ab.AB_FIXTURES`:
  - Generate one report using PROMPT_A
  - Generate one report using PROMPT_B

Both calls go through `app.agents.llm_client.get_llm_client()` which uses
DeepSeek V4 Pro — no mocking. Each report is scored by the project's own
quality checker so we can compare pass-rates.

Output: `docs/evidence/053/prompt_ab_results.json` containing all reports +
per-report metrics for the downstream analyzer.

Run:
    cd backend && uv run python -m app.eval.run_prompt_ab
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend root is on the path
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.eval.prompts_ab import AB_FIXTURES, PROMPT_A, PROMPT_B  # noqa: E402
from app.modules.research.quality_checker import check_report_quality  # noqa: E402

REQUIRED_EMOJIS = ["📋", "🏢", "📝", "🎯", "⚠️", "💡"]


# Demo user that exists in the DB so the LLM client's ai_messages INSERT
# succeeds (otherwise we'd hit a foreign-key violation after the LLM call).
DEMO_USER_UID = os.environ.get(
    "PROMPT_AB_USER_ID", "019ebc56-fb4f-7978-bf91-29abc5c13d93"
)


def _build_user_message(fixture: dict) -> str:
    payload = {
        "company": fixture["company"],
        "position": fixture["position"],
        "interview_time": fixture["interview_time_iso"],
        "interview_round": fixture["interview_round"],
        "search_results_by_dimension": {
            k: [{"title": r.get("title"), "url": r.get("url"),
                 "content": (r.get("content") or "")[:500]} for r in v]
            for k, v in fixture["search_results"].items()
        },
        "user_weakness": fixture["user_weakness"],
        "historical_comparison": None,
    }
    return (
        "请基于以下信息生成面试备战报告：\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


async def _call_llm_real(prompt: str, fixture: dict, label: str) -> dict[str, Any]:
    """One real LLM invocation + per-report metrics."""
    from app.agents.llm_client import get_llm_client

    user_msg = _build_user_message(fixture)
    client = get_llm_client()
    started = time.monotonic()
    # Use the demo user so ai_messages INSERT satisfies the FK constraint.
    test_uid = DEMO_USER_UID
    try:
        response = await client.invoke(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg},
            ],
            estimated_tokens=8000,
            user_id=test_uid,
            thread_id=f"prompt-ab-{label}-{fixture['company'][:20]}",
            node_name=f"prompt_ab_{label}",
            max_retries=2,
            timeout_ms=120_000,
        )
    except Exception as exc:
        return {
            "label": label,
            "fixture": fixture["name"],
            "company": fixture["company"],
            "ok": False,
            "error": str(exc)[:300],
            "duration_sec": round(time.monotonic() - started, 2),
        }

    content = response.get("content", "") or ""
    duration = round(time.monotonic() - started, 2)
    return {
        "label": label,
        "fixture": fixture["name"],
        "company": fixture["company"],
        "ok": bool(content),
        "content": content,
        "duration_sec": duration,
        "prompt_tokens": int(response.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(response.get("completion_tokens", 0) or 0),
    }


def _score_report(report_md: str, fixture: dict) -> dict[str, Any]:
    """Run the project's own quality checker + additional metric extraction."""
    has_ability = fixture["user_weakness"].get("has_ability_data", False)
    passed, failures = check_report_quality(
        report_md, company=fixture["company"], user_has_ability_data=has_ability
    )

    # Sections
    has_all_sections = all(e in report_md for e in REQUIRED_EMOJIS)

    # Char count (Chinese=1, ASCII=0.5 per the spec)
    chinese = sum(1 for c in report_md if "一" <= c <= "鿿")
    ascii_chars = sum(1 for c in report_md if c.isascii() and not c.isspace())
    weighted_chars = chinese + ascii_chars * 0.5

    # Interview question count (numbered list + ? / ？)
    import re
    question_patterns = [
        re.compile(r"^\s*\d+[\.\)、]\s*.+[\?？]"),
        re.compile(r"^\s*[一二三四五六七八九十][\.\)、]\s*.+[\?？]"),
    ]
    q_count = sum(
        1 for line in report_md.split("\n")
        if line.strip() and any(p.match(line.strip()) for p in question_patterns)
    )

    # History comparison table (B variant requirement)
    has_history_table = "📊 历史对比" in report_md and "|" in report_md

    # Weakness section contains dimension key + score (B variant requirement)
    weakness_ok = False
    if "⚠️ 你的薄弱环节" in report_md:
        section = report_md.split("⚠️ 你的薄弱环节", 1)[1].split("##", 1)[0]
        has_dim_key = any(
            d["key"] in section for d in fixture["user_weakness"].get("dimensions", [])
        )
        has_score = bool(re.search(r"\d{1,3}", section))
        weakness_ok = has_dim_key and has_score

    return {
        "quality_passed": passed,
        "quality_failures": failures,
        "has_all_six_sections": has_all_sections,
        "weighted_chars": round(weighted_chars, 1),
        "chinese_chars": chinese,
        "ascii_chars": ascii_chars,
        "question_count": q_count,
        "has_history_table": has_history_table,
        "weakness_section_ok": weakness_ok,
        "content_length": len(report_md),
    }


async def main() -> int:
    settings_label = "REAL_LLM"
    print(f"=== REQ-053 Prompt A/B Experiment ({settings_label}) ===", flush=True)
    fixtures_to_run = os.environ.get("PROMPT_AB_FIXTURE_LIMIT")
    if fixtures_to_run:
        fixtures = AB_FIXTURES[: int(fixtures_to_run)]
        print(f"Fixtures: {len(fixtures)} (limited via PROMPT_AB_FIXTURE_LIMIT)", flush=True)
    else:
        fixtures = AB_FIXTURES
        print(f"Fixtures: {len(fixtures)}", flush=True)

    output_dir = BACKEND_ROOT.parent / "docs" / "evidence" / "053"
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for i, fixture in enumerate(fixtures):
        for label, prompt in [("A", PROMPT_A), ("B", PROMPT_B)]:
            print(f"\n[{i+1}/{len(fixtures)}] -> {fixture['name']} | Prompt {label}", flush=True)
            raw = await _call_llm_real(prompt, fixture, label)
            metrics = (
                _score_report(raw["content"], fixture) if raw.get("ok") else {}
            )
            row = {
                **raw,
                "metrics": metrics,
                "model_used": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            }
            results.append(row)
            # Persist after every call so partial progress is not lost
            out_path = output_dir / "prompt_ab_results.json"
            out_path.write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            status = (
                f"chars={metrics.get('weighted_chars', 0)} "
                f"questions={metrics.get('question_count', 0)} "
                f"sections={'OK' if metrics.get('has_all_six_sections') else 'MISS'} "
                f"quality={'PASS' if metrics.get('quality_passed') else 'FAIL'}"
            )
            print(f"   {status} | {raw.get('duration_sec', 0)}s | saved {len(results)} rows", flush=True)

    print(f"\nDONE. Wrote {len(results)} rows -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
