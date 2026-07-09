"""V2 cycle demo — real DeepSeek + 026 ChineseFidelityChecker.

Run: cd backend && LLM_MOCK_MODE=0 uv run python scripts/demo_v2_real_llm.py

Demonstrates the v2 cycle's most user-visible value:
  - 026 Eval Loop ChineseFidelityChecker catching DeepSeek's occasional
    English outputs on zh-CN prompts (memory interview_report_chinese_caveat).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.llm_client import get_llm_client
from app.eval.checker import ChineseFidelityChecker


async def run_one(client, label: str, system_prompt: str, user_message: str) -> dict | None:
    """Run one LLM call + check fidelity. Returns None on network failure."""
    print(f"\n{'='*70}")
    print(f"[{label}]")
    print(f"System: {system_prompt[:80]}...")
    print(f"User:   {user_message[:80]}...")

    try:
        response = await client.invoke(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            estimated_tokens=2000,
            user_id="019ebc56-9f93-7d19-ade9-b5f18b8c16c1",
            thread_id=f"demo-{label}",
            node_name=f"demo-{label}",
            timeout_ms=30_000,
            max_retries=1,
        )
    except Exception as exc:
        print(f"\n⚠️  LLM invoke failed: {type(exc).__name__}: {exc}")
        return None

    output = response["content"]
    duration_ms = response.get("duration_ms", 0)
    print(f"\nLLM output ({len(output)} chars, {duration_ms}ms):")
    print(output[:400] + ("..." if len(output) > 400 else ""))

    check = ChineseFidelityChecker()
    verdict = check.check(output, expected_language="zh-CN")
    print(f"\n[026 ChineseFidelityChecker verdict]")
    print(f"  is_correct (target lang only): {verdict.is_correct}")
    print(f"  chinese_ratio (CJK / total):    {verdict.chinese_ratio:.3f}")
    print(f"  english_ratio (ASCII / total):  {verdict.english_ratio:.3f}")
    print(f"  score (alias):                  {verdict.score:.3f}")
    if verdict.violation_segments:
        print(f"  ⚠️  violation_segments (English runs): {verdict.violation_segments[:3]}")

    return {
        "label": label,
        "output_preview": output[:200],
        "is_correct": verdict.is_correct,
        "chinese_ratio": round(verdict.chinese_ratio, 3),
        "english_ratio": round(verdict.english_ratio, 3),
        "violation_count": len(verdict.violation_segments),
        "duration_ms": duration_ms,
    }


async def main() -> None:
    client = get_llm_client()

    print("=" * 70)
    print("V2 cycle real-LLM demo: 026 ChineseFidelityChecker")
    print("=" * 70)
    print(f"LLM client: {type(client).__name__}")
    print(f"Model: deepseek-v4-pro (assumed from env)")

    results = []

    # Test 1: Zh-CN summary request — most likely to trigger the regression
    results.append(await run_one(
        client,
        "report-zh-CN",
        system_prompt="你是 InterCraft 面试官。请用中文（zh-CN）给出面试报告的 summary_md 字段。要求全中文输出，禁止英文。",
        user_message="候选人张三，5 题平均分 8.5/10，技术深度强但架构一般。请生成 200 字内的 summary。",
    ))

    # Test 2: Zh-CN score feedback — second-most-likely regression
    results.append(await run_one(
        client,
        "score-zh-CN",
        system_prompt="你是 InterCraft 面试评分员。请用中文（zh-CN）给出逐题反馈。要求全中文，禁止英文出现在 feedback 字段。",
        user_message="题目：解释 React Hooks 原理。候选人回答正确但深度一般。评分 7/10，请给反馈。",
    ))

    # Test 3: Code-mixed OK — English code, Chinese commentary should PASS
    results.append(await run_one(
        client,
        "code-commentary-zh-CN",
        system_prompt="你是 InterCraft 代码评审员。请用中文解释代码，要求中文为主。",
        user_message="这段 TypeScript 代码做了什么：const x: number = await fetch('/api').then(r => r.json());",
    ))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # Verdict
    failed = [r for r in results if not r["is_correct"]]
    print(f"\nVerdict: {len(failed)}/{len(results)} caught fidelity failures")
    if failed:
        print("[!] DeepSeek V4 Pro DID leak English on zh-CN prompt — 026 checker caught it.")
        print("    This is the EXACT regression that prompted 026 Eval Loop.")
    else:
        print("[OK] All zh-CN prompts returned zh-CN outputs this run.")
        print("     (memory caveate says DeepSeek V4 Pro occasionally leaks English —")
        print("      this run did not trigger it, but 026 checker is in place if it does.)")


if __name__ == "__main__":
    asyncio.run(main())
