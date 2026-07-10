"""parse_jd node — structured JD parse (heuristic + optional LLM later)."""
from __future__ import annotations

import re
from typing import Any

from app.agents.state.resume_derive_state import ResumeDeriveState


_SKILL_HINTS = (
    "python",
    "java",
    "go",
    "react",
    "typescript",
    "llm",
    "rag",
    "agent",
    "evals",
    "eval",
    "kubernetes",
    "k8s",
    "sql",
    "spark",
    "pytorch",
    "tensorflow",
)


def parse_jd(state: ResumeDeriveState) -> dict[str, Any]:
    text = (state.get("jd_text") or "").lower()
    keywords = sorted({h for h in _SKILL_HINTS if h in text})
    # Also pull Capitalized tokens / CN phrases roughly
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{1,24}", state.get("jd_text") or "")
    for t in raw_tokens:
        if t.lower() in _SKILL_HINTS:
            keywords.append(t.lower())
    keywords = sorted(set(keywords))

    high = keywords[: max(1, len(keywords) // 2)] if keywords else []
    mid = keywords[len(high) :] if keywords else []

    root_data = state.get("root_data") or {}
    root_blob = str(root_data).lower()
    present = [k for k in keywords if k in root_blob]
    missing = [k for k in keywords if k not in root_blob]

    jd_parse = {
        "position": state.get("job_position"),
        "company": state.get("job_company"),
        "keywords": keywords,
        "ats_keywords": keywords,
        "priority_high": high,
        "priority_mid": mid,
        "priority_low": [],
        "evidence_present": present,
        "evidence_missing": missing,
        "core_duties": [],
        "hard_skills": high,
        "nice_to_haves": mid,
    }
    return {"jd_parse": jd_parse, "phase": "select"}
