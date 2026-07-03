"""REQ-041 US1 FR-002 — ``@node_error_handler`` decorator.

Wrap any graph-node function to give it one of three failure strategies
(per AC-2.1 ~ AC-2.9):

- ``"retry"`` (default) — call the node up to ``max_retries`` times
  before re-raising as ``LLMInvokeError``. The first time a token-limit
  error is detected, a single ``retry_with_shorter_prompt`` retry is
  attempted without consuming the ``max_retries`` budget (AC-2.5 /
  AC-1.8 / openDeepResearch pattern).
- ``"use_previous"`` — call the node exactly once. On failure, write
  ``state["error"] = NodeError(...)`` (mandatory — no silent swallow)
  and return ``fallback_value``.
- ``"hard_fail"`` — call the node exactly once. Re-raise the original
  exception unchanged so the graph layer / supervisor can branch on it.

Constraints (per AC matrix):
- AC-2.2a / AC-E2E-US1-1: ``retry_graph_op`` (023 outer graph retry) is
  NOT called from inside this decorator — it's a separate layer at the
  graph-edge level. Tests must ``monkeypatch`` it to identity to keep
  the inner-retry contract observable in isolation.
- AC-2.6: the decorator must be applied line-anchored (``@node_error_handler``
  exactly at column 0) so a future grep audit can enumerate coverage
  unambiguously.
- AC-2.7 / AC-2.8: ``intake_node`` and ``report_node`` MUST be marked
  ``hard_fail`` explicitly per spec clarification (terminal / gateway
  nodes — silent retry would mask the failure).
- AC-3.6 / AC-3.6a: classification imports REQ-038 ``SchemaInvalid``,
  ``ParseFail``, ``Quota``, ``Timeout``, ``OutOfBounds`` and REQ-023
  ``CheckpointerUnavailableError`` rather than redefining the taxonomy.

State contract:
- The decorator writes ``state["error"]`` ONLY under
  ``fallback_strategy == "use_previous"``. ``hard_fail`` re-raises so
  the upstream graph / API layer can observe the original traceback.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Literal, Optional, TypeVar

# 023 — graph checkpointer error taxonomy (re-use, don't redefine)
from app.agents.checkpointer import CheckpointerUnavailableError

# 038 — structured-output exception taxonomy (re-use, don't redefine)
from app.agents.structured_output.errors import (
    OutOfBounds,
    ParseFail,
    Quota,
    SchemaInvalid,
    Timeout,
)

# MB1 — token-limit detection (FR-001)
from app.agents.utils.token_limit import is_token_limit_exceeded

# MB2 sibling — failure envelope written to state["error"]
from app.agents.utils.node_error import NodeError, classify_exception

# LLM client — outer layer raises this on persistent node failure
from app.agents.llm_client import LLMInvokeError


FallbackStrategy = Literal["retry", "use_previous", "hard_fail"]

F = TypeVar("F", bound=Callable[..., Any])

# AC-2.5 R8 — only ONE retry-with-shorter-prompt attempt is allowed before
# the decorator falls back to the normal max_retries budget. This keeps
# the truncation loop bounded: at most max_retries + 1 total node calls
# when the token limit keeps re-occurring.
_MAX_TRUNCATION_ATTEMPTS = 1


def _truncate_state_prompts(state: Any, *, ratio: float = 0.5) -> Any:
    """Halve any in-state prompt-like strings (best-effort heuristic).

    Per AC-2.5, the truncation branch exists to satisfy the openDeepResearch
    ``retry_with_shorter_prompt`` pattern referenced in
    ``backend/app/agents/deep_researcher.py:663-683``. We mutate the
    state in place: any string-valued field longer than 200 chars is
    halved. Numeric fields are left alone (they don't drive token cost
    in a meaningful way for InterCraft's prompt shape).
    """
    if not isinstance(state, dict):
        return state

    def _trunc(v: Any) -> Any:
        if isinstance(v, str) and len(v) > 200:
            return v[: max(1, int(len(v) * ratio))]
        if isinstance(v, list):
            return [_trunc(x) for x in v]
        if isinstance(v, dict):
            return {k: _trunc(x) for k, x in v.items()}
        return v

    for k, v in list(state.items()):
        state[k] = _trunc(v)
    return state


def _model_name_from_state(state: Any) -> str:
    """Best-effort extraction of ``"<provider>:<model>"`` from state.

    Looks for the first key that endswith ``_model_name`` or is literally
    ``"model_name"`` / ``"llm_model_name"``. Returns ``""`` if absent —
    ``is_token_limit_exceeded`` will fail-safe to ``False``.
    """
    if not isinstance(state, dict):
        return ""
    for key in ("_llm_model_name", "llm_model_name", "model_name"):
        if key in state and isinstance(state[key], str):
            return state[key]
    return ""


def node_error_handler(
    fallback_strategy: FallbackStrategy = "retry",
    fallback_value: Any = None,
    max_retries: int = 3,
) -> Callable[[F], F]:
    """Wrap a graph-node function with a configurable failure strategy.

    See module docstring for strategy semantics and constraints.
    """

    def decorator(func: F) -> F:
        if not _is_async_callable(func):
            raise TypeError(
                f"@node_error_handler only supports async callables; "
                f"got {func!r}"
            )

        node_name = getattr(func, "__name__", "node")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            state = args[0] if args else kwargs.get("state")
            attempts = 0
            truncation_attempts = 0
            last_exc: Optional[BaseException] = None

            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:  # noqa: BLE001 — broad catch is intentional
                    last_exc = e

                    # AC-2.4 — hard_fail re-raises immediately, no retry
                    if fallback_strategy == "hard_fail":
                        raise last_exc

                    # AC-2.5: token-limit retry WITHOUT consuming max_retries.
                    # Apply under both ``retry`` and ``use_previous`` strategies
                    # — use_previous's "fallback_value + state.error" semantics
                    # still benefit from one-shot prompt shortening because the
                    # user sees a meaningful error rather than a quota'd one.
                    if (
                        is_token_limit_exceeded(e, _model_name_from_state(state))
                        and truncation_attempts < _MAX_TRUNCATION_ATTEMPTS
                    ):
                        truncation_attempts += 1
                        if isinstance(state, dict):
                            _truncate_state_prompts(state, ratio=0.5)
                        # don't bump attempts; the truncation retry is free
                        continue

                    # retry budget — increment + decide whether to continue
                    attempts += 1
                    if attempts < max_retries:
                        # keep retrying under ``retry`` strategy
                        if fallback_strategy == "retry":
                            continue
                        # use_previous deliberately does NOT retry — write error + return
                        if fallback_strategy == "use_previous":
                            if isinstance(state, dict):
                                state["error"] = NodeError.from_exception(
                                    last_exc,
                                    node_name=node_name,
                                )
                            return fallback_value

                    # retries exhausted — apply fallback strategy
                    if fallback_strategy == "use_previous":
                        # AC-2.3 — write state["error"] and return fallback
                        if isinstance(state, dict):
                            state["error"] = NodeError.from_exception(
                                last_exc,
                                node_name=node_name,
                            )
                        return fallback_value

                    # default retry path — re-raise as LLMInvokeError so graph
                    # layers (retry_graph_op, supervisor) can branch on a
                    # well-known type. This is the AC-2.2a contract.
                    raise LLMInvokeError(
                        f"Node {node_name} failed after {max_retries} retries: {last_exc}"
                    ) from last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


def _is_async_callable(obj: Any) -> bool:
    """True iff ``obj`` is an ``async def`` function or callable wrapping one."""
    import inspect

    if inspect.iscoroutinefunction(obj):
        return True
    # functools.wrapped async functions expose __wrapped__
    wrapped = getattr(obj, "__wrapped__", None)
    return wrapped is not None and inspect.iscoroutinefunction(wrapped)


__all__ = ["node_error_handler", "_MAX_TRUNCATION_ATTEMPTS"]
