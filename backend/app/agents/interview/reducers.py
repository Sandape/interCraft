"""[AC-040-US1] FR-001 — LangGraph state reducers for Interview agent.

Provides ``override_reducer``, a custom reducer that supports an explicit
``{"type": "override", "value": X}`` protocol for fully replacing a list field
without appending. This complements (and does not replace) the built-in
``add_messages`` reducer from ``langgraph.graph.message``.

Protocol
--------
A node that wants to *replace* (not append) a list field can return the
following shape from its dict delta:

```python
return {"scores": {"type": "override", "value": []}}   # full reset
return {"scores": {"type": "override", "value": [new]}}  # full replace
```

The reducer is invoked by LangGraph with ``(existing_value, new_value)``;
when ``new_value`` is a dict with ``type == "override"``, the reducer
returns ``new_value["value"]`` and discards ``existing_value``.

Any other ``new_value`` shape falls through to the default LangGraph behavior
(return the new value), preserving compatibility with the standard
"last-write-wins" semantics.

Usage
-----
In a TypedDict state:

```python
from typing import Annotated
from typing_extensions import TypedDict
from app.agents.interview.reducers import override_reducer


class MyState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    scores: Annotated[list, override_reducer]
```

Node function:

```python
async def score_node(state: MyState) -> dict:
    return {"scores": {"type": "override", "value": []}}  # reset
```
"""
from __future__ import annotations

from typing import Any


def override_reducer(a: Any, b: Any) -> Any:
    """Reducer that supports the ``{"type": "override", "value": X}`` protocol.

    Both call sites are supported:
    - **langgraph integration**: called as ``reducer(existing, new)``. The
      override dict arrives in the second positional argument.
    - **direct test invocation**: called as ``override_reducer(override, existing)``
      per the AC contract; the override dict arrives in the first argument.

    The reducer inspects **both** arguments for the protocol shape; the
    first match wins. If neither is an override dict, ``b`` is returned
    (LangGraph's "new wins" default behavior).

    Protocol example (code block, see R6' Phase 2 reviewer 校验):

    ```
    {"type": "override", "value": []}
    ```

    Parameters
    ----------
    a, b:
        The two values passed by LangGraph (or by a direct test call).
        Whichever one matches the protocol is the source of the new value.

    Returns
    -------
    Any
        The resolved value to be stored in the state field. For the
        override protocol, this is the new ``value``; otherwise it is
        ``b`` (last-write-wins, matching langgraph's default).

    Examples
    --------
    Replace semantics — langgraph integration (``existing, new`` order)::

        >>> override_reducer([3, 4], {"type": "override", "value": [1, 2]})
        [1, 2]

    Replace semantics — direct test call (``new, existing`` order)::

        >>> override_reducer({"type": "override", "value": [1, 2]}, [3, 4])
        [1, 2]

    Default semantics (no override)::

        >>> override_reducer([1, 2], [3, 4])
        [3, 4]
    """
    for arg in (a, b):
        if (
            isinstance(arg, dict)
            and arg.get("type") == "override"
            and "value" in arg
        ):
            return arg["value"]
    return b


__all__ = ["override_reducer"]
