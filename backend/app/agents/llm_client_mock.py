"""021: MockLLMClient for deterministic E2E testing.

Activated by LLM_MOCK_MODE=1 env var. Reads a scenario JSON file describing
the score sequence for evaluate nodes and static hint content for hint nodes.
Skips quota deduction and ai_messages writes (no DB pollution).

Scenario JSON format:
{
  "evaluate_scores": [8, 9, 9],
  "hint_contents": {
    "small": "小提示文案",
    "medium": "中等提示文案",
    "detailed": "详细提示文案"
  }
}
"""
from __future__ import annotations

import json
import structlog
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agents.llm_client import LLMClient, LLMResponse

logger = structlog.get_logger("agents.llm_client_mock")

_DEFAULT_SCORES: list[int] = [5]
_DEFAULT_HINTS: dict[str, str] = {"small": "", "medium": "", "detailed": ""}


# Schema-aware fixture strings used by by_scenario().
# Adding a new scenario: drop it here AND in tests/fixtures/structured_output/.
_SCENARIO_FIXTURES: dict[str, str] = {
    "malformed": "{ next_question: ... }",            # truncated brace
    "missing": "{}",                                   # empty object
    "enum_violation": '{"severity": "extreme"}',       # not in {low,medium,high}
    "oob": '{"score": 200, "feedback": "too high"}',  # > Field(le=100)
    "quota": '{"_kind": "quota_429"}',                 # HTTP 429 trigger
    "timeout": '{"_kind": "timeout_504"}',             # HTTP 504 trigger
}


class MockLLMClient(LLMClient):
    """Deterministic mock LLM client for E2E tests.

    Subclasses LLMClient so the production `parse_structured_output`
    (Pydantic validator) is reachable from the mock path (ac-matrix
    AC-009: mock and prod share the validator).
    """

    def __init__(
        self,
        evaluate_scores: list[int] | None = None,
        hint_contents: dict[str, str] | None = None,
    ) -> None:
        self.evaluate_scores: list[int] = list(evaluate_scores or _DEFAULT_SCORES)
        self.hint_contents: dict[str, str] = dict(hint_contents or _DEFAULT_HINTS)
        self._evaluate_index: int = 0

    @classmethod
    def from_scenario_file(cls, path: str) -> "MockLLMClient":
        """Load scenario from a JSON file path. Falls back to defaults on error."""
        if not path:
            logger.warning("llm.mock_scenario_missing", path=path)
            return cls()
        p = Path(path)
        if not p.exists():
            logger.warning("llm.mock_scenario_not_found", path=path)
            return cls()
        try:
            data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
            return cls(
                evaluate_scores=data.get("evaluate_scores"),
                hint_contents=data.get("hint_contents"),
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("llm.mock_scenario_parse_error", path=path, error=str(exc))
            return cls()

    async def invoke(
        self,
        *,
        messages: list[dict[str, str]],
        estimated_tokens: int | None = None,
        user_id: str,
        thread_id: str,
        node_name: str,
        checkpoint_id: str | None = None,
        max_retries: int = 3,
        timeout_ms: int = 30_000,
        stream: bool = False,
    ) -> LLMResponse:
        """Return a deterministic response based on node_name."""
        content = self._content_for(node_name, messages)
        logger.info(
            "llm.mock_invoke",
            user_id=user_id,
            thread_id=thread_id,
            node_name=node_name,
        )
        return LLMResponse(
            content=content,
            model="mock-llm",
            prompt_tokens=0,
            completion_tokens=0,
            duration_ms=0,
            checkpoint_id=checkpoint_id,
        )

    async def invoke_stream(self, **kwargs):  # pragma: no cover - unused in Error Coach
        yield ""

    # ------------------------------------------------------------------
    # REQ-038 US1 P1 — structured-output parity (ac-matrix AC-009).
    # Mock subclasses LLMClient and routes parse_structured_output
    # through the production Pydantic path so mock and prod share the
    # same validator. Mock cannot silently bypass validation.
    # ------------------------------------------------------------------
    def parse_structured_output(
        self,
        content: str,
        schema: type[BaseModel],
        *,
        fallback_strategy: str = "retry",
        node_name: str | None = None,
    ) -> BaseModel:
        """Reuse the production parse path (ac-matrix AC-009)."""
        return LLMClient.parse_structured_output(
            self,
            content,
            schema,
            fallback_strategy=fallback_strategy,
            node_name=node_name,
        )

    def by_scenario(self, name: str, schema: type[BaseModel] | None = None) -> str:
        """Return a fixture content string for a named scenario.

        Raises ``KeyError`` with the full list of available scenarios so
        callers can never silently fall back to an unrelated fixture
        (ac-matrix Note R11 / AC-009 side-constraint).
        """
        if name not in _SCENARIO_FIXTURES:
            raise KeyError(
                f"Unknown scenario '{name}'. "
                f"Available scenarios: {', '.join(_SCENARIO_FIXTURES)}"
            )
        return _SCENARIO_FIXTURES[name]

    def _content_for(self, node_name: str, messages: list[dict[str, str]]) -> str:
        if node_name == "error_coach_evaluate":
            if self._evaluate_index < len(self.evaluate_scores):
                score = self.evaluate_scores[self._evaluate_index]
                self._evaluate_index += 1
            else:
                score = 5
            return json.dumps({"score": score, "feedback": "mock"}, ensure_ascii=False)
        if node_name == "error_coach_hint":
            level = self._extract_hint_level(messages)
            return self.hint_contents.get(level, self.hint_contents.get("small", ""))
        return ""

    @staticmethod
    def _extract_hint_level(messages: list[dict[str, str]]) -> str:
        """Parse the hint level from the hint_ladder prompt.

        The real hint_ladder node formats the prompt with "Hint level: <level>"
        (see backend/app/agents/prompts/error_coach/hint_ladder.md). We scan the
        last user message for that pattern. Falls back to "small" if not found.
        """
        for msg in reversed(messages):
            content = msg.get("content", "")
            for level in ("detailed", "medium", "small"):
                if f"Hint level: {level}" in content or f"current_hint_level={level}" in content:
                    return level
        return "small"


__all__ = ["MockLLMClient"]
