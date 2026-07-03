"""DEPRECATED — score node re-export shell (US2 FR-004 AC-4.8).

This module is a **compatibility re-export** for the US2 split of the
legacy ``score_node``. It is **not** the implementation site anymore:

- ``score_llm_node`` lives in ``score_llm.py`` (LLM call only).
- ``sink_error_node`` lives in ``sink_error.py`` (DB write only).

The legacy ``score_node`` (which mixed LLM + DB) is intentionally NOT
exported here — per US2 R5'' (round 3) the old implementation is removed
in favour of the split. Test files and external imports should reference
``score_llm`` / ``sink_error`` directly.

This file exists for the dual-track period (FR-008, US1 AC-8.3) so that
any caller that imported ``from app.agents.interview.nodes.score import
score_node`` continues to import without raising. The re-export surfaces a
``DeprecationWarning``-level marker (``"DEPRECATED"`` literal in this
docstring + ``__all__``) so lint / grep checks can detect stale call
sites and we can delete the file after the 1-week observation window
(AC-8.3 — release manager tracks the deletion in the release tag).
"""
from __future__ import annotations

# DEPRECATED: this file is a re-export shell, the implementation has moved.
from app.agents.interview.nodes.score_llm import ERROR_THRESHOLD  # noqa: F401
from app.agents.interview.nodes.score_llm import score_llm_node
from app.agents.interview.nodes.sink_error import _derive_source_qid, sink_error_node

# Compatibility: ``score_node`` is gone. Importing it raises AttributeError
# so callers fail fast and update to the split names.
__all__ = [
    "ERROR_THRESHOLD",
    "_derive_source_qid",
    "score_llm_node",
    "sink_error_node",
]