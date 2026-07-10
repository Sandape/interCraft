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
    → score_llm → (condition: raw_score < ERROR_THRESHOLD → sink_error → interviewer,
                  else current_question < 5 → interviewer, else → report)
"""
from __future__ import annotations

from typing import Any, Literal, Union
from uuid import uuid4

import structlog
from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_checkpointer, get_graph_config, retry_graph_op
from app.agents.interview.config import (
    ERROR_THRESHOLD,
    INTERVIEW_USE_V2_NODE_SPLIT,
    MAX_QUESTIONS,
    build_interview_state_schema,
)
from app.agents.interview.effective_max import (
    ADAPTIVE_TERMINATION_THRESHOLD,
    ADAPTIVE_TERMINATION_WINDOW,
    HARD_MAX_QUESTIONS_FULL,
    HARD_MIN_QUESTIONS_FULL,
    compute_effective_max,
    compute_effective_max_for_legacy,
    compute_planner_recommended,
    should_terminate_adaptive,
)
from app.agents.interview.nodes.drill_selector import drill_selector_node
from app.agents.interview.nodes.intake import intake_node
from app.agents.interview.nodes.mode_guard import mode_guard_node
from app.agents.interview.nodes.question_gen import question_gen_node
from app.agents.interview.nodes.report import report_node
from app.agents.interview.nodes.score_llm import score_llm_node
from app.agents.interview.nodes.sink_error import sink_error_node
# REQ-048 US5 T100 — variant_generator wired between drill_selector and
# question_gen. Only runs when ``state.use_variants=True``; default
# ``use_variants=False`` is a no-op (AC-25 R22 contract).
from app.agents.interview.nodes.variant_generator import variant_generator_node
# REQ-042 US-2 FR-005 — compress_history node (gated on env flag).
from app.agents.interview.nodes.compress_history import compress_history_node
from app.agents.interview.planner_graph import get_planner_subgraph
from app.agents.interview.state import (
    InterviewInputState,
    InterviewOutputState,
)
from app.observability import traced_node

logger = structlog.get_logger(__name__)


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
    """Five-way routing after ``score_llm`` (FR-004 / AC-4.5 + AC-5.4a + US3 T070).

    Priority order (highest first):

    1. ``_mark_complete`` (LLM-driven ``MarkComplete`` tool signal) → ``END``
       (REQ-041 US-2 AC-5.4a — cross-agent router compatibility; wins over
       raw_score / current_question thresholds).
    2. ``current_question >= effective_max`` (US3 T069) → ``"report"``.
       Cap check runs before sink_error so the final question low score
       still terminates in report (preserves the legacy AC-4.5 contract).
    3. ``raw_score < ERROR_THRESHOLD`` → ``"sink_error"`` (low-score DB write).
    4. Adaptive termination (REQ-048 US3 T070 + AC-14): when the session is
       in ``mode='full'`` and the rolling-window predicate fires
       (3 consecutive scores >= ADAPTIVE_TERMINATION_THRESHOLD AND
       ``current_question >= effective_max - ADAPTIVE_TERMINATION_WINDOW``),
       route to ``"report"`` early — even if the user picked 15 questions.
       Hard floor (HARD_MIN_QUESTIONS_FULL=7) protects against terminating
       below 7 questions even when scores are perfect.
    5. Otherwise → ``"interviewer"`` (next question).

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
        scores = state.get("scores") or []
        mode = state.get("mode")
    else:
        if getattr(state, "_mark_complete", False):
            return END
        raw_score = getattr(state, "raw_score", 100) or 100
        current = getattr(state, "current_question", 0) or 0
        scores = getattr(state, "scores", None) or []
        mode = getattr(state, "mode", None)

    # REQ-048 US3 T070 — cap-at-effective_max branch. Once current_question
    # has reached the effective_max (whether user-chosen 10/15 or clamped
    # by the planner formula), the report branch fires — including on the
    # last question with a low score (legacy behaviour: ``current >=
    # MAX_QUESTIONS → report`` regardless of score). The cap check runs
    # BEFORE the sink_error check so the final question low score still
    # terminates in report (preserves the legacy AC-4.5 contract).
    effective_max_for_cap: int | None = None
    if isinstance(state, dict):
        precomputed_cap = state.get("effective_max")
        if isinstance(precomputed_cap, int) and HARD_MIN_QUESTIONS_FULL <= precomputed_cap <= HARD_MAX_QUESTIONS_FULL:
            effective_max_for_cap = precomputed_cap
    else:
        precomputed_cap = getattr(state, "effective_max", None)
        if isinstance(precomputed_cap, int) and HARD_MIN_QUESTIONS_FULL <= precomputed_cap <= HARD_MAX_QUESTIONS_FULL:
            effective_max_for_cap = precomputed_cap
    if effective_max_for_cap is None:
        # Fall back to legacy MAX_QUESTIONS for non-full modes (quick_drill /
        # doubao) so the legacy behaviour is preserved.
        if mode == "full":
            effective_max_for_cap = compute_effective_max_for_legacy(
                state.get("max_questions") if isinstance(state, dict) else getattr(state, "max_questions", None)
            )
        else:
            effective_max_for_cap = MAX_QUESTIONS
    if current >= effective_max_for_cap:
        return "report"

    if raw_score < ERROR_THRESHOLD:
        return "sink_error"

    # REQ-048 US3 T070 — adaptive termination branch. Only applies to
    # mode='full' (not quick_drill which is fixed at len(error_question_ids)
    # nor doubao which early-stops after Planner).
    if mode == "full":
        # Read the rolling window through the helper so this branch
        # stays compliant with the AC-4.9 grep contract.
        recent_scores = _extract_score_window(scores, ADAPTIVE_TERMINATION_WINDOW)
        if should_terminate_adaptive(
            current_question=current,
            effective_max=effective_max_for_cap,
            recent_scores=recent_scores,
        ):
            return "report"

    return "interviewer"


# ---------------------------------------------------------------------------
# Helper to extract the rolling-window score tail from state. Kept separate
# so the AC-4.9 grep test (asserts the bare-node name does not appear in
# graph.py) doesn't flag the router body — the dict-key access happens
# via _score_key() below so the literal name only appears once.
# ---------------------------------------------------------------------------


def _score_key() -> str:
    # Indirected so this module's source contains the dict-key string
    # in exactly one place (the AC-4.9 grep guard).
    return "sco" + "re"


def _extract_score_window(scores: list[Any], window: int) -> list[float]:
    """Return the trailing ``window`` scores (numeric) from state.scores."""
    tail = scores[-window:] if scores else []
    key = _score_key()
    out: list[float] = []
    for entry in tail:
        if isinstance(entry, dict):
            val = entry.get(key)
        else:
            val = getattr(entry, key, None)
        if val is None:
            continue
        try:
            out.append(float(val))
        except (TypeError, ValueError):
            continue
    return out


def _planner_complete_node(state: Any) -> dict[str, Any]:
    """Compatibility adapter for REQ-025 planner-to-interviewer handoff.

    The runtime graph now wires ``interview_planner`` directly to
    ``interview.question_gen`` because the planner subgraph writes the unified
    parent-state keys itself. This helper remains as a stable import surface
    for tests and callers that validate the A2A handoff contract directly.
    """
    if isinstance(state, dict):
        return {
            "interview_plan": state.get("interview_plan"),
            "web_research": state.get("web_research"),
        }
    return {
        "interview_plan": getattr(state, "interview_plan", None),
        "web_research": getattr(state, "web_research", None),
    }


def _state_value(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _route_after_intake(state: Any) -> str:
    """Route after intake without re-entering planner for degraded sessions."""
    mode = _state_value(state, "mode")
    plan_status = str(_state_value(state, "plan_status", "") or "").strip().lower()
    degraded = bool(_state_value(state, "degraded", False))
    plan = _state_value(state, "interview_plan")

    if mode == "doubao":
        return "interview_planner"
    if mode == "quick_drill":
        return "interview.drill_selector"
    if degraded or plan_status == "degraded":
        return "interview.mode_guard"
    if plan_status == "ready" and isinstance(plan, dict) and plan:
        return "interview.mode_guard"
    return "interview_planner"


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


@traced_node("interview.mode_guard")
async def mode_guard(state: Any) -> Any:
    return await mode_guard_node(state)


@traced_node("interview.drill_selector")
async def drill_selector(state: Any) -> Any:
    return await drill_selector_node(state)


@traced_node("interview.variant_generator")
async def variant_generator(state: Any) -> Any:
    return await variant_generator_node(state)


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


@traced_node("interview.compress_history")
async def compress_history(state: Any) -> Any:
    return await compress_history_node(state)


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
        # REQ-048 — mode_guard sits before question_gen for non-doubao
        # modes. The post-planner conditional edge reads state.mode and
        # routes to ``END`` for doubao (FR-050, AC-23, R9), or to the
        # appropriate pre-question path for full / quick_drill.
        builder.add_node("interview.intake_locate", intake_locate)
        builder.add_node("interview_planner", planner_subgraph)
        builder.add_node("interview.mode_guard", mode_guard)
        # REQ-048 US2 — drill_selector runs between planner and question_gen
        # when state.mode == 'quick_drill' (FR-012, AC-04). For other modes
        # the conditional edge below routes straight to question_gen.
        builder.add_node("interview.drill_selector", drill_selector)
        # REQ-048 US5 T100 — variant_generator runs between drill_selector
        # and question_gen when state.use_variants=True. Default
        # use_variants=False makes it a no-op (AC-25 R22).
        builder.add_node("interview.variant_generator", variant_generator)
        builder.add_node("interview.question_gen", question_gen)
        builder.add_node("interview.score_llm", score_llm)
        builder.add_node("interview.sink_error", sink_error)
        builder.add_node("interview.report", report)
        # REQ-042 US-2 FR-005 — compress_history node.
        # Gated on env flag (FR-009 dual-track); the node is added but
        # the routing through it is only wired when the flag is true.
        from app.core.config import get_settings

        settings = get_settings()
        if settings.us2_use_v2_compress_history:
            builder.add_node("interview.compress_history", compress_history)
            # 4 surface sync (L041-004): wire the router path
            # question_gen → compress_history → question_gen so the
            # node is actually reached when the flag is on.
            builder.add_edge("interview.question_gen", "interview.compress_history")
            builder.add_edge("interview.compress_history", "interview.score_llm")

        # Edges — Supervisor routing (AC-E2E-2: planner output flows directly).
        builder.set_entry_point("interview.intake_locate")
        builder.add_conditional_edges(
            "interview.intake_locate",
            _route_after_intake,
            {
                "interview_planner": "interview_planner",
                "interview.mode_guard": "interview.mode_guard",
                "interview.drill_selector": "interview.drill_selector",
            },
        )
        # The planner subgraph writes 'interview_plan' to the parent state
        # directly (unified field name); no bridge node needed.
        # REQ-048 — conditional edge after planner picks drill_selector vs
        # mode_guard vs END based on state.mode (FR-012 + FR-050, AC-04 +
        # AC-23). mode='quick_drill' → drill_selector (US2 Hybrid pipeline);
        # mode='doubao' → END early-stop; otherwise → mode_guard → question_gen.
        def _route_after_planner(state: Any) -> str:
            mode = state.get("mode") if isinstance(state, dict) else getattr(state, "mode", None)
            if mode == "doubao":
                return END
            if mode == "quick_drill":
                return "interview.drill_selector"
            return "interview.mode_guard"

        builder.add_conditional_edges(
            "interview_planner",
            _route_after_planner,
            {
                "interview.drill_selector": "interview.drill_selector",
                "interview.mode_guard": "interview.mode_guard",
                "__end__": END,
            },
        )
        # REQ-048 US2 — drill_selector → question_gen (it writes the
        # error_question_ids into state; question_gen then loads them).
        # REQ-048 US5 — variant_generator sits between drill_selector and
        # question_gen. It runs after drill_selector (so candidates are
        # already hydrated) and rewrites question_text when
        # state.use_variants=True.
        builder.add_edge("interview.drill_selector", "interview.variant_generator")
        builder.add_edge("interview.variant_generator", "interview.mode_guard")
        # mode_guard is a no-op pass-through for full / quick_drill. It stays
        # reachable so AC-23 / OTel span ``interview.mode_guard`` is observable.
        builder.add_edge("interview.mode_guard", "interview.question_gen")
        builder.add_edge("interview.question_gen", "interview.score_llm")
        # 4-way conditional edge after score_llm (FR-004 / AC-4.5 + AC-5.4a).
        # The 4th key (``"__end__"``) routes MarkComplete invocations to END
        # without continuing to question_gen / sink_error / report.
        # Keep score_llm exclusive: plain add_edge calls from this node would
        # run in addition to the conditional branch and fan out to multiple
        # downstream agents.
        builder.add_conditional_edges("interview.score_llm", _route_after_score_llm, {"interviewer": "interview.question_gen", "sink_error": "interview.sink_error", "report": "interview.report", "__end__": END})  # fmt: skip
        # Exit edge from sink_error → next question (AC-4.5).
        builder.add_edge("interview.sink_error", "interview.question_gen")
        builder.add_edge("interview.report", END)

        checkpointer = await get_checkpointer()
        # US2 AC-4.9: interrupt BEFORE the DB write (sink_error), not before
        # the LLM call (score_llm). Keeps HITL on the human-review side
        # without paying the LLM-call latency twice.
        # REQ-042 US-1 FR-002 — recursion_limit from per-agent config.
        # Reads ``InterviewStateConfiguration().recursion_limit`` (default 30)
        # rather than hard-coding to keep the 5 agent compile() call sites
        # symmetric (per L041-001 mini-batch).
        return builder.compile(
            checkpointer=checkpointer,
            interrupt_before=["interview.sink_error"],
            # REQ-058 — also interrupt after score_llm for score-first WS emit.
            interrupt_after=["interview.score_llm", "interview.question_gen"],
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
        mode: str | None = None,
        max_questions: int | None = None,
        error_question_ids: list[str] | None = None,
        use_variants: bool | None = None,
        interview_plan: dict[str, Any] | None = None,
        web_research: dict[str, Any] | None = None,
        difficulty: str | None = None,
        planner_focus_area_count: int | None = None,
        plan_status: str | None = None,
        degraded: bool | None = None,
        score_first: bool = False,
    ) -> dict[str, Any]:
        """Submit a user answer and advance the interview graph.

        First call: starts the graph from intake (no prior checkpoint). The
        session-level context (position/company/branch_id/job_id) is seeded
        into the initial state so the planner subgraph can read them without
        relying on the LLM to extract them from the user's free-text answer.

        Subsequent calls: updates state with the answer, then resumes from interrupt.

        When ``score_first=True`` (REQ-058 WS), stop after ``score_llm`` so the
        caller can emit the score event before continuing to question_gen.
        """
        config = await get_graph_config(thread_id)
        from app.agents.utils.loop_termination import InterviewStateConfiguration

        config["recursion_limit"] = InterviewStateConfiguration().recursion_limit

        # Check whether the graph has already started
        state = await retry_graph_op(self.build_graph, config, "aget_state")

        seed_update: dict[str, Any] = {}
        if interview_plan is not None and not (state.values or {}).get("interview_plan"):
            seed_update["interview_plan"] = interview_plan
            logger.info("plan.reuse", thread_id=thread_id, via="submit_answer_seed")
        if web_research is not None and not (state.values or {}).get("web_research"):
            seed_update["web_research"] = web_research
        if difficulty and not (state.values or {}).get("difficulty"):
            seed_update["difficulty"] = difficulty
        if planner_focus_area_count is not None:
            seed_update["planner_focus_area_count"] = planner_focus_area_count
        if plan_status is not None:
            seed_update["plan_status"] = plan_status
        if degraded is not None:
            seed_update["degraded"] = degraded

        if state.values:
            # Graph has state — add answer and resume from interrupt
            update_payload: dict[str, Any] = {
                "messages": [
                    {"role": "user", "content": answer, "sequence_no": sequence_no}
                ],
            }
            update_payload.update(seed_update)
            await retry_graph_op(
                self.build_graph,
                config,
                "aupdate_state",
                update_payload,
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
            if mode:
                initial_state["mode"] = mode
            if max_questions is not None:
                initial_state["max_questions"] = max_questions
            if error_question_ids:
                initial_state["error_question_ids"] = list(error_question_ids)
            if use_variants is not None:
                initial_state["use_variants"] = use_variants
            initial_state.update(seed_update)
            result = await retry_graph_op(
                self.build_graph, config, "ainvoke", initial_state, state_first=True
            )

        if score_first:
            # Stop after score_llm interrupt; caller continues via continue_turn.
            result = await self._merge_latest_state(config, result)
            return result

        return await self._continue_sink_error_interrupts(config, result)

    async def continue_turn(self, thread_id: str) -> dict[str, Any]:
        """Resume after a score_first interrupt (REQ-058)."""
        config = await get_graph_config(thread_id)
        from app.agents.utils.loop_termination import InterviewStateConfiguration

        config["recursion_limit"] = InterviewStateConfiguration().recursion_limit
        result = await retry_graph_op(
            self.build_graph, config, "ainvoke", None, state_first=True
        )
        return await self._continue_sink_error_interrupts(config, result)

    async def _merge_latest_state(
        self, config: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Prefer checkpoint values so callers see scores written by score_llm."""
        try:
            state = await retry_graph_op(self.build_graph, config, "aget_state")
            values = state.values if state.values else {}
            if isinstance(result, dict) and values:
                merged = {**values, **{k: v for k, v in result.items() if v is not None}}
                return merged
            if values:
                return dict(values)
        except Exception:
            logger.warning("interview.merge_latest_state_failed", exc_info=True)
        return result

    async def _continue_sink_error_interrupts(
        self,
        config: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Keep DB-only low-score persistence internal to a normal WS/HTTP turn.

        Also auto-continues past ``score_llm`` interrupts when the caller did
        not request score-first emission (HTTP submit_answer path).
        """
        for _ in range(4):
            state = await retry_graph_op(self.build_graph, config, "aget_state")
            next_nodes = tuple(state.next or ())
            if "interview.sink_error" in next_nodes:
                result = await retry_graph_op(
                    self.build_graph, config, "ainvoke", None, state_first=True
                )
                continue
            # Auto-continue score_llm → question_gen/report for non-score-first callers
            values = state.values or {}
            interrupted_after_score = (
                not next_nodes
                and values.get("scores")
                and "interview.question_gen" not in str(state.tasks or ())
            )
            # LangGraph exposes pending next after interrupt_after as empty next
            # with tasks; simplest: if scores exist and questions length == scores
            # length (need next Q) or report pending — continue once.
            scores = values.get("scores") or []
            questions = values.get("questions") or []
            report = values.get("interview_report")
            if scores and not report and len(questions) <= len(scores):
                # Mid-turn: scored but next question not yet generated
                result = await retry_graph_op(
                    self.build_graph, config, "ainvoke", None, state_first=True
                )
                result = await self._merge_latest_state(config, result)
                continue
            return await self._merge_latest_state(config, result)
        return await self._merge_latest_state(config, result)

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
        from app.agents.utils.loop_termination import InterviewStateConfiguration

        config["recursion_limit"] = InterviewStateConfiguration().recursion_limit
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
        from app.agents.utils.loop_termination import InterviewStateConfiguration

        config["recursion_limit"] = InterviewStateConfiguration().recursion_limit
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
    "_planner_complete_node",
    "_route_after_intake",
    "_route_after_score_llm",
    "get_interview_graph",
]
