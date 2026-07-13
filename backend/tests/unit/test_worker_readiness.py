"""Worker heartbeat, readiness, and local lifecycle contracts for issue #73."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.redis import (
    ARQ_HEALTH_CHECK_TTL_MS,
    WorkerHealth,
    classify_arq_worker_health,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
VALID_HEALTH = "Jul-14 12:34:56 j_complete=1 j_failed=0 j_retried=0 j_ongoing=0 queued=0"


@pytest.mark.parametrize(
    ("payload", "pttl_ms", "expected_state", "expected_reason"),
    [
        (VALID_HEALTH, ARQ_HEALTH_CHECK_TTL_MS - 100, "up", "fresh"),
        (None, -2, "down", "missing"),
        ("not-an-arq-health-record", 5_000, "down", "malformed"),
        (VALID_HEALTH, -1, "stale", "no_ttl"),
        (VALID_HEALTH, 1, "stale", "expired_heartbeat"),
        (
            VALID_HEALTH,
            ARQ_HEALTH_CHECK_TTL_MS + 5_000,
            "stale",
            "unexpected_ttl",
        ),
    ],
)
def test_classify_arq_worker_health_truth_table(
    payload: str | None,
    pttl_ms: int,
    expected_state: str,
    expected_reason: str,
) -> None:
    health = classify_arq_worker_health(payload, pttl_ms)

    assert health.state == expected_state
    assert health.reason == expected_reason


@pytest.mark.asyncio
async def test_healthz_is_dependency_free_liveness(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "db_ping",
        AsyncMock(side_effect=AssertionError("liveness must not call Postgres")),
    )
    monkeypatch.setattr(
        main_module,
        "redis_ping",
        AsyncMock(side_effect=AssertionError("liveness must not call Redis")),
    )

    async with AsyncClient(
        transport=ASGITransport(app=main_module.app), base_url="http://test"
    ) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("db_ok", "redis_ok", "worker", "expected_status"),
    [
        (True, True, WorkerHealth("up", "fresh", 100), 200),
        (True, True, WorkerHealth("down", "missing"), 503),
        (True, True, WorkerHealth("stale", "no_ttl"), 503),
        (False, True, WorkerHealth("up", "fresh", 100), 503),
        (True, False, WorkerHealth("up", "fresh", 100), 503),
    ],
)
async def test_readyz_requires_db_redis_and_fresh_worker(
    monkeypatch: pytest.MonkeyPatch,
    db_ok: bool,
    redis_ok: bool,
    worker: WorkerHealth,
    expected_status: int,
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "db_ping", AsyncMock(return_value=db_ok))
    monkeypatch.setattr(main_module, "redis_ping", AsyncMock(return_value=redis_ok))
    monkeypatch.setattr(main_module, "arq_worker_health", AsyncMock(return_value=worker))

    async with AsyncClient(
        transport=ASGITransport(app=main_module.app), base_url="http://test"
    ) as client:
        response = await client.get("/readyz")

    payload = response.json()
    assert response.status_code == expected_status
    assert payload["arq_worker"] == worker.state
    assert payload["arq_worker_reason"] == worker.reason
    assert payload["derive_backend"] == ("ready" if expected_status == 200 else "unavailable")


@pytest.mark.asyncio
async def test_readyz_bounds_slow_dependency_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    async def never_returns() -> bool:
        await asyncio.Event().wait()
        return True

    monkeypatch.setattr(main_module, "READINESS_PROBE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(main_module, "db_ping", never_returns)
    monkeypatch.setattr(main_module, "redis_ping", AsyncMock(return_value=True))
    monkeypatch.setattr(
        main_module,
        "arq_worker_health",
        AsyncMock(return_value=WorkerHealth("up", "fresh", 100)),
    )

    async with AsyncClient(
        transport=ASGITransport(app=main_module.app), base_url="http://test"
    ) as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["db"] == "down"


def test_worker_settings_register_transport_smoke_and_health_contract() -> None:
    from app.core.redis import (
        ARQ_HEALTH_CHECK_INTERVAL_SECONDS,
        ARQ_HEALTH_CHECK_KEY,
        ARQ_QUEUE_NAME,
    )
    from app.workers.main import WorkerSettings
    from app.workers.tasks.dummy import ping

    assert ping in WorkerSettings.functions
    assert WorkerSettings.queue_name == ARQ_QUEUE_NAME
    assert WorkerSettings.health_check_key == ARQ_HEALTH_CHECK_KEY
    assert WorkerSettings.health_check_interval == ARQ_HEALTH_CHECK_INTERVAL_SECONDS
    assert WorkerSettings.on_startup is not None
    assert WorkerSettings.on_shutdown is not None
    assert not hasattr(WorkerSettings, "on_failure")


@pytest.mark.asyncio
async def test_worker_callbacks_initialize_and_release_process_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agents.checkpointer as checkpointer_module
    import app.channels.message_handler as message_handler_module
    import app.workers.main as worker_module

    configure_logging = MagicMock()
    init_tracing = MagicMock()
    close_checkpointer = AsyncMock()
    shutdown_llm_client = AsyncMock()
    close_redis = AsyncMock()
    dispose_engine = AsyncMock()
    shutdown_tracing = MagicMock()
    monkeypatch.setattr(worker_module, "configure_logging", configure_logging)
    monkeypatch.setattr(worker_module, "init_tracing", init_tracing)
    monkeypatch.setattr(checkpointer_module, "close_checkpointer", close_checkpointer)
    monkeypatch.setattr(message_handler_module, "shutdown_llm_client", shutdown_llm_client)
    monkeypatch.setattr(worker_module, "close_redis", close_redis)
    monkeypatch.setattr(worker_module, "dispose_engine", dispose_engine)
    monkeypatch.setattr(worker_module, "shutdown_tracing", shutdown_tracing)
    ctx: dict[str, object] = {}

    await worker_module.on_worker_startup(ctx)
    await worker_module.on_worker_shutdown(ctx)

    configure_logging.assert_called_once_with()
    init_tracing.assert_called_once()
    close_checkpointer.assert_awaited_once_with()
    shutdown_llm_client.assert_awaited_once_with()
    close_redis.assert_awaited_once_with()
    dispose_engine.assert_awaited_once_with()
    shutdown_tracing.assert_called_once_with()


def test_local_lifecycle_scripts_use_owned_pid_manifest() -> None:
    dev_up = (REPO_ROOT / "scripts" / "dev-up.sh").read_text(encoding="utf-8")
    restart = (REPO_ROOT / "scripts" / "dev-restart.sh").read_text(encoding="utf-8")

    assert "WorkerSettings" in dev_up
    assert "manifest.tsv" in dev_up
    assert "INTERCRAFT_RUN_ROOT" in dev_up
    assert "msys_pid_to_winpid" in dev_up
    assert "native_pid" in dev_up
    assert "${DATABASE_URL" not in dev_up
    assert "${REDIS_URL" not in dev_up
    assert "--stop-only" in restart
    assert 'dev-up.sh" --stop-only' in restart
    assert "manifest retained" in restart
    assert "survived TERM and KILL" in dev_up
    assert "taskkill /IM" not in restart
    assert "Get-NetTCPConnection" not in restart


def test_unverified_manifest_evidence_is_fail_closed() -> None:
    dev_up = (REPO_ROOT / "scripts" / "dev-up.sh").read_text(encoding="utf-8")

    assert "UNVERIFIED ownership evidence retained" in dev_up
    assert "UNVERIFIED ownership evidence blocks startup" in dev_up
    assert "invalid native PID evidence blocks startup" in dev_up


def test_compose_declares_full_stack_and_worker_healthcheck() -> None:
    compose = (REPO_ROOT / "backend" / "docker-compose.yml").read_text(encoding="utf-8")

    for service in ("api:", "worker:", "redis:", "frontend:"):
        assert service in compose
    assert "app.workers.main.WorkerSettings" in compose
    assert "--check" in compose
    assert "stop_grace_period" in compose
    assert "${DATABASE_URL:?" in compose
    assert "${JWT_SECRET:?" in compose
    assert "${MASTER_KEY:?" in compose
    assert "http://127.0.0.1:8000/readyz" in compose
    assert "VITE_API_TARGET: http://api:8000" in compose
    assert "http://127.0.0.1:5173/api/v1/openapi.json" in compose
    assert "INTERCRAFT_FRONTEND_PORT:-5173" in compose
    assert compose.count("healthcheck:") >= 4


def test_ci_runs_real_worker_readiness_gate_and_uploads_evidence() -> None:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "worker-readiness:" in ci
    assert "INTERCRAFT_TEST_REDIS_URL" in ci
    assert "postgresql+asyncpg://PLACEHOLDER" not in ci
    assert "test_worker_lifecycle.py" in ci
    assert "test_worker_readiness.py" in ci
    assert "if: always()" in ci
    assert "upload-artifact" in ci
    assert "owned-pid-evidence" in ci
    assert "Verify owned PID evidence" in ci
    assert "frontend-proxy-openapi.json" in ci
    assert "ps -eo pid,ppid,lstart,args" not in ci
