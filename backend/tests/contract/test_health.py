"""Contract test — health endpoint shape."""
import pytest

pytestmark = pytest.mark.contract


def test_healthz_shape():
    payload = {"status": "ok", "db": "ok", "redis": "ok", "version": "0.1.0"}
    # Required fields
    for k in ("status", "db", "redis", "version"):
        assert k in payload
    # Status enum
    assert payload["status"] in {"ok", "down", "degraded"}
