"""REQ-041 US-2 FR-006 — ToolSpec Pydantic model + extract_tool_spec + SIDE_EFFECT_RULES.

Auto-generated ToolSpec is the canonical contract for any tool registered in
``TOOL_REGISTRY``. The 4 fields (name + schema + side_effects + requires_approval)
are derived from the ``@tool``-decorated function via reflection; side_effects /
requires_approval use the explicit ``SIDE_EFFECT_RULES`` / ``APPROVAL_RULES``
literal maps below (AC-6.3 / AC-6.3a — explicit module-level rule constants).
"""
from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """Tool contract emitted by ``extract_tool_spec``.

    Fields:
        name: function / tool name (matches LangChain StructuredTool.name)
        args_schema: parameter schema dict ``{param_name: annotation_str}``
        side_effects: subset of {"read", "write", "external_api", "ws_push"}
        requires_approval: True when side_effects includes write / ws_push
    """

    model_config = {"protected_namespaces": ()}

    name: str
    args_schema: dict[str, Any] = Field(default_factory=dict)
    side_effects: list[str] = Field(default_factory=list)
    requires_approval: bool = False


# Module-level rule dictionaries (AC-6.3a). Picked up by ``grep`` and reviewer
# without needing to walk the ``extract_tool_spec`` function body.
# Matching strategy: longest-prefix wins; ``MarkComplete`` matches its own rule
# before any ``query_`` / ``tavily`` fallback would (it's a full name match).
SIDE_EFFECT_RULES: dict[str, list[str]] = {
    "tavily": ["read", "external_api"],
    "query_error_question": ["read"],
    "query_resume_blocks": ["read"],
    "query_interview_report": ["read"],
    "think_tool": ["read"],
    "MarkComplete": ["ws_push"],
}


APPROVAL_RULES: dict[str, bool] = {
    "MarkComplete": True,
}


def _rule_for(tool_name: str) -> list[str]:
    """Return the side_effects list for ``tool_name`` by exact match, falling back
    to prefix match for the ``query_*`` family. Returns an empty list if no
    rule matches (the dev then receives a ToolSpec with empty side_effects)."""
    if tool_name in SIDE_EFFECT_RULES:
        return list(SIDE_EFFECT_RULES[tool_name])
    # Prefix match for query_* family / future names following the same pattern.
    if tool_name.startswith("query_"):
        return ["read"]
    if tool_name.startswith("tavily"):
        return ["read", "external_api"]
    return []


def _requires_approval_for(tool_name: str, side_effects: list[str]) -> bool:
    """Derive requires_approval from explicit APPROVAL_RULES first; fall back to
    side-effect heuristics (write / ws_push both imply approval per spec edge case)."""
    if tool_name in APPROVAL_RULES:
        return APPROVAL_RULES[tool_name]
    return bool(set(side_effects) & {"write", "ws_push"})


def extract_tool_spec(tool_func: Any) -> ToolSpec:
    """Reflect a ``@tool``-decorated function into a ``ToolSpec``.

    Accepts either the raw async function (during decoration time) or the
    LangChain ``StructuredTool`` wrapper (after ``from langchain_core.tools
    import tool; @tool`` has been applied). Reflection order:
      1. ``tool_func.args_schema`` (a Pydantic model with the param fields)
      2. ``tool_func.func`` (the underlying raw callable, if present)
      3. ``tool_func`` itself (raw function at decoration time)
    """
    schema: dict[str, Any] = {}

    # (1) LangChain StructuredTool: read Pydantic model fields.
    args_schema = getattr(tool_func, "args_schema", None)
    if args_schema is not None and hasattr(args_schema, "model_fields"):
        for fname, field in args_schema.model_fields.items():
            if fname == "tool_call_id":
                continue
            schema[fname] = str(field.annotation) if field.annotation is not None else "Any"
        name = getattr(tool_func, "name", getattr(args_schema, "__name__", "unknown"))
    else:
        # (2) Raw function: inspect signature.
        raw = getattr(tool_func, "func", tool_func)
        if raw is None:
            raw = tool_func
        try:
            sig = inspect.signature(raw)
            for pname, param in sig.parameters.items():
                if pname == "tool_call_id":
                    continue
                anno = param.annotation
                if anno is inspect.Parameter.empty:
                    schema[pname] = "Any"
                else:
                    schema[pname] = str(anno) if not isinstance(anno, type) else anno.__name__
        except (TypeError, ValueError):
            schema = {}
        name = getattr(tool_func, "name", getattr(raw, "__name__", "unknown"))

    side_effects = _rule_for(name)
    requires_approval = _requires_approval_for(name, side_effects)
    return ToolSpec(
        name=name,
        args_schema=schema,
        side_effects=side_effects,
        requires_approval=requires_approval,
    )


__all__ = [
    "ToolSpec",
    "SIDE_EFFECT_RULES",
    "APPROVAL_RULES",
    "extract_tool_spec",
]
