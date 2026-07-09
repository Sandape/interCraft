"""Analyze prompt A/B results — compute aggregate metrics + pick a winner.

Reads `docs/evidence/053/prompt_ab_results.json` and writes:
  - `docs/evidence/053/prompt_ab_comparison.md`  — human-readable table
  - `docs/evidence/053/prompt_ab_summary.json`   — aggregated metrics

Selection rules (per REQ-053 spec):
  1. quality_pass_rate > A's  (hard requirement — losing prompt disqualified)
  2. avg_weighted_chars closer to the 2500 sweet-spot (target window 2000-3000)
  3. avg_question_count ≥ 3 and ideally higher than A's
  4. sections_complete_rate ≥ 0.9 (must contain all 6 emojis)
  5. weakness_section_ok rate is the tie-breaker for B's stricter requirement

Run:
    cd backend && uv run python -m app.eval.analyze_prompt_ab
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


RESULTS_PATH = BACKEND_ROOT.parent / "docs" / "evidence" / "053" / "prompt_ab_results.json"
COMPARISON_PATH = BACKEND_ROOT.parent / "docs" / "evidence" / "053" / "prompt_ab_comparison.md"
SUMMARY_PATH = BACKEND_ROOT.parent / "docs" / "evidence" / "053" / "prompt_ab_summary.json"


def _aggregate(rows: list[dict]) -> dict:
    """Aggregate metrics across one prompt variant."""
    ok_rows = [r for r in rows if r.get("ok") and r.get("metrics")]
    if not ok_rows:
        return {
            "samples": 0,
            "ok_count": 0,
            "quality_pass_count": 0,
            "quality_pass_rate": 0.0,
            "sections_complete_count": 0,
            "sections_complete_rate": 0.0,
            "avg_weighted_chars": 0.0,
            "median_weighted_chars": 0.0,
            "in_window_count": 0,
            "in_window_rate": 0.0,
            "avg_question_count": 0.0,
            "history_table_count": 0,
            "history_table_rate": 0.0,
            "weakness_section_ok_count": 0,
            "weakness_section_ok_rate": 0.0,
            "avg_duration_sec": 0.0,
            "avg_prompt_tokens": 0.0,
            "avg_completion_tokens": 0.0,
        }
    m = [r["metrics"] for r in ok_rows]
    n = len(m)
    weighted = [x["weighted_chars"] for x in m]
    in_window = sum(1 for w in weighted if 2000 <= w <= 3000)
    return {
        "samples": len(rows),
        "ok_count": n,
        "quality_pass_count": sum(1 for x in m if x["quality_passed"]),
        "quality_pass_rate": round(sum(1 for x in m if x["quality_passed"]) / n, 3),
        "sections_complete_count": sum(1 for x in m if x["has_all_six_sections"]),
        "sections_complete_rate": round(
            sum(1 for x in m if x["has_all_six_sections"]) / n, 3),
        "avg_weighted_chars": round(statistics.mean(weighted), 1),
        "median_weighted_chars": round(statistics.median(weighted), 1),
        "in_window_count": in_window,
        "in_window_rate": round(in_window / n, 3),
        "avg_question_count": round(statistics.mean([x["question_count"] for x in m]), 2),
        "history_table_count": sum(1 for x in m if x["has_history_table"]),
        "history_table_rate": round(
            sum(1 for x in m if x["has_history_table"]) / n, 3),
        "weakness_section_ok_count": sum(1 for x in m if x["weakness_section_ok"]),
        "weakness_section_ok_rate": round(
            sum(1 for x in m if x["weakness_section_ok"]) / n, 3),
        "avg_duration_sec": round(
            statistics.mean([r.get("duration_sec", 0) for r in ok_rows]), 2),
        "avg_prompt_tokens": round(
            statistics.mean([r.get("prompt_tokens", 0) for r in ok_rows]), 0),
        "avg_completion_tokens": round(
            statistics.mean([r.get("completion_tokens", 0) for r in ok_rows]), 0),
    }


def _pick_winner(agg_a: dict, agg_b: dict) -> tuple[str, list[str]]:
    """Pick A or B with reasons.

    Selection priority (in order):
      1. quality_pass_rate — strict; higher wins.
      2. in_window_rate (chars within 2000-3000) — strictly preferred.
      3. avg_weighted_chars distance to 2500 — closer is better.
      4. sections_complete_rate — secondary.
      5. avg_question_count, history_table_rate, weakness_section_ok_rate
         as tiebreakers (any of these).
    """
    reasons: list[str] = []

    if agg_a["samples"] == 0 or agg_b["samples"] == 0:
        return "A", ["missing data; default to A"]

    # Hard rule 1: quality
    if agg_b["quality_pass_rate"] > agg_a["quality_pass_rate"]:
        return "B", [
            f"B quality {agg_b['quality_pass_rate']} > A {agg_a['quality_pass_rate']} — hard rule"
        ]
    if agg_a["quality_pass_rate"] > agg_b["quality_pass_rate"]:
        return "A", [
            f"A quality {agg_a['quality_pass_rate']} > B {agg_b['quality_pass_rate']} — hard rule"
        ]

    # Hard rule 2: in-window rate
    if agg_b["in_window_rate"] > agg_a["in_window_rate"]:
        return "B", [
            f"B in-window rate {agg_b['in_window_rate']} > A {agg_a['in_window_rate']} — hard rule"
        ]
    if agg_a["in_window_rate"] > agg_b["in_window_rate"]:
        return "A", [
            f"A in-window rate {agg_a['in_window_rate']} > B {agg_b['in_window_rate']} — hard rule"
        ]

    # Soft rule 1: closer to 2500 sweet-spot
    a_dist = abs(agg_a["avg_weighted_chars"] - 2500)
    b_dist = abs(agg_b["avg_weighted_chars"] - 2500)
    if b_dist < a_dist:
        reasons.append(
            f"B avg_chars closer to 2500 ({agg_b['avg_weighted_chars']} vs {agg_a['avg_weighted_chars']})")
    elif a_dist < b_dist:
        reasons.append(
            f"A avg_chars closer to 2500 ({agg_a['avg_weighted_chars']} vs {agg_b['avg_weighted_chars']})")

    # Soft rule 2: sections completeness
    if agg_b["sections_complete_rate"] > agg_a["sections_complete_rate"]:
        reasons.append(
            f"B sections {agg_b['sections_complete_rate']} > A {agg_a['sections_complete_rate']}")
    elif agg_a["sections_complete_rate"] > agg_b["sections_complete_rate"]:
        reasons.append(
            f"A sections {agg_a['sections_complete_rate']} > B {agg_b['sections_complete_rate']}")

    # Soft rule 3: weakness quality (B variant requirement)
    if agg_b["weakness_section_ok_rate"] > agg_a["weakness_section_ok_rate"]:
        reasons.append(
            f"B weakness ok {agg_b['weakness_section_ok_rate']} > A {agg_a['weakness_section_ok_rate']}")

    # Soft rule 4: question count
    if agg_b["avg_question_count"] > agg_a["avg_question_count"]:
        reasons.append(
            f"B questions {agg_b['avg_question_count']} > A {agg_a['avg_question_count']}")

    if not reasons:
        return "A", ["no clear advantage; default to A (control)"]

    # Decide based on weighted reasons
    b_wins = sum(1 for r in reasons if r.startswith("B "))
    a_wins = sum(1 for r in reasons if r.startswith("A "))
    if b_wins > a_wins:
        return "B", reasons
    if a_wins > b_wins:
        return "A", reasons
    # tie: prefer A (it's the established control)
    return "A", reasons + ["tie on soft rules — prefer A (control)"]


def _render_markdown(agg_a: dict, agg_b: dict, winner: str, reasons: list[str]) -> str:
    rows = [
        ("样本数 (samples)", agg_a["samples"], agg_b["samples"]),
        ("成功调用数", agg_a["ok_count"], agg_b["ok_count"]),
        ("质量检查通过率", agg_a["quality_pass_rate"], agg_b["quality_pass_rate"]),
        ("6 章节完整率", agg_a["sections_complete_rate"], agg_b["sections_complete_rate"]),
        ("平均加权字符数", agg_a["avg_weighted_chars"], agg_b["avg_weighted_chars"]),
        ("中位加权字符数", agg_a["median_weighted_chars"], agg_b["median_weighted_chars"]),
        ("字数落在 2000-3000 比例", agg_a["in_window_rate"], agg_b["in_window_rate"]),
        ("平均面经题目数", agg_a["avg_question_count"], agg_b["avg_question_count"]),
        ("📊 历史对比表格命中率", agg_a["history_table_rate"], agg_b["history_table_rate"]),
        ("⚠️ 薄弱环节合规率", agg_a["weakness_section_ok_rate"], agg_b["weakness_section_ok_rate"]),
        ("平均耗时 (秒)", agg_a["avg_duration_sec"], agg_b["avg_duration_sec"]),
        ("平均 prompt tokens", agg_a["avg_prompt_tokens"], agg_b["avg_prompt_tokens"]),
        ("平均 completion tokens", agg_a["avg_completion_tokens"], agg_b["avg_completion_tokens"]),
    ]
    lines = [
        "# REQ-053 Prompt A vs B 评测报告",
        "",
        f"**胜出 prompt: `{winner}`**",
        "",
        "## 决策理由",
        "",
    ]
    for r in reasons:
        lines.append(f"- {r}")
    lines += [
        "",
        "## 指标对比表",
        "",
        "| 指标 | PROMPT_A | PROMPT_B |",
        "|------|---------|---------|",
    ]
    for name, a, b in rows:
        lines.append(f"| {name} | {a} | {b} |")
    lines += [
        "",
        "## 决策总结",
        "",
        f"- 胜出 prompt: PROMPT_{winner}（保留 `app/modules/research/report_generator.py:SYSTEM_PROMPT` 默认值）"
        if winner == "A"
        else f"- 胜出 prompt: PROMPT_{winner}（替换 `app/modules/research/report_generator.py:SYSTEM_PROMPT`）",
        "- 替换方式（若需要）: 直接覆盖 (verbatim)；保留原有 `## 历史对比（可选）` 段。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    if not RESULTS_PATH.exists():
        print(f"ERROR: {RESULTS_PATH} not found. Run run_prompt_ab.py first.", file=sys.stderr)
        return 2

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    rows_a = [r for r in data if r.get("label") == "A"]
    rows_b = [r for r in data if r.get("label") == "B"]
    agg_a = _aggregate(rows_a)
    agg_b = _aggregate(rows_b)
    winner, reasons = _pick_winner(agg_a, agg_b)

    SUMMARY_PATH.write_text(
        json.dumps(
            {"winner": winner, "reasons": reasons, "A": agg_a, "B": agg_b},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    md = _render_markdown(agg_a, agg_b, winner, reasons)
    COMPARISON_PATH.write_text(md, encoding="utf-8")

    print(md)
    print(f"\n✓ Summary: {SUMMARY_PATH}")
    print(f"✓ Comparison: {COMPARISON_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
