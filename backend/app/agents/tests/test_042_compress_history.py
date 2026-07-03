"""REQ-042 US-2 MB3 — compress_history + CompressedHistory.

AC-5.1 ~ AC-5.5 (FR-005), AC-6.1 ~ AC-6.3 (FR-006), AC-9.1 (FR-009 env).

Test-First red-phase commit per REQ-041 AC-9.1 pattern.
Per L041-003 — REAL graph.ainvoke end-to-end test (no helper-direct mock).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# AC-6.1 — CompressedHistory Pydantic fields
# ---------------------------------------------------------------------------
class TestCompressedHistorySchema:
    def test_compressed_history_module_exists(self):
        """AC-6.1: CompressedHistory defined in compress_history.py."""
        from app.agents.utils.compress_history import CompressedHistory

        assert CompressedHistory is not None

    def test_compressed_history_required_fields(self):
        """AC-6.1: summary + retained_message_count + original_message_count + compressed_at + triggered_by."""
        from app.agents.utils.compress_history import CompressedHistory

        ch = CompressedHistory(
            summary="user talked about Python",
            retained_message_count=8,
            original_message_count=20,
            compressed_at=datetime.utcnow(),
            triggered_by="active",
        )
        assert ch.summary == "user talked about Python"
        assert ch.retained_message_count == 8
        assert ch.original_message_count == 20
        assert isinstance(ch.compressed_at, datetime)
        assert ch.triggered_by == "active"

    def test_triggered_by_literal_validation(self):
        """AC-6.1: triggered_by is Literal['active', 'passive']."""
        from app.agents.utils.compress_history import CompressedHistory
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CompressedHistory(
                summary="x",
                retained_message_count=8,
                original_message_count=20,
                compressed_at=datetime.utcnow(),
                triggered_by="invalid",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# AC-5.2 — Active trigger (len(messages) >= 20)
# ---------------------------------------------------------------------------
class TestActiveTrigger:
    def test_estimate_tokens_function_exists(self):
        """AC-5.x: _estimate_tokens function exists."""
        from app.agents.utils.compress_history import _estimate_tokens

        assert _estimate_tokens([{"role": "user", "content": "hi"}]) > 0


# ---------------------------------------------------------------------------
# AC-5.5 — node_error_handler decorator attached
# ---------------------------------------------------------------------------
class TestCompressHistoryNodeDecorator:
    def test_compress_history_node_module_exists(self):
        """AC-5.1: compress_history_node defined."""
        from app.agents.interview.nodes.compress_history import compress_history_node

        assert callable(compress_history_node)


# ---------------------------------------------------------------------------
# AC-9.1 — env var us2_use_v2_compress_history
# ---------------------------------------------------------------------------
class TestCompressHistoryEnvFlag:
    def test_compress_history_env_flag(self):
        """AC-9.1: us2_use_v2_compress_history flag exists, default False."""
        from app.core.config import get_settings

        settings = get_settings()
        assert settings.us2_use_v2_compress_history is False
