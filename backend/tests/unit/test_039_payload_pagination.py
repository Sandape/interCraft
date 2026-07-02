"""REQ-039 US6 — payload pagination unit tests (FR-025/026/027/028/029).

Pure unit tests over :func:`service.fetch_payload_chunk`. Uses a fake
``repository.list_node_payload`` to avoid DB I/O.

Coverage:

- Default offset=0, limit=51200 (FR-025 default).
- Custom offset + limit applied to byte range (FR-026).
- ``total_size`` / ``remaining`` computed correctly.
- 50MB payload → :class:`PayloadTooLargeError` → HTTP 413 (FR-029).
- Negative offset or zero limit → :class:`ValueError`.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.admin_console import service
from app.modules.admin_console.service import (
    DEFAULT_PAYLOAD_LIMIT,
    MAX_PAYLOAD_BYTES,
    PayloadTooLargeError,
    TraceNotFoundError,
    _normalize_chunk_args,
    fetch_payload_chunk,
)


# ---------------------------------------------------------------------------
# Argument normalization
# ---------------------------------------------------------------------------


class TestNormalizeChunkArgs:
    def test_defaults(self) -> None:
        assert _normalize_chunk_args(0, 51200) == (0, 51200)

    def test_negative_offset_rejected(self) -> None:
        with pytest.raises(ValueError):
            _normalize_chunk_args(-1, 51200)

    def test_zero_limit_rejected(self) -> None:
        with pytest.raises(ValueError):
            _normalize_chunk_args(0, 0)

    def test_huge_limit_clamped_to_51200(self) -> None:
        assert _normalize_chunk_args(0, 999999) == (0, 51200)


# ---------------------------------------------------------------------------
# fetch_payload_chunk — patches repository
# ---------------------------------------------------------------------------


async def _patch_repo(monkeypatch, *, payload: str | None, total_override: int | None = None):
    """Patch ``service.repository.list_node_payload`` and yield the call args."""

    captured = {}

    async def fake_list_node_payload(session, trace_id, node_id):
        captured["trace_id"] = trace_id
        captured["node_id"] = node_id
        if payload is None:
            return None
        size = total_override if total_override is not None else len(payload.encode("utf-8"))
        return payload, size

    monkeypatch.setattr(service.repository, "list_node_payload", fake_list_node_payload)
    return captured


class TestFetchPayloadChunkHappyPath:
    async def test_default_returns_first_51200(self, monkeypatch) -> None:
        payload = "x" * 100_000
        captured = await _patch_repo(monkeypatch, payload=payload)
        tid, nid = uuid4(), "plan"
        chunk = await fetch_payload_chunk(
            SimpleNamespace(), trace_id=tid, node_id=nid
        )
        assert chunk.trace_id == tid
        assert chunk.node_id == "plan"
        assert chunk.offset == 0
        assert chunk.limit == 51200
        assert len(chunk.chunk.encode("utf-8")) == 51200
        assert chunk.total_size == 100_000
        assert chunk.remaining == 100_000 - 51200
        assert captured["trace_id"] == tid
        assert captured["node_id"] == "plan"

    async def test_custom_offset_and_limit(self, monkeypatch) -> None:
        payload = "abcdefghij" * 1000  # 10000 bytes
        await _patch_repo(monkeypatch, payload=payload)
        chunk = await fetch_payload_chunk(
            SimpleNamespace(),
            trace_id=uuid4(),
            node_id="plan",
            offset=100,
            limit=200,
        )
        assert chunk.offset == 100
        assert chunk.limit == 200
        assert chunk.chunk == payload[100:300]
        assert chunk.remaining == 10000 - 300

    async def test_offset_past_end_returns_empty(self, monkeypatch) -> None:
        payload = "hello"
        await _patch_repo(monkeypatch, payload=payload)
        chunk = await fetch_payload_chunk(
            SimpleNamespace(),
            trace_id=uuid4(),
            node_id="plan",
            offset=999,
            limit=51200,
        )
        assert chunk.chunk == ""
        assert chunk.remaining == 0

    async def test_total_size_uses_utf8_bytes(self, monkeypatch) -> None:
        # Multi-byte characters: each Chinese char is 3 bytes in UTF-8.
        payload = "中" * 100  # 300 bytes
        await _patch_repo(monkeypatch, payload=payload)
        chunk = await fetch_payload_chunk(
            SimpleNamespace(), trace_id=uuid4(), node_id="plan"
        )
        assert chunk.total_size == 300


class TestFetchPayloadChunkErrors:
    async def test_missing_trace_raises(self, monkeypatch) -> None:
        await _patch_repo(monkeypatch, payload=None)
        with pytest.raises(TraceNotFoundError):
            await fetch_payload_chunk(
                SimpleNamespace(), trace_id=uuid4(), node_id="plan"
            )

    async def test_oversize_raises_413(self, monkeypatch) -> None:
        # Use a small payload string but override total to 50MB + 1.
        await _patch_repo(monkeypatch, payload="x", total_override=MAX_PAYLOAD_BYTES + 1)
        with pytest.raises(PayloadTooLargeError) as exc:
            await fetch_payload_chunk(
                SimpleNamespace(), trace_id=uuid4(), node_id="plan"
            )
        assert exc.value.status_code == 413
        assert exc.value.size == MAX_PAYLOAD_BYTES + 1
        assert exc.value.limit == MAX_PAYLOAD_BYTES

    async def test_exact_limit_passes(self, monkeypatch) -> None:
        await _patch_repo(monkeypatch, payload="x", total_override=MAX_PAYLOAD_BYTES)
        # Should NOT raise.
        chunk = await fetch_payload_chunk(
            SimpleNamespace(), trace_id=uuid4(), node_id="plan"
        )
        assert chunk.total_size == MAX_PAYLOAD_BYTES


def test_constants_match_ac() -> None:
    """Lock the public constants so a silent change to defaults breaks tests."""
    assert DEFAULT_PAYLOAD_LIMIT == 51200
    assert MAX_PAYLOAD_BYTES == 50 * 1024 * 1024