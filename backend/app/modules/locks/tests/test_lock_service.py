"""Lock service unit tests (T008) — mock Redis, test acquire/release/heartbeat/get_status."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.unit]


@pytest.fixture
def mock_redis():
    with (
        patch("app.modules.locks.redis_store.get_redis") as redis_store_get,
        patch("app.core.redis.get_redis") as core_redis_get,
    ):
        redis_mock = MagicMock()
        redis_mock.set = AsyncMock(return_value=True)
        redis_mock.get = AsyncMock(return_value=None)
        redis_mock.delete = AsyncMock(return_value=True)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.publish = AsyncMock(return_value=1)
        redis_mock.scan = AsyncMock(return_value=(0, []))
        redis_store_get.return_value = redis_mock
        core_redis_get.return_value = redis_mock
        yield redis_mock


@pytest.fixture
def mock_ws():
    with patch("app.modules.locks.service.connection_manager") as m:
        m.send_to_user = AsyncMock()
        m.broadcast_to_resource = AsyncMock()
        m.is_online = MagicMock(return_value=True)
        yield m


@pytest.fixture
def mock_audit():
    with patch("app.modules.locks.service.write_lock_audit", new_callable=AsyncMock):
        yield


class TestLockServiceAcquire:
    async def test_acquire_success_first_time(self, mock_redis, mock_ws, mock_audit):
        """User A acquires lock — SET NX returns True."""
        from app.modules.locks.service import LockService
        from app.modules.locks.schemas import AcquireInput

        mock_redis.set.return_value = True
        svc = LockService()
        user_id = str(uuid4())
        resource_id = str(uuid4())
        result = await svc.acquire(
            user_id=user_id,
            device_id="dev-1",
            session_id=str(uuid4()),
            input=AcquireInput(
                resource_type="resume_branch",
                resource_id=resource_id,
            ),
        )
        assert result.locked is True
        assert result.user_id == user_id
        assert result.lock_id is not None

    async def test_acquire_409_different_user(self, mock_redis, mock_ws, mock_audit):
        """User B tries to acquire a lock already held by User A."""
        from app.modules.locks.service import LockService
        from app.modules.locks.schemas import AcquireInput

        resource_id = str(uuid4())
        mock_redis.set.return_value = False
        mock_redis.get.return_value = {
            "user_id": str(uuid4()),
            "device_id": "dev-a",
            "acquired_at": "2026-06-13T10:00:00Z",
        }
        svc = LockService()
        with pytest.raises(Exception) as exc_info:
            await svc.acquire(
                user_id=str(uuid4()),
                device_id="dev-b",
                session_id=str(uuid4()),
                input=AcquireInput(
                    resource_type="resume_branch",
                    resource_id=resource_id,
                ),
            )
        assert exc_info.value.code_override == "lock.resource_locked"
        assert exc_info.value.http_status_override == 409

    async def test_acquire_idempotent_same_user(self, mock_redis, mock_ws, mock_audit):
        """Same user re-acquiring (e.g. React StrictMode double-mount) — returns existing lock_id (200).

        This is the fix for defect #3: previously this case returned 409 because
        of a TOCTOU race in the pre-check path. Now we let atomic SET NX decide.
        """
        from app.modules.locks.service import LockService
        from app.modules.locks.schemas import AcquireInput

        existing_lock_id = "existing-lock-abc"
        # SET NX returns False (key already exists)
        mock_redis.set.return_value = False
        mock_redis.get.return_value = {
            "user_id": "user-1",
            "device_id": "dev-a",
            "lock_id": existing_lock_id,
            "acquired_at": "2026-06-13T10:00:00Z",
            "expires_at": "2026-06-13T10:05:00Z",
        }
        svc = LockService()
        result = await svc.acquire(
            user_id="user-1",
            device_id="dev-b",  # different device, but same user
            session_id=str(uuid4()),
            input=AcquireInput(
                resource_type="resume_branch",
                resource_id=str(uuid4()),
            ),
        )
        assert result.locked is True
        assert result.lock_id == existing_lock_id  # Idempotent — returns existing
        assert result.user_id == "user-1"


class TestLockServiceRelease:
    async def test_release_success(self, mock_redis, mock_ws, mock_audit):
        """Owner releases lock — DEL succeeds."""
        from app.modules.locks.service import LockService

        lock_id = str(uuid4())
        resource_id = str(uuid4())
        mock_redis.scan.return_value = (0, [f"lock:resume_branch:{resource_id}"])
        mock_redis.get.return_value = {
            "lock_id": lock_id,
            "resource_type": "resume_branch",
            "resource_id": resource_id,
            "user_id": "user-1",
            "device_id": "dev-1",
            "session_id": "session-1",
        }
        mock_redis.delete.return_value = True
        svc = LockService()
        result = await svc.release(lock_id=lock_id, user_id="user-1")
        assert result.lock_id is not None

    async def test_release_403_not_owner(self, mock_redis, mock_ws, mock_audit):
        """Non-owner tries to release — 403."""
        from app.modules.locks.service import LockService

        lock_id = str(uuid4())
        resource_id = str(uuid4())
        mock_redis.scan.return_value = (0, [f"lock:resume_branch:{resource_id}"])
        mock_redis.get.return_value = {
            "lock_id": lock_id,
            "resource_type": "resume_branch",
            "resource_id": resource_id,
            "user_id": "user-a",
            "device_id": "dev-a",
        }
        svc = LockService()
        with pytest.raises(Exception) as exc_info:
            await svc.release(lock_id=lock_id, user_id="user-b")
        assert exc_info.value.code_override == "lock.not_yours"
        assert exc_info.value.http_status_override == 403

    async def test_release_404_lock_not_found(self, mock_redis, mock_ws, mock_audit):
        """Release non-existent lock — 404."""
        from app.modules.locks.service import LockService

        mock_redis.get.return_value = None
        svc = LockService()
        with pytest.raises(Exception) as exc_info:
            await svc.release(lock_id=str(uuid4()), user_id="user-1")
        assert exc_info.value.code_override == "lock.not_found"
        assert exc_info.value.http_status_override == 404


class TestLockServiceHeartbeat:
    async def test_heartbeat_success(self, mock_redis, mock_ws, mock_audit):
        """Heartbeat renews TTL."""
        from app.modules.locks.service import LockService

        lock_id = str(uuid4())
        resource_id = str(uuid4())
        mock_redis.scan.return_value = (0, [f"lock:resume_branch:{resource_id}"])
        mock_redis.get.return_value = {
            "lock_id": lock_id,
            "resource_type": "resume_branch",
            "resource_id": resource_id,
            "user_id": "user-1",
            "device_id": "dev-1",
            "session_id": "session-1",
        }
        mock_redis.expire.return_value = True
        svc = LockService()
        result = await svc.heartbeat(lock_id=lock_id, user_id="user-1")
        assert result is True


class TestLockServiceGetStatus:
    async def test_get_status_locked(self, mock_redis, mock_ws, mock_audit):
        """Get status returns locked=true with holder info."""
        from app.modules.locks.service import LockService

        mock_redis.get.return_value = {
            "user_id": "user-1",
            "device_id": "dev-1",
            "acquired_at": "2026-06-13T10:00:00Z",
            "expires_at": "2026-06-13T10:05:00Z",
        }
        svc = LockService()
        result = await svc.get_status("resume_branch", str(uuid4()))
        assert result.locked is True

    async def test_get_status_unlocked(self, mock_redis, mock_ws, mock_audit):
        """Get status returns locked=false when no lock exists."""
        from app.modules.locks.service import LockService

        mock_redis.get.return_value = None
        svc = LockService()
        result = await svc.get_status("resume_branch", str(uuid4()))
        assert result.locked is False
