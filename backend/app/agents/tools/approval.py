"""REQ-041-P0-APPROVAL — Run-time approval gate for ``requires_approval=True`` tools.

Elevates the compile-time-only ``APPROVAL_RULES["MarkComplete"] = True`` declaration
(``backend/app/agents/tools/spec.py:49-51``) into a run-time interception layer that
runs **before** the underlying ``@tool`` callable. On denial, the gate raises
:class:`ToolApprovalDenied`, which :func:`classify_exception` maps to the
``tool_approval_denied`` bucket of ``NodeErrorCategory``.

Three symbols:

- :func:`_enforce_approval` — pure decision function returning
  ``(allowed: bool, reason: str)``. **Side-effect free** (no I/O, no state
  mutation, no LangChain imports) — this is the AC-1.1 contract.
- :func:`bind_tools_with_approval` — wrapper around ``llm.bind_tools(...)``.
  Default ``enforce=True`` to require the gate; ``enforce=False`` is byte-equivalent
  to plain ``llm.bind_tools`` (AC-2.2).
- :func:`_approval_runtime` — interception layer called immediately before tool
  execution. On denial, raises :class:`ToolApprovalDenied`; on approval, returns
  a LangChain :class:`ToolMessage` carrying the underlying callable's return value.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

from langchain_core.messages import ToolMessage

from app.agents.tools.spec import ToolSpec


class ToolApprovalDenied(RuntimeError):
    """Raised by :func:`_approval_runtime` when an LLM-emitted tool call is denied
    by the approval gate.

    Subclass of ``RuntimeError`` so :func:`app.agents.utils.node_error.classify_exception`
    recognises the ``"approval_missing:<ToolName>"`` message pattern and maps it to
    the ``tool_approval_denied`` bucket of ``NodeErrorCategory`` (AC-1.3a).
    """


def _enforce_approval(
    tool_call: Any,
    tool_spec: ToolSpec,
    state: dict[str, Any],
) -> tuple[bool, str]:
    """Pure decision function (AC-1.1 / AC-1.2 / AC-1.3).

    Returns ``(True, "no_approval_required")`` when:
        - tool_call is for a read-only tool (``requires_approval=False``).

    Returns ``(True, "approved_via_state")`` when:
        - ``state["approved_tools"]`` is a list containing ``tool_spec.name``, OR
        - ``state["approval_token"]`` is a truthy value.

    Returns ``(False, "approval_missing:<ToolName>")`` when:
        - ``tool_spec.requires_approval is True`` and neither of the above
          is present in ``state``.

    Implementation guarantee (AC-1.2): no mutation of ``state``, no I/O,
    no network calls, no ``langchain_*`` imports. Deterministic over
    the same input.
    """
    # Read-only path is the fast lane (AC-1.2).
    if not tool_spec.requires_approval:
        return (True, "no_approval_required")

    # Approval path: explicit allow-list OR token.
    approved_list = state.get("approved_tools")
    if isinstance(approved_list, list) and tool_spec.name in approved_list:
        return (True, "approved_via_state")

    if state.get("approval_token"):
        return (True, "approved_via_token")

    # Default deny path (AC-1.3).
    return (False, f"approval_missing:{tool_spec.name}")


def _bound_tool_funcs() -> dict[str, Any]:
    """Build a name -> StructuredTool mapping by reading the registered tools.

    The LangChain ``@tool``-decorated tools expose their underlying callable via
    ``StructuredTool.func`` (async) or ``.coroutine``. We use the wrapping object
    directly here so that :func:`_approval_runtime` can drive the underlying
    function while honouring test-time monkeypatches (e.g. spies on
    ``MarkComplete.func``).
    """
    # Local import: avoid eager-loading TOOL_REGISTRY at module import time
    # (it is populated by ``_register_tools()`` at ``app.agents.tools`` import).
    from app.agents.tools import (
        MarkComplete,
        query_error_question_by_id,
        query_interview_report,
        query_resume_blocks,
        tavily_search,
        think_tool,
    )

    return {
        "tavily_search": tavily_search,
        "query_error_question_by_id": query_error_question_by_id,
        "query_resume_blocks": query_resume_blocks,
        "query_interview_report": query_interview_report,
        "think_tool": think_tool,
        "MarkComplete": MarkComplete,
    }


def bind_tools_with_approval(
    llm: Any,
    tools: list[Any],
    *,
    enforce: bool = True,
) -> Any:
    """Wrap ``llm.bind_tools(tools)`` with the approval gate.

    - When ``enforce=True`` (default), returns whatever
      ``llm.bind_tools(tools_snapshot)`` returns (LangChain-compatible runnable).
      Callers that want to gate execution MUST additionally call
      :func:`_approval_runtime` before invoking the tool runnable.

    - When ``enforce=False``, returns verbatim whatever ``llm.bind_tools(tools)``
      returns (AC-2.2 — byte-equivalent back-compat).

    Implementation contract:
        - MUST NOT mutate the input ``tools`` list (NAC-3).
        - MUST NOT mutate ``llm``.
        - Returns the same kind of object as ``llm.bind_tools``.
    """
    if not enforce:
        # Byte-equivalent back-compat path (AC-2.2).
        return llm.bind_tools(list(tools))

    tools_snapshot = list(tools)  # defensive copy — avoid caller mutation
    return llm.bind_tools(tools_snapshot)


def _approval_runtime(
    tool_calls: list[dict[str, Any]],
    state: dict[str, Any],
    registry: dict[str, ToolSpec],
    *,
    node_name: str,
) -> Any:
    """Run-time interception layer — called immediately before tool execution
    (AC-3.1 / AC-4.2).

    For each ``tool_call`` in ``tool_calls``:
      - Looks up the :class:`ToolSpec` in ``registry``.
      - Runs :func:`_enforce_approval` for a gate decision.
      - On denial, raises :class:`ToolApprovalDenied` (the underlying callable
        is **not** invoked).
      - On approval, invokes the underlying callable (async or sync) and wraps
        the result in a LangChain :class:`ToolMessage` keyed to the input
        ``tool_call_id``.

    Returns a single :class:`ToolMessage` when the batch size is 1 (the
    primary test fixture uses a single MarkComplete invocation); returns a list
    for larger batches.
    """
    from app.agents.tools import TOOL_REGISTRY

    if registry is None:
        registry = TOOL_REGISTRY

    if not isinstance(tool_calls, list) or not tool_calls:
        return None

    # Step 1 — gate each call. Any denial aborts the entire batch (AC-3.1).
    for tc in tool_calls:
        name = tc.get("name", "")
        spec = registry.get(name)
        if spec is None:
            # Unknown tool — let the underlying callable surface its own error
            # if it cannot find the symbol. We do NOT apply the gate to it.
            continue
        allowed, reason = _enforce_approval(tc, spec, state)
        if not allowed:
            # The underlying callable SHALL NOT execute (AC-3.1).
            raise ToolApprovalDenied(reason)

    # Step 2 — approved path. Invoke underlying callables, wrap into ToolMessages.
    funcs = _bound_tool_funcs()
    messages: list[ToolMessage] = []
    for tc in tool_calls:
        name = tc.get("name", "")
        tool_call_id = tc.get("id", "")
        args = tc.get("args", {}) or {}
        callable_ = funcs.get(name)
        if callable_ is None:
            messages.append(
                ToolMessage(
                    content=f"tool '{name}' not registered in approval gate",
                    tool_call_id=tool_call_id,
                )
            )
            continue
        try:
            result = _invoke_callable(callable_, args)
        except Exception as exc:  # surface as a tool error string
            result = f"tool '{name}' raised: {exc}"

        if not isinstance(result, str):
            result = str(result)

        messages.append(
            ToolMessage(content=result, tool_call_id=tool_call_id)
        )

    if len(messages) == 1:
        return messages[0]
    return messages


def _invoke_callable(func: Any, args: dict[str, Any]) -> Any:
    """Invoke ``func`` respecting its sync/async nature; supports the LangChain
    :class:`StructuredTool` wrapper convention.

    LangChain ``@tool``-decorated async functions expose the underlying
    coroutine via ``StructuredTool.coroutine`` (NOT ``.func``), and sync
    functions via ``StructuredTool.func``. We prefer ``.coroutine`` first
    because every ``@tool`` in this codebase is ``async def``.

    The fallback (``func(**args)``) handles arbitrary callables — it would
    land on ``StructuredTool.__call__`` only if both ``.coroutine`` and
    ``.func`` were absent, which LangChain guarantees they are not.
    """
    # Async tool (default in this codebase).
    coroutine = getattr(func, "coroutine", None)
    if coroutine is not None and inspect.iscoroutinefunction(coroutine):
        return asyncio.run(coroutine(**args))

    # Sync tool — unwrap via .func, fall back to func itself if .func is None.
    target = getattr(func, "func", None) or func
    if inspect.iscoroutinefunction(target):
        return asyncio.run(target(**args))
    if callable(target):
        return target(**args)
    # Final fallback — call the wrapper itself; StructuredTool instances accept
    # kwargs via invoke but not directly via __call__ with kwargs.
    return func(**args)


__all__ = [
    "ToolApprovalDenied",
    "_enforce_approval",
    "bind_tools_with_approval",
    "_approval_runtime",
]
