from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.middleware.trace_id import TraceIDMiddleware
from app.observability.tracing import get_trace_context


@pytest.mark.anyio
async def test_http_trace_header_binds_request_state_and_context() -> None:
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/probe")
    async def probe(request: Request) -> dict[str, str | None]:
        ctx = get_trace_context()
        return {"stateTraceId": request.state.trace_id, "contextTraceId": ctx.trace_id}

    trace_id = "1" * 32
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/probe", headers={"X-Trace-Id": trace_id})

    assert response.status_code == 200
    assert response.headers["X-Trace-Id"] == trace_id
    assert response.json() == {"stateTraceId": trace_id, "contextTraceId": trace_id}
