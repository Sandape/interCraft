"""REQ-042 US-2 FR-008 — researcher sub-state.

This module defines the **per-agent** state shape for the
``researcher`` subgraph (M013 / search-then-summarise pattern). The
researcher subgraph is layered on top of an existing
``sqlalchemy.select(...)``-based long-term note pipeline (the
``raw_notes`` *write* path lives in module ``M013`` and is **not**
replaced by REQ-042 — see AC-8.3 cross-team contract).

REQ-042 adds two new fields:
* ``raw_notes`` — a ``list[dict]`` accumulator. Reducer is ``extend``
  (take the union of new and existing notes) so we never lose
  history when multiple tool calls land in the same graph step.
* ``compressed_research`` — a ``CompressedHistory | None`` snapshot
  of the latest LLM-compressed view of ``raw_notes``. The
  ``final_report`` phase reads this rather than ``raw_notes`` when
  the trigger has fired.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agents.utils.compress_history import CompressedHistory


def raw_notes_reducer(
    existing: list[dict[str, Any]] | None,
    new: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Extend-reducer for ``raw_notes``.

    Returns the union of existing and new notes (de-duplicated by
    ``id`` field when present; preserves insertion order otherwise).

    Per FR-008 / AC-8.2 — this is **not** an override reducer; raw_notes
    must accumulate, not be replaced on each step.
    """
    base = list(existing or [])
    seen_ids: set[str] = set()
    for note in base:
        if isinstance(note, dict) and "id" in note:
            seen_ids.add(str(note["id"]))
    for note in new or []:
        if isinstance(note, dict) and "id" in note:
            if str(note["id"]) in seen_ids:
                continue
            seen_ids.add(str(note["id"]))
        base.append(note)
    return base


class ResearcherSubState(BaseModel):
    """State for the researcher subgraph (M013).

    Two new fields added in REQ-042 US-2 (FR-008):
    * ``raw_notes`` — list of search-result dicts (extend reducer).
    * ``compressed_research`` — CompressedHistory | None (override).

    The legacy ``final_report: str`` field is preserved (read by
    032/033/034 pipeline) so we do not break cross-team contracts
    (AC-8.3).
    """

    raw_notes: list[dict[str, Any]] = Field(default_factory=list)
    compressed_research: CompressedHistory | None = None
    final_report: str = ""


__all__ = [
    "ResearcherSubState",
    "raw_notes_reducer",
]
