"""Real ARQ/Redis and owned-process lifecycle verification for issue #73.

These tests never flush Redis and refuse to use the default database. CI
provides an ephemeral Redis service and explicitly marks it test-owned.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

import pytest
from arq import Worker
from arq.connections import RedisSettings, create_pool

from app.workers.main import WorkerSettings

REPO_ROOT = Path(__file__).resolve().parents[3]


def _append_pid_evidence(event: str, **payload: object) -> None:
    configured = os.getenv("INTERCRAFT_PID_EVIDENCE_PATH", "").strip()
    if not configured:
        return
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, **payload}, sort_keys=True) + "\n")


def _owned_test_redis_url() -> str:
    url = os.getenv("INTERCRAFT_TEST_REDIS_URL", "").strip()
    owned = os.getenv("INTERCRAFT_TEST_REDIS_OWNED", "").strip() == "1"
    if not url or not owned:
        pytest.skip("explicit test-owned Redis was not provided")

    parsed = urlparse(url)
    db_index = int((parsed.path or "/0").lstrip("/") or "0")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or db_index == 0:
        pytest.fail("worker lifecycle tests require loopback Redis on a non-default DB")
    return url


async def _wait_until(
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout: float = 3.0,
    interval: float = 0.03,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition did not become true before the deadline")


@pytest.mark.asyncio
async def test_real_worker_heartbeat_job_consumption_and_shutdown() -> None:
    redis_url = _owned_test_redis_url()
    token = uuid.uuid4().hex
    queue_name = f"intercraft:test:queue:{token}"
    health_key = f"{queue_name}:health-check"
    job_id = f"worker-smoke-{token}"
    redis_settings = RedisSettings.from_dsn(redis_url)
    producer = await create_pool(redis_settings, default_queue_name=queue_name)
    worker = Worker(
        functions=WorkerSettings.functions,
        cron_jobs=[],
        redis_settings=redis_settings,
        queue_name=queue_name,
        health_check_key=health_key,
        health_check_interval=0.15,
        poll_delay=0.03,
        keep_result=5,
        handle_signals=False,
    )
    runner = asyncio.create_task(worker.async_run())

    try:
        await _wait_until(lambda: _key_exists(producer, health_key))
        first_payload = await producer.get(health_key)
        assert first_payload and b"j_complete=" in first_payload

        job = await producer.enqueue_job("ping", _job_id=job_id)
        assert job is not None
        result = await job.result(timeout=3, poll_delay=0.03)
        assert result == {"pong": True, "ts": 1}

        await _wait_until(lambda: _ttl_below(producer, health_key, 900))
        low_ttl = await producer.pttl(health_key)
        await _wait_until(lambda: _ttl_above(producer, health_key, low_ttl + 100))

        await worker.close()
        await asyncio.wait_for(asyncio.gather(runner, return_exceptions=True), timeout=2)
        assert await producer.exists(health_key) == 0
    finally:
        if not runner.done():
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)
        if worker._pool is not None:  # abrupt-failure cleanup only
            await worker.pool.close(close_connection_pool=True)
        await producer.delete(queue_name, health_key, f"arq:job:{job_id}", f"arq:result:{job_id}")
        await producer.close(close_connection_pool=True)


@pytest.mark.asyncio
async def test_abrupt_worker_loss_expires_heartbeat_without_manual_cleanup() -> None:
    redis_url = _owned_test_redis_url()
    token = uuid.uuid4().hex
    queue_name = f"intercraft:test:queue:{token}"
    health_key = f"{queue_name}:health-check"
    redis_settings = RedisSettings.from_dsn(redis_url)
    observer = await create_pool(redis_settings, default_queue_name=queue_name)
    worker = Worker(
        functions=WorkerSettings.functions,
        cron_jobs=[],
        redis_settings=redis_settings,
        queue_name=queue_name,
        health_check_key=health_key,
        health_check_interval=0.1,
        poll_delay=0.03,
        handle_signals=False,
    )
    runner = asyncio.create_task(worker.async_run())

    try:
        await _wait_until(lambda: _key_exists(observer, health_key))
        runner.cancel()
        await asyncio.gather(runner, return_exceptions=True)
        # Deliberately close only the socket: Worker.close() would delete the
        # heartbeat and would not model an abruptly terminated process.
        await worker.pool.close(close_connection_pool=True)
        worker._pool = None
        await _wait_until(lambda: _key_missing(observer, health_key), timeout=2.5)
    finally:
        if not runner.done():
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)
        await observer.delete(queue_name, health_key)
        await observer.close(close_connection_pool=True)


async def _key_exists(pool: object, key: str) -> bool:
    return bool(await pool.exists(key))  # type: ignore[attr-defined]


async def _key_missing(pool: object, key: str) -> bool:
    return not await _key_exists(pool, key)


async def _ttl_below(pool: object, key: str, threshold: int) -> bool:
    ttl = await pool.pttl(key)  # type: ignore[attr-defined]
    return 0 < ttl < threshold


async def _ttl_above(pool: object, key: str, threshold: int) -> bool:
    return await pool.pttl(key) > threshold  # type: ignore[attr-defined]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process ownership contract")
def test_restart_stops_only_manifest_owned_processes(tmp_path: Path) -> None:
    run_root = tmp_path / "run-root"
    current = run_root / "current"
    current.mkdir(parents=True)
    owned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    proc_stat = Path(f"/proc/{owned.pid}/stat")
    if proc_stat.exists():
        fingerprint = proc_stat.read_text(encoding="utf-8").split()[21]
    else:
        fingerprint = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(owned.pid)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        fingerprint = " ".join(fingerprint.split())
    manifest = current / "manifest.tsv"
    manifest.write_text(
        "service\tpid\towned\tlog\tstart_fingerprint\n"
        f"owned-test\t{owned.pid}\t1\t{tmp_path / 'owned.log'}\t{fingerprint}\n",
        encoding="utf-8",
    )
    _append_pid_evidence(
        "owned-process-before-stop",
        shell_pid=owned.pid,
        native_pid=owned.pid,
        start_fingerprint=fingerprint,
        owned_alive=True,
        unrelated_pid=unrelated.pid,
        unrelated_alive=True,
    )

    try:
        completed = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "dev-restart.sh"), "--stop-only"],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "INTERCRAFT_RUN_ROOT": str(run_root),
                "INTERCRAFT_STOP_TIMEOUT_SECONDS": "1",
                "INTERCRAFT_FORCE_STOP_TIMEOUT_SECONDS": "2",
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr

        deadline = time.monotonic() + 3
        while owned.poll() is None and time.monotonic() < deadline:
            time.sleep(0.03)
        assert owned.poll() is not None
        assert unrelated.poll() is None
        _append_pid_evidence(
            "owned-process-after-stop",
            shell_pid=owned.pid,
            native_pid=owned.pid,
            start_fingerprint=fingerprint,
            owned_alive=False,
            unrelated_pid=unrelated.pid,
            unrelated_alive=True,
        )
    finally:
        for process in (owned, unrelated):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=3)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process ownership contract")
def test_restart_retains_manifest_when_ownership_fingerprint_mismatches(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-root"
    current = run_root / "current"
    current.mkdir(parents=True)
    owned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    proc_stat = Path(f"/proc/{owned.pid}/stat")
    if proc_stat.exists():
        fingerprint = proc_stat.read_text(encoding="utf-8").split()[21]
    else:
        fingerprint = " ".join(
            subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(owned.pid)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.split()
        )
    manifest = current / "manifest.tsv"
    manifest.write_text(
        "service\tpid\tnative_pid\towned\tlog\tstart_fingerprint\n"
        f"owned-test\t{owned.pid}\t{owned.pid}\t1\towned.log\t{fingerprint}-wrong\n",
        encoding="utf-8",
    )

    try:
        completed = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "dev-restart.sh"), "--stop-only"],
            cwd=REPO_ROOT,
            env={**os.environ, "INTERCRAFT_RUN_ROOT": str(run_root)},
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert completed.returncode != 0
        assert "manifest retained" in completed.stderr
        assert manifest.exists()
        assert owned.poll() is None
    finally:
        if owned.poll() is None:
            owned.terminate()
            owned.wait(timeout=3)


@pytest.mark.skipif(os.name != "nt", reason="Git Bash/MSYS process contract")
def test_windows_restart_maps_msys_pid_and_preserves_unrelated_process(
    tmp_path: Path,
) -> None:
    bash = Path(os.getenv("INTERCRAFT_GIT_BASH", r"D:\Develop\Git\bin\bash.exe"))
    if not bash.exists():
        pytest.fail(f"required Git Bash not found: {bash}")

    run_root = tmp_path / "run-root"
    current = run_root / "current"
    current.mkdir(parents=True)
    ids_file = tmp_path / "native-ids.tsv"
    launcher = tmp_path / "launch-native-children.sh"
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "run_root=$1\n"
        "ids_file=$2\n"
        "ping.exe -n 60 127.0.0.1 >/dev/null &\n"
        "owned=$!\n"
        "ping.exe -n 60 127.0.0.1 >/dev/null &\n"
        "unrelated=$!\n"
        "map_winpid() {\n"
        "  local line\n"
        '  line=$(ps -p "$1" | tail -n 1)\n'
        "  set -- $line\n"
        "  printf '%s' \"$4\"\n"
        "}\n"
        'owned_win=$(map_winpid "$owned")\n'
        'unrelated_win=$(map_winpid "$unrelated")\n'
        "fingerprint=$(powershell.exe -NoProfile -NonInteractive -Command \"(Get-Process -Id $owned_win -ErrorAction Stop).StartTime.ToUniversalTime().Ticks\" | tr -d '\\r\\n')\n"
        "unrelated_fingerprint=$(powershell.exe -NoProfile -NonInteractive -Command \"(Get-Process -Id $unrelated_win -ErrorAction Stop).StartTime.ToUniversalTime().Ticks\" | tr -d '\\r\\n')\n"
        "printf 'service\\tpid\\tnative_pid\\towned\\tlog\\tstart_fingerprint\\n' > \"$run_root/current/manifest.tsv\"\n"
        'printf \'owned-test\\t%s\\t%s\\t1\\towned.log\\t%s\\n\' "$owned" "$owned_win" "$fingerprint" >> "$run_root/current/manifest.tsv"\n'
        'printf \'%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n\' "$owned" "$owned_win" "$unrelated" "$unrelated_win" "$fingerprint" "$unrelated_fingerprint" > "$ids_file"\n'
        "wait || true\n",
        encoding="utf-8",
    )
    launcher_process = subprocess.Popen(
        [str(bash), str(launcher), str(run_root), str(ids_file)],
        cwd=REPO_ROOT,
    )
    owned_winpid = unrelated_winpid = 0

    try:
        deadline = time.monotonic() + 5
        while not ids_file.exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        assert ids_file.exists(), "Git Bash launcher did not publish native PIDs"
        (
            owned_shell_raw,
            owned_raw,
            unrelated_shell_raw,
            unrelated_raw,
            fingerprint,
            unrelated_fingerprint,
        ) = ids_file.read_text(encoding="utf-8").strip().split("\t")
        owned_shell_pid = int(owned_shell_raw)
        unrelated_shell_pid = int(unrelated_shell_raw)
        owned_winpid, unrelated_winpid = int(owned_raw), int(unrelated_raw)
        assert fingerprint.isdigit() and int(fingerprint) > 0
        _append_pid_evidence(
            "windows-owned-process-before-stop",
            shell_pid=owned_shell_pid,
            native_pid=owned_winpid,
            start_fingerprint=fingerprint,
            owned_alive=True,
            unrelated_pid=unrelated_winpid,
            unrelated_alive=True,
        )

        completed = subprocess.run(
            [str(bash), str(REPO_ROOT / "scripts" / "dev-restart.sh"), "--stop-only"],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "INTERCRAFT_RUN_ROOT": str(run_root),
                "INTERCRAFT_STOP_TIMEOUT_SECONDS": "1",
                "INTERCRAFT_FORCE_STOP_TIMEOUT_SECONDS": "2",
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert completed.returncode == 0, completed.stderr
        assert not _windows_pid_exists(owned_winpid)
        assert _windows_pid_exists(unrelated_winpid)
        assert not (current / "manifest.tsv").exists()

        # A stale/reused ownership fingerprint must neither kill the process
        # nor discard the evidence needed for manual recovery.
        (current / "manifest.tsv").write_text(
            "service\tpid\tnative_pid\towned\tlog\tstart_fingerprint\n"
            f"stale-test\t{unrelated_shell_pid}\t{unrelated_winpid}\t1\tstale.log\t{unrelated_fingerprint}-wrong\n",
            encoding="utf-8",
        )
        refused = subprocess.run(
            [str(bash), str(REPO_ROOT / "scripts" / "dev-restart.sh"), "--stop-only"],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "INTERCRAFT_RUN_ROOT": str(run_root),
                "INTERCRAFT_STOP_TIMEOUT_SECONDS": "1",
                "INTERCRAFT_FORCE_STOP_TIMEOUT_SECONDS": "2",
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert refused.returncode != 0
        assert "manifest retained" in refused.stderr
        assert (current / "manifest.tsv").exists()
        assert _windows_pid_exists(unrelated_winpid)

        unverified_manifest = (
            "service\tpid\tnative_pid\towned\tlog\tstart_fingerprint\n"
            f"unverified-test\t{unrelated_shell_pid}\t0\t1\tunverified.log\tUNVERIFIED\n"
        )
        (current / "manifest.tsv").write_text(
            unverified_manifest,
            encoding="utf-8",
        )
        unverified_stop = subprocess.run(
            [str(bash), str(REPO_ROOT / "scripts" / "dev-restart.sh"), "--stop-only"],
            cwd=REPO_ROOT,
            env={**os.environ, "INTERCRAFT_RUN_ROOT": str(run_root)},
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert unverified_stop.returncode != 0
        assert (current / "manifest.tsv").read_text(encoding="utf-8") == unverified_manifest
        assert _windows_pid_exists(unrelated_winpid)

        blocked_start = subprocess.run(
            [str(bash), str(REPO_ROOT / "scripts" / "dev-up.sh")],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                "INTERCRAFT_RUN_ROOT": str(run_root),
                "INTERCRAFT_SKIP_INSTALL": "1",
                "INTERCRAFT_API_PORT": "48991",
                "INTERCRAFT_FRONTEND_PORT": "48992",
            },
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert blocked_start.returncode != 0
        assert "UNVERIFIED ownership evidence blocks startup" in blocked_start.stderr
        assert (current / "manifest.tsv").read_text(encoding="utf-8") == unverified_manifest
        assert _windows_pid_exists(unrelated_winpid)
        _append_pid_evidence(
            "windows-owned-process-after-stop",
            shell_pid=owned_shell_pid,
            native_pid=owned_winpid,
            start_fingerprint=fingerprint,
            owned_alive=False,
            unrelated_pid=unrelated_winpid,
            unrelated_alive=True,
        )
    finally:
        for winpid in (owned_winpid, unrelated_winpid):
            if winpid and _windows_pid_exists(winpid):
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(winpid)],
                    check=False,
                    capture_output=True,
                )
        try:
            launcher_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            launcher_process.terminate()
            launcher_process.wait(timeout=3)


def _windows_pid_exists(pid: int) -> bool:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 0 }} else {{ exit 1 }}",
        ],
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0
