# ruff: noqa: RUF001
"""Real structured-LLM JD parsing for REQ-059."""
from __future__ import annotations

from typing import Any

from app.agents.state.resume_derive_state import ResumeDeriveState
from app.modules.resume_intelligence.llm import invoke_structured
from app.modules.resume_intelligence.schemas import JobParseOutput

_FIXTURE_SKILLS = (
    "python", "java", "go", "react", "typescript", "llm", "rag", "agent",
    "evals", "eval", "kubernetes", "k8s", "sql", "spark", "pytorch", "tensorflow",
)


async def parse_jd_ai(state: ResumeDeriveState) -> dict[str, Any]:
    jd_text = str(state.get("jd_text") or "").strip()
    if not jd_text:
        raise ValueError("NO_JD")
    result = await invoke_structured(
        user_id=str(state.get("user_id")),
        run_id=str(state.get("run_id")),
        node_name="resume_intelligence_parse_jd",
        contract="job_parse.v1",
        output_model=JobParseOutput,
        system_prompt=(
            "你是岗位要求结构化分析器。提取真实要求、优先级与六类维度。"
            "不要把招聘文案当作候选人事实；要求ID必须稳定、简短。"
        ),
        payload={
            "job": {
                "company": state.get("job_company") or "",
                "position": state.get("job_position") or "",
                "jd_text": jd_text,
            }
        },
    )
    parsed = result.model_dump(mode="json")
    # Compatibility projection for current editor/derive metadata.
    requirements = parsed["requirements"]
    parsed.update(
        {
            "company": state.get("job_company") or "",
            "keywords": [r["text"] for r in requirements if r["category"] == "skills_keywords"],
            "priority_high": [r["text"] for r in requirements if r["priority"] == "hard"],
            "priority_mid": [r["text"] for r in requirements if r["priority"] == "important"],
            "priority_low": [r["text"] for r in requirements if r["priority"] == "nice"],
        }
    )
    return {"jd_parse": parsed, "phase": "map_evidence"}


def parse_jd(state: ResumeDeriveState) -> dict[str, Any]:
    """Legacy deterministic fixture adapter; production uses `parse_jd_ai`."""
    text = str(state.get("jd_text") or "").casefold()
    tokens = sorted({skill for skill in _FIXTURE_SKILLS if skill in text})
    root_blob = str(state.get("root_data") or {}).casefold()
    present = [skill for skill in tokens if skill in root_blob]
    missing = [skill for skill in tokens if skill not in root_blob]
    return {
        "jd_parse": {
            "position": state.get("job_position") or "",
            "company": state.get("job_company") or "",
            "keywords": tokens[:12],
            "priority_high": tokens[:4],
            "priority_mid": tokens[4:8],
            "priority_low": tokens[8:12],
            "evidence_present": present,
            "evidence_missing": missing,
            "requirements": [],
            "jd_quality": 0.0,
            "quality_reasons": ["fixture_adapter_not_real_ai"],
        },
        "phase": "select",
    }
