"""REQ-041 US-2 FR-005 — ``think_tool`` control-flow tool.

Per spec US-2 AS2: ``think_tool(reflection)`` records a free-form reflection as
a :class:`langchain_core.messages.ToolMessage`. The LangChain ``@tool`` wrapper
auto-converts the returned ``ToolMessage`` into a node-bound message that the
LLM agent reads on the next iteration. Reflection text is truncated to 200
characters to bound node-message size (per AC-5.2 boundary conditions).

Signature note: ``tool_call_id`` is injected by the LangChain ``@tool`` runtime
when binding ``tool_call_id`` via the runnable config; we explicitly accept it
as a kwarg so the LangChain StructuredTool picks it up on construction.
"""
from __future__ import annotations

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool


@tool
async def think_tool(
    reflection: str,
    tool_call_id: str = "",  # injected by LangChain @tool runtime via config
) -> ToolMessage:
    """Record a reflection between LLM tool calls so the next iteration sees it.

    Use this between searches to:
    - summarise findings
    - identify gaps in current information
    - plan follow-up queries before issuing them

    Args:
        reflection: free-form text from the LLM (truncated to 200 chars in
            the emitted ToolMessage to bound message length).
        tool_call_id: optional LangChain-injected identifier; when absent, the
            :class:`ToolMessage` is still constructed but ``tool_call_id``
            will be an empty string.

    Returns:
        A :class:`ToolMessage` named ``"think_tool"`` with content
        ``"Reflection recorded: <truncated[:200]>"``. Returning a ToolMessage
        directly (rather than a plain str) lets the LangChain agent attribute
        the message to ``think_tool`` in its message history.
    """
    truncated = reflection[:200]
    return ToolMessage(
        content=f"Reflection recorded: {truncated}",
        tool_call_id=tool_call_id,
        name="think_tool",
    )


__all__ = ["think_tool"]
