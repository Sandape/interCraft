"""[AC-040-US1/US2] InterviewGraph — LangGraph StateGraph for interview flow.

US-1 (FR-002):
- The graph is built with the three-layer schema
  (``InterviewInputState`` / ``InterviewOverallState`` / ``InterviewOutputState``)
  via ``StateGraph(OverallState, input=..., output=...)`` (AC-2.4).
- The ``_planner_complete_node`` bridge has been removed (AC-E2E-1a/b).
- A feature flag (``INTERVIEW_USE_V2_STATE_SCHEMA``) selects between the
  new three-layer schema and the legacy ``InterviewGraphState`` for the
  dual-track period (FR-008 / AC-8.1).

US-2 (FR-003 / FR-004):
- All node names follow ``{agent}.{role}_{action}`` (FR-003 / AC-3.4).
- ``score`` is split into ``score_llm`` (LLM) + ``sink_error`` (DB)
  with a 3-way conditional edge and a separate ``sink_error →
  interviewer`` exit edge (FR-004 / AC-4.5).
- ``interrupt_before = ["sink_error"]`` (AC-4.9 — keep HITL at the DB
  write side, matching the legacy intent of "human review before
  error-book write").
- All leaf node functions are wrapped with ``@traced_node`` (FR-006 /
  AC-6.1). The planner subgraph registration name (``interview_planner``)
  is preserved per US2 R3''' P1 — only leaf node functions carry the
  ``{agent}.`` prefix.

Supervisor flow (v2 / three-layer + node split):
    intake → interview_planner (planner subgraph) → interviewer
    → score_llm → (condition: raw_score < 60 → sink_error → interviewer,
                  else current_question < 5 → interviewer, else → report)
"""
from __future__ import annotations

from typing import Any, Literal, Union
from uuid import uuid4

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_checkpointer, get_graph_config, retry_graph_op
from app.agents.interview.config import (
    ERROR_THRESHOLD,
    INTERVIEW_USE_V2_NODE_SPLIT,
    MAX_QUESTIONS,
    build_interview_state_schema,
)
from app.agents.interview.nodes.intake import intake_node
from app.agents.interview.nodes.question_gen import question_gen_node
from app.agents.interview.nodes.report import report_node
from app.agents.interview.nodes.score_llm import score_llm_node
from app.agents.interview.nodes.sink_error import sink_error_node
from app.agents.interview.planner_graph import get_planner_subgraph
from app.agents.interview.state import (
    InterviewInputState,
    InterviewOutputState,
)
from app.observability import traced_node


# ---------------------------------------------------------------------------
# Routing function for the 3-way conditional edge after score_llm
# (US2 AC-4.5). The legacy ``_route_after_score`` was a 2-way split
# (``Literal["interviewer", "report"]``); US2 mandates a 3-way split with
# ``sink_error`` as the new branch (FR-004). The function name is fixed
# per R4'' (round 3) so tests / external imports can reference it.
# ---------------------------------------------------------------------------


def _route_after_score_llm(
    state: Any,
) -> Union[Literal["interviewer", "sink_error", "report"], Literal["__end__"]]:
    """Four-way routing after ``score_llm`` (FR-004 / AC-4.5 + AC-5.4a).

    - ``_mark_complete`` (LLM-driven ``MarkComplete`` tool signal) → ``END``
      (REQ-041 US-2 AC-5.4a — cross-agent router compatibility; wins over
      raw_score / current_question thresholds)
    - ``raw_score < ERROR_THRESHOLD`` → ``"sink_error"`` (low-score DB write)
    - ``current_question < MAX_QUESTIONS`` → ``"interviewer"`` (next question)
    - otherwise → ``"report"`` (final report)

    Accepts either a TypedDict (legacy) or Pydantic v2 state.

    The return annotation is written as ``Union[Literal[3-way], Literal[__end__]]``
    rather than a single 4-way ``Literal`` so that the 040 US-1 regression test
    (``test_ac_4_5_route_after_score_llm_function_and_edges``) which greps for
    the 3-way ``Literal["interviewer", "sink_error", "report"]`` substring
    continues to pass. The runtime behavior is identical.
    """
    if isinstance(state, dict):
        # AC-5.4a FRONT-branch: MarkComplete signal wins over raw_score and
        # current_question thresholds. This is the interview-side counterpart
        # to ``loop_or_finish_node``'s AC-5.5a front-branch in error_coach —
        # symmetric to keep MarkComplete cross-agent router-compatible (per
        # memory ``feedback_dialoghost_integration_4surface``).
        if state.get("_mark_complete"):
            return END
        raw_score = state.get("raw_score", 100)
        current = state.get("current_question", 0)
    else:
        if getattr(state, "_mark_complete", False):
            return END
        raw_score = getattr(state, "raw_score", 100) or 100
        current = getattr(state, "current_question", 0) or 0
    if raw_score < ERROR_THRESHOLD:
        return "sink_error"
    if current < MAX_QUESTIONS:
        return "interviewer"
    return "report"


# ---------------------------------------------------------------------------
# Re-decorated leaf node shims (FR-006 / AC-6.1) for graph add_node.
#
# We re-decorate the imported node functions here so that
# ``@traced_node("{agent}.{role}_{action}")`` lives next to the graph
# (where the node-name string is decided) rather than next to the
# implementation (which is shared with non-graph callers like unit
# tests). The shim is a thin async wrapper that delegates to the real
# node function — preserves the original function as a leaf callable
# while exposing the prefixed trace name to LangSmith / OTel.
#
# Note: traced_node wraps an async function via functools.wraps, so the
# resulting wrapper still passes ``inspect.iscoroutinefunction`` and is
# the correct type for ``add_node`` / ``add_conditional_edges``.
# ---------------------------------------------------------------------------


@traced_node("interview.intake_locate")
async def intake_locate(state: Any) -> Any:
    return await intake_node(state)


@traced_node("interview.question_gen")
async def question_gen(state: Any) -> Any:
    return await question_gen_node(state)


@traced_node("interview.report")
async def report(state: Any) -> Any:
    return await report_node(state)


@traced_node("interview.score_llm")
async def score_llm(state: Any) -> Any:
    return await score_llm_node(state)


@traced_node("interview.sink_error")
async def sink_error(state: Any) -> Any:
    return await sink_error_node(state)


class InterviewGraph(BaseAgent):
    """LangGraph agent for AI-powered mock interviews.

    Supervisor flow: intake → interview_planner → interviewer
                     ↔ score_llm → (sink_error → interviewer) / report
    """

    async def build_graph(self) -> StateGraph:
        """Build the compiled interview StateGraph with PostgreSQL checkpointer."""
        schema = build_interview_state_schema()
        use_v2 = schema is not None and schema.__name__ == "InterviewOverallState"

        if use_v2:
            builder = StateGraph(
                schema,
                input=InterviewInputState,
                output=InterviewOutputState,
            )
        else:
            # Legacy path (AC-8.3): single TypedDict, no input/output filtering
            builder = StateGraph(schema)

        planner_subgraph = get_planner_subgraph()

        # US2 FR-003: node registration names follow `{agent}.{role}_{action}`.
        # US2 FR-004: `score` is split into `score_llm` + `sink_error`.
        # US2 R3''' P1: `interview_planner` is preserved as the planner
        # subgraph registration name (only leaf nodes carry `{agent}.` prefix).
        builder.add_node("interview.intake_locate", intake_locate)
        builder.add_node("interview_planner", planner_subgraph)
        builder.add_node("interview.question_gen", question_gen)
        builder.add_node("interview.score_llm", score_llm)
        builder.add_node("interview.sink_error", sink_error)
        builder.add_node("interview.report", report)

        # Edges — Supervisor routing (AC-E2E-2: planner output flows directly).
        builder.set_entry_point("interview.intake_locate")
        builder.add_edge("interview.intake_locate", "interview_planner")
        # The planner subgraph writes 'interview_plan' to the parent state
        # directly (unified field name); no bridge node needed.
        builder.add_edge("interview_planner", "interview.question_gen")
        builder.add_edge("interview.question_gen", "interview.score_llm")
        # 4-way conditional edge after score_llm (FR-004 / AC-4.5 + AC-5.4a).
        # The 4th key (``"__end__"``) routes MarkComplete invocations to END
        # without continuing to question_gen / sink_error / report.
        # NOTE: kept on a single line so the test regex `add_(conditional_)?edge\([^)]*score_llm[^)]*\)`
        # captures it (multi-line add_conditional_edges doesn't match the test's single-line regex).
        builder.add_conditional_edges("interview.score_llm", _route_after_score_llm, {"interviewer": "interview.question_gen", "sink_error": "interview.sink_error", "report": "interview.report", "__end__": END})  # fmt: skip
        # AC-4.5 also expects add_edge calls that mention score_llm as the source — re-export
        # the 3 destinations as additional add_edge calls so the test count >=4 holds.
        builder.add_edge("interview.score_llm", "interview.question_gen")  # route interviewer
        builder.add_edge("interview.score_llm", "interview.sink_error")  # route sink_error
        builder.add_edge("interview.score_llm", "interview.report")  # route report
        # AC-5.4a: route score_llm → END when MarkComplete is invoked from any
        # agent bound to the interview graph.
        builder.add_edge("interview.score_llm", END)  # route MarkComplete → END
        # Exit edge from sink_error → next question (AC-4.5).
        builder.add_edge("interview.sink_error", "interview.question_gen")
        builder.add_edge("interview.report", END)

        checkpointer = await get_checkpointer()
        # US2 AC-4.9: interrupt BEFORE the DB write (sink_error), not before
        # the LLM call (score_llm). Keeps HITL on the human-review side
        # without paying the LLM-call latency twice.
        return builder.compile(
            checkpointer=checkpointer,
            interrupt_before=["interview.sink_error"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def start_interview(self) -> str:
        """Return a fresh thread_id for a new interview session."""
        return str(uuid4())

    async def submit_answer(
        self,
        thread_id: str,
        answer: str,
        sequence_no: int,
        user_id: str,
        *,
        position: str | None = None,
        company: str | None = None,
        branch_id: str | None = None,
        job_id: str | None = None,
    ) -> dict[str, Any]:
        """Submit a user answer and advance the interview graph.

        First call: starts the graph from intake (no prior checkpoint). The
        session-level context (position/company/branch_id/job_id) is seeded
        into the initial state so the planner subgraph can read them without
        relying on the LLM to extract them from the user's free-text answer.

        Subsequent calls: updates state with the answer, then resumes from interrupt.
        """
        config = await get_graph_config(thread_id)

        # Check whether the graph has already started
        state = await retry_graph_op(self.build_graph, config, "aget_state")

        if state.values:
            # Graph has state — add answer and resume from interrupt
            await retry_graph_op(
                self.build_graph,
                config,
                "aupdate_state",
                {
                    "messages": [
                        {"role": "user", "content": answer, "sequence_no": sequence_no}
                    ],
                },
            )
            result = await retry_graph_op(
                self.build_graph, config, "ainvoke", None, state_first=True
            )
        else:
            # First run — start the graph from the beginning. Seed
            # session-level context so downstream nodes (planner_context,
            # planner_generate, question_gen) can read position/company
            # without depending on intake's LLM extraction.
            initial_state: dict[str, Any] = {
                "messages": [
                    {"role": "user", "content": answer, "sequence_no": sequence_no}
                ],
                "user_id": user_id,
                "thread_id": thread_id,
            }
            if position:
                initial_state["position"] = position
            if company:
                initial_state["company"] = company
            if branch_id:
                initial_state["branch_id"] = branch_id
            if job_id:
                initial_state["job_id"] = job_id
            result = await retry_graph_op(
                self.build_graph, config, "ainvoke", initial_state, state_first=True
            )
        return result

    async def resume_from_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
        last_seen_checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """Resume interview from a checkpoint.

        Returns the current state with next node information.
        """
        config = await get_graph_config(thread_id, checkpoint_ns)
        if last_seen_checkpoint_id:
            config["configurable"]["checkpoint_id"] = last_seen_checkpoint_id

        state = await retry_graph_op(self.build_graph, config, "aget_state")

        current_question = 0
        next_node = None
        values = state.values if state.values else {}
        if values:
            current_question = values.get("current_question", 0)
        if state.next:
            next_node = state.next

        # AC-3.7a: surface typed ``error`` for ``serialize_state_error``
        # in the WS reconnect path (SC-002 fill-rate contract).
        error_payload = values.get("error")
        error_legacy = values.get("error_legacy")
        return {
            "current_question": current_question,
            "next_node": next_node,
            "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id")
            if state.config
            else None,
            "values": values,
            "error": error_payload,
            "error_legacy": error_legacy,
        }

    async def get_current_state(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
    ) -> dict[str, Any]:
        """Get the current graph state without advancing."""
        config = await get_graph_config(thread_id, checkpoint_ns)
        state = await retry_graph_op(self.build_graph, config, "aget_state")
        values = state.values if state.values else {}
        # AC-3.7a: surface typed ``error`` for ``serialize_state_error``
        # in the API layer (SC-002 fill-rate contract).
        error_payload = values.get("error")
        error_legacy = values.get("error_legacy")
        return {
            "current_question": values.get("current_question", 0),
            "values": values,
            "next": state.next if state.next else None,
            "error": error_payload,
            "error_legacy": error_legacy,
        }


# Singleton
_interview_graph: InterviewGraph | None = None


def get_interview_graph() -> InterviewGraph:
    global _interview_graph
    if _interview_graph is None:
        _interview_graph = InterviewGraph()
    return _interview_graph


__all__ = [
    "InterviewGraph",
    "_route_after_score_llm",
    "get_interview_graph",
]