"""020 (FIX-004, D-003) — clear-source must be PATCH, not POST.

The 019 contract documents PATCH; the backend currently implements POST.
Per the contract-parity principle, the implementation must conform to the
contract, not vice versa. This test asserts:

  1. The FastAPI app registers clear-source as PATCH.
  2. POST to clear-source returns 405 Method Not Allowed.
  3. PATCH is the registered verb in the OpenAPI schema.
"""
from __future__ import annotations

import pytest


def _route_for_clear_source(app) -> tuple[str, list[str]]:
    """Return (path, methods) for the clear-source route in the FastAPI app."""
    for route in app.routes:
        if getattr(route, "path", "").endswith("/clear-source"):
            methods = sorted(getattr(route, "methods", set()) - {"HEAD"})
            return route.path, methods
    raise AssertionError("clear-source route not registered")


class TestClearSourceMethodIsPatch:
    def test_route_registered_as_patch_not_post(self) -> None:
        from app.main import app

        path, methods = _route_for_clear_source(app)
        assert "PATCH" in methods, f"clear-source must allow PATCH; got {methods}"
        assert "POST" not in methods, f"clear-source must NOT allow POST anymore; got {methods}"

    def test_openapi_schema_declares_patch(self) -> None:
        """The OpenAPI document is the source of truth for 3rd-party clients."""
        from app.main import app

        schema = app.openapi()
        path = "/api/v1/error-questions/{id}/clear-source"
        # FastAPI may register the full prefixed path or a suffix depending
        # on how the router is mounted; accept either form.
        matching = [p for p in schema["paths"].keys() if p.endswith("/clear-source")]
        assert matching, f"clear-source path missing from OpenAPI: {schema['paths'].keys()}"

        ops = schema["paths"][matching[0]]
        assert "patch" in ops, f"OpenAPI missing PATCH op for clear-source: {ops.keys()}"
        assert "post" not in ops, f"OpenAPI still has POST op for clear-source: {ops.keys()}"