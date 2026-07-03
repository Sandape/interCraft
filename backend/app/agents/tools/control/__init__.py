"""REQ-041 US-2 FR-005 — Control-flow tools (think_tool + MarkComplete).

These tools let the LLM own flow control inside LangGraph:

- :func:`think_tool` emits a ``ToolMessage`` so the LLM can record a reflection
  in its own message history (used between searches to avoid duplicate work).
- :func:`MarkComplete` signals that the agent believes its current task is
  done; the caller is responsible for setting ``state["_mark_complete"] = True``
  so the conditional edge routers (in :mod:`app.agents.nodes.error_coach.loop_or_finish`
  and :mod:`app.agents.interview.graph`) route to END.
"""
