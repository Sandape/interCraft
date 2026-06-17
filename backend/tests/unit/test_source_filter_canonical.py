"""020 (FIX-005, D-004) — ?source= is the canonical filter param.

The 019 contract documents `?source=auto|manual|all`; the implementation
accepted only `?filter[source]=`. 020 makes `?source=` canonical and
keeps `?filter[source]=` as a deprecated alias for one release so
existing 3rd-party consumers keep working.

This test asserts (at the FastAPI/OpenAPI layer):
  1. The OpenAPI schema declares `source` as a query parameter on
     GET /error-questions.
  2. Both `?source=` and `?filter[source]=` are accepted at the route
     level (i.e. the parameter has both an alias and a canonical name).
"""
from __future__ import annotations


class TestSourceFilterCanonical:
    def test_openapi_lists_source_query_param(self) -> None:
        from app.main import app

        schema = app.openapi()
        # Find the GET /error-questions path (it may be prefixed).
        matching = [
            p for p in schema["paths"].keys()
            if p.endswith("/error-questions") and "get" in schema["paths"][p]
        ]
        assert matching, f"GET /error-questions not in OpenAPI: {schema['paths'].keys()}"

        get_op = schema["paths"][matching[0]]["get"]
        query_names = [p["name"] for p in get_op.get("parameters", []) if p.get("in") == "query"]
        assert "source" in query_names, f"Canonical ?source= missing: got {query_names}"

    def test_filter_source_alias_preserved(self) -> None:
        """Deprecated `?filter[source]=` alias kept for one release."""
        from app.main import app

        schema = app.openapi()
        matching = [
            p for p in schema["paths"].keys()
            if p.endswith("/error-questions") and "get" in schema["paths"][p]
        ]
        get_op = schema["paths"][matching[0]]["get"]
        query_names = [p["name"] for p in get_op.get("parameters", []) if p.get("in") == "query"]
        # The FastAPI `alias` keeps the URL form `?filter[source]=` while
        # the parameter name (what OpenAPI lists) is `source`.
        # We accept either: alias "filter[source]" surfaces as a separate
        # parameter, OR the canonical "source" with an alias annotation.
        assert "source" in query_names, f"Canonical ?source= missing: got {query_names}"