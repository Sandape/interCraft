"""REQ-042 US-2 MB4 — LangGraph Store + researcher.

AC-7.1 ~ AC-7.4 (FR-007), AC-8.1 ~ AC-8.3 (FR-008), AC-E2E-5 (cross-session).

Test-First red-phase commit per REQ-041 AC-9.1 pattern.
Per L041-003 — REAL PostgresStore, no helper-direct mock.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# AC-7.1 — PostgresStore importable
# ---------------------------------------------------------------------------
class TestPostgresStoreImport:
    def test_langgraph_store_module_exists(self):
        """AC-7.1: langgraph_store module exists."""
        from app.agents.utils.langgraph_store import (
            get_user_memory,
            put_user_memory,
        )

        assert callable(get_user_memory)
        assert callable(put_user_memory)

    def test_postgres_store_importable(self):
        """AC-7.1: PostgresStore importable from langgraph.store.postgres."""
        from langgraph.store.postgres import PostgresStore

        assert PostgresStore is not None


# ---------------------------------------------------------------------------
# AC-7.2 — namespace format ("agent_mem", uid) tuple
# ---------------------------------------------------------------------------
class TestNamespace:
    def test_namespace_is_tuple_format(self):
        """AC-7.2: namespace is ("agent_runtime_v2", uid) tuple — not single string.

        Per AC-US-2 R3: avoid collision with 028 agent_memory namespace by
        using the ``agent_runtime_v2`` prefix (per US-2 R3 dispute log).
        """
        from app.agents.utils.langgraph_store import _namespace_for_user

        ns = _namespace_for_user("user-123")
        assert isinstance(ns, tuple)
        assert ns[0] == "agent_runtime_v2"
        assert ns[1] == "user-123"


# ---------------------------------------------------------------------------
# AC-8.1 — researcher state fields
# ---------------------------------------------------------------------------
class TestResearcherStateFields:
    def test_researcher_state_module_exists(self):
        """AC-8.1: researcher/state.py defines ResearcherSubState."""
        from app.agents.researcher.state import ResearcherSubState

        assert ResearcherSubState is not None

    def test_researcher_state_has_raw_notes(self):
        """AC-8.1: raw_notes: list[dict] with default_factory=list."""
        from app.agents.researcher.state import ResearcherSubState

        # Pydantic v2 default_factory should produce []
        state = ResearcherSubState()
        assert state.raw_notes == []

    def test_researcher_state_has_compressed_research(self):
        """AC-8.1: compressed_research: CompressedHistory | None default None."""
        from app.agents.researcher.state import ResearcherSubState

        state = ResearcherSubState()
        assert state.compressed_research is None
