"""T017 — Resume v2 repository tests.

Covers the async SQLAlchemy repository in `app.modules.resumes_v2.repository`:
- create() returns row with version=0
- get(id) round-trips data
- list(user_id) returns the user's resumes (and NOT another user's)
- update_with_version happy path: version bumps N -> N+1
- update_with_version conflict path: stale version returns None
- duplicate() deep-copies data, resets is_public/is_locked/password_hash, generates
  new UUID + new slug `<orig>-copy-1` (or `-copy-N` if collisions exist), no
  statistics or analysis row is created
- soft_delete() cascades to statistics + analysis
- set_lock() toggles is_locked independently of version
- set_sharing() sets is_public + password_hash

These tests pin the repository contract that the US1 service layer (T021)
will build on. They are real-DB integration tests; the repository methods
already exist per T013, so these should PASS in Wave 2 (Wave 3 will only
change api.py + service.py).

T017 — authored in Wave 2, awaiting US1 service-layer wiring.
"""
from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import set_rls_user_id
from app.modules.resumes_v2.repository import ResumeV2Repository
from app.modules.resumes_v2.tests.conftest import (
    create_real_user,
    insert_analysis_raw,
    insert_resume_v2_raw,
    insert_stats_raw,
    minimal_resume_data_v2,
)


pytestmark = pytest.mark.integration


# ── fixtures specific to the repository ────────────────────────────────────

@pytest.fixture
async def user_id(raw_db: AsyncSession) -> UUID:
    """A real User row in the DB (needed for the resumes_v2 FK)."""
    uid = await create_real_user(raw_db)
    await raw_db.commit()
    return uid


@pytest.fixture
async def repo(raw_db: AsyncSession, user_id: UUID) -> ResumeV2Repository:
    """A repository bound to the RLS user_id of the test user.

    The Wave 1 repository doesn't bind RLS itself; the service layer
    (T021) is expected to call ``set_rls_user_id()`` before invoking
    repo methods. We do the same in the test fixture.
    """
    await set_rls_user_id(raw_db, user_id)
    return ResumeV2Repository(raw_db)


async def _flush(raw_db: AsyncSession) -> None:
    """Flush + rebind RLS — needed after a commit to keep writes passing."""
    await raw_db.flush()


# ── 1. create ──────────────────────────────────────────────────────────────

class TestCreate:
    async def test_create_returns_row_with_version_zero(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        data = minimal_resume_data_v2()
        row = await repo.create(
            user_id=user_id,
            name="Hello",
            slug=f"hello-{secrets.token_hex(4)}",
            data=data,
        )
        await _flush(raw_db)
        assert row.version == 0, f"newly created resume must have version=0, got {row.version}"
        assert row.user_id == user_id
        assert row.name == "Hello"
        assert row.is_public is False
        assert row.is_locked is False
        assert row.password_hash is None


# ── 2. get round-trip ─────────────────────────────────────────────────────

class TestGet:
    async def test_get_round_trips_data(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        data = minimal_resume_data_v2()
        data["summary"]["content"] = "<<<SENTINEL>>>"

        created = await repo.create(
            user_id=user_id,
            name="RoundTrip",
            slug=f"rt-{secrets.token_hex(4)}",
            data=data,
        )
        await _flush(raw_db)

        fetched = await repo.get(created.id, user_id=user_id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.data["summary"]["content"] == "<<<SENTINEL>>>"

    async def test_get_with_wrong_user_returns_none(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        created = await repo.create(
            user_id=user_id,
            name="Hidden",
            slug=f"hidden-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)

        other = await repo.get(created.id, user_id=uuid4())
        assert other is None


# ── 3. list ────────────────────────────────────────────────────────────────

class TestList:
    async def test_list_returns_only_users_own_resumes(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        alice = await create_real_user(raw_db, email=f"alice_{secrets.token_hex(4)}@t.local")
        bob = await create_real_user(raw_db, email=f"bob_{secrets.token_hex(4)}@t.local")
        await raw_db.commit()

        for i in range(3):
            await set_rls_user_id(raw_db, alice)
            await repo.create(
                user_id=alice,
                name=f"Alice {i}",
                slug=f"alice-{i}-{secrets.token_hex(2)}",
                data=minimal_resume_data_v2(),
            )
        for i in range(2):
            await set_rls_user_id(raw_db, bob)
            await repo.create(
                user_id=bob,
                name=f"Bob {i}",
                slug=f"bob-{i}-{secrets.token_hex(2)}",
                data=minimal_resume_data_v2(),
            )
        await _flush(raw_db)

        await set_rls_user_id(raw_db, alice)
        alice_list = await repo.list(alice)
        await set_rls_user_id(raw_db, bob)
        bob_list = await repo.list(bob)

        assert len(alice_list) == 3
        assert len(bob_list) == 2
        assert all(r.user_id == alice for r in alice_list)
        assert all(r.user_id == bob for r in bob_list)

        # Cleanup
        await raw_db.execute(
            sa.text("DELETE FROM users WHERE id IN (:a, :b)"),
            {"a": str(alice), "b": str(bob)},
        )
        await raw_db.commit()


# ── 4. update_with_version ─────────────────────────────────────────────────

class TestUpdateWithVersion:
    async def test_happy_path_bumps_version(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        created = await repo.create(
            user_id=user_id,
            name="ToUpdate",
            slug=f"upd-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)
        assert created.version == 0

        new_data = minimal_resume_data_v2()
        new_data["summary"]["content"] = "updated!"
        new_version = await repo.update_with_version(
            created.id, user_id=user_id, if_match=0, data=new_data, name="Renamed"
        )
        assert new_version == 1

        # Re-fetch and confirm
        await set_rls_user_id(raw_db, user_id)
        fetched = await repo.get(created.id, user_id=user_id)
        assert fetched is not None
        assert fetched.version == 1
        assert fetched.name == "Renamed"
        assert fetched.data["summary"]["content"] == "updated!"

    async def test_conflict_returns_none(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        """A PUT with a stale if_match must return None — the service layer
        uses this signal to build the 409 response with latest_version +
        latest_data from a fresh get()."""
        created = await repo.create(
            user_id=user_id,
            name="Conflict",
            slug=f"conf-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)

        # Bump to v1
        await repo.update_with_version(
            created.id, user_id=user_id, if_match=0, data=minimal_resume_data_v2()
        )
        await _flush(raw_db)

        # Now try with stale v0 — must return None
        result = await repo.update_with_version(
            created.id, user_id=user_id, if_match=0, data=minimal_resume_data_v2()
        )
        assert result is None

    async def test_three_way_version_chain(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        """Verify N -> N+1 works repeatedly and the counter accumulates."""
        created = await repo.create(
            user_id=user_id,
            name="Chain",
            slug=f"chain-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)

        expected = 0
        for i in range(5):
            v = await repo.update_with_version(
                created.id,
                user_id=user_id,
                if_match=expected,
                data=minimal_resume_data_v2(),
            )
            assert v == expected + 1, f"step {i}: expected {expected + 1}, got {v}"
            expected += 1
        assert expected == 5


# ── 5. duplicate ───────────────────────────────────────────────────────────

class TestDuplicate:
    async def test_duplicate_creates_new_uuid_with_version_zero(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        src = await repo.create(
            user_id=user_id,
            name="Source",
            slug=f"src-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)

        new_id = uuid4()
        copy = await repo.duplicate(
            src.id,
            user_id=user_id,
            new_id=new_id,
            new_slug=f"{src.slug}-copy-1",
            new_name="Source (Copy)",
        )
        assert copy is not None
        assert copy.id == new_id
        assert copy.id != src.id
        assert copy.version == 0
        assert copy.user_id == user_id

    async def test_duplicate_deep_copies_data(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        """The copy's data must equal the source's data field-for-field, and
        mutating the copy must NOT affect the source."""
        src_data = minimal_resume_data_v2()
        src_data["summary"]["content"] = "ORIGINAL"
        src = await repo.create(
            user_id=user_id, name="DeepSrc", slug=f"ds-{secrets.token_hex(4)}", data=src_data
        )
        await _flush(raw_db)

        new_id = uuid4()
        copy = await repo.duplicate(
            src.id,
            user_id=user_id,
            new_id=new_id,
            new_slug=f"{src.slug}-copy-1",
            new_name="DeepSrc (Copy)",
        )
        assert copy is not None
        assert copy.data["summary"]["content"] == "ORIGINAL"

        # Deep-copy: mutating the copy must not bleed back
        copy.data["summary"]["content"] = "MUTATED"

        await set_rls_user_id(raw_db, user_id)
        refetched = await repo.get(src.id, user_id=user_id)
        assert refetched is not None
        assert refetched.data["summary"]["content"] == "ORIGINAL", (
            "duplicate() must deep-copy, not share references"
        )

    async def test_duplicate_resets_public_lock_password(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        """Even if the source is public + locked + passworded, the copy
        must come back private + unlocked + no password."""
        src = await repo.create(
            user_id=user_id,
            name="SourceLocked",
            slug=f"sl-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        # Make source public + locked + passworded
        await repo.set_sharing(
            src.id, user_id=user_id, is_public=True, password_hash="$2b$12$abcd"
        )
        await repo.set_lock(src.id, user_id=user_id, is_locked=True)
        await _flush(raw_db)

        copy = await repo.duplicate(
            src.id,
            user_id=user_id,
            new_id=uuid4(),
            new_slug=f"{src.slug}-copy-1",
            new_name="SourceLocked (Copy)",
        )
        assert copy is not None
        assert copy.is_public is False
        assert copy.is_locked is False
        assert copy.password_hash is None

    async def test_duplicate_slug_collides_to_copy_n(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        """If `<slug>-copy-1` already exists, the service must call the repo
        with `<slug>-copy-2`. We simulate the collision by pre-creating copy-1
        and asserting the next call uses -copy-2 as the input.
        """
        src = await repo.create(
            user_id=user_id,
            name="Collide",
            slug=f"cd-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        # Pre-existing -copy-1
        await repo.create(
            user_id=user_id,
            name="Copy 1",
            slug=f"{src.slug}-copy-1",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)

        # Service computes -copy-2 then calls repo
        copy2 = await repo.duplicate(
            src.id,
            user_id=user_id,
            new_id=uuid4(),
            new_slug=f"{src.slug}-copy-2",
            new_name="Collide (Copy)",
        )
        assert copy2 is not None
        assert copy2.slug == f"{src.slug}-copy-2"

    async def test_duplicate_does_not_create_statistics_or_analysis(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        """Per FR-100: a copy must have no statistics row and no analysis row."""
        src = await repo.create(
            user_id=user_id,
            name="WithKids",
            slug=f"wk-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await insert_stats_raw(raw_db, src.id)
        await insert_analysis_raw(raw_db, src.id)
        await _flush(raw_db)

        copy = await repo.duplicate(
            src.id,
            user_id=user_id,
            new_id=uuid4(),
            new_slug=f"{src.slug}-copy-1",
            new_name="WithKids (Copy)",
        )
        assert copy is not None
        await _flush(raw_db)

        stats = await repo.get_statistics(copy.id)
        assert stats is None, "copy must not have a statistics row"

        analysis = await repo.get_analysis(copy.id)
        assert analysis is None, "copy must not have an analysis row"


# ── 6. soft_delete cascades ───────────────────────────────────────────────

class TestSoftDeleteCascade:
    async def test_soft_delete_removes_resume_and_children(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        src = await repo.create(
            user_id=user_id,
            name="ToDelete",
            slug=f"del-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await insert_stats_raw(raw_db, src.id)
        await insert_analysis_raw(raw_db, src.id)
        await _flush(raw_db)

        ok = await repo.soft_delete(src.id, user_id=user_id)
        assert ok is True

        # Resume gone
        await set_rls_user_id(raw_db, user_id)
        result = await repo.get(src.id, user_id=user_id)
        assert result is None

        # Children gone via FK ON DELETE CASCADE
        count_stats = (
            await raw_db.execute(
                sa.text("SELECT COUNT(*) FROM resume_statistics_v2 WHERE resume_id = :rid"),
                {"rid": str(src.id)},
            )
        ).scalar_one()
        count_analysis = (
            await raw_db.execute(
                sa.text("SELECT COUNT(*) FROM resume_analysis_v2 WHERE resume_id = :rid"),
                {"rid": str(src.id)},
            )
        ).scalar_one()
        assert count_stats == 0
        assert count_analysis == 0

    async def test_soft_delete_unknown_returns_false(
        self, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        ok = await repo.soft_delete(uuid4(), user_id=user_id)
        assert ok is False


# ── 7. set_lock ────────────────────────────────────────────────────────────

class TestSetLock:
    async def test_set_lock_toggles_independently_of_version(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        created = await repo.create(
            user_id=user_id,
            name="Lockable",
            slug=f"lk-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)
        v0 = created.version

        ok = await repo.set_lock(created.id, user_id=user_id, is_locked=True)
        assert ok is True
        await _flush(raw_db)
        await set_rls_user_id(raw_db, user_id)
        refetched = await repo.get(created.id, user_id=user_id)
        assert refetched is not None
        assert refetched.is_locked is True
        assert refetched.version == v0, "set_lock must not bump version"

        ok = await repo.set_lock(created.id, user_id=user_id, is_locked=False)
        assert ok is True
        await _flush(raw_db)
        await set_rls_user_id(raw_db, user_id)
        refetched = await repo.get(created.id, user_id=user_id)
        assert refetched is not None
        assert refetched.is_locked is False
        assert refetched.version == v0


# ── 8. set_sharing ────────────────────────────────────────────────────────

class TestSetSharing:
    async def test_set_sharing_sets_public_and_password(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        created = await repo.create(
            user_id=user_id,
            name="Sharable",
            slug=f"sh-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)

        ok = await repo.set_sharing(
            created.id,
            user_id=user_id,
            is_public=True,
            password_hash="$2b$12$abc",
        )
        assert ok is True
        await _flush(raw_db)

        await set_rls_user_id(raw_db, user_id)
        refetched = await repo.get(created.id, user_id=user_id)
        assert refetched is not None
        assert refetched.is_public is True
        assert refetched.password_hash == "$2b$12$abc"

    async def test_set_sharing_clears_password_when_none(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        created = await repo.create(
            user_id=user_id,
            name="ClearPwd",
            slug=f"cp-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await repo.set_sharing(
            created.id,
            user_id=user_id,
            is_public=True,
            password_hash="$2b$12$xyz",
        )
        await _flush(raw_db)

        ok = await repo.set_sharing(
            created.id, user_id=user_id, is_public=True, password_hash=None
        )
        assert ok is True
        await _flush(raw_db)

        await set_rls_user_id(raw_db, user_id)
        refetched = await repo.get(created.id, user_id=user_id)
        assert refetched is not None
        assert refetched.password_hash is None
        assert refetched.is_public is True, "is_public must remain true even when password cleared"

    async def test_set_sharing_rejects_password_when_private(
        self, raw_db: AsyncSession, repo: ResumeV2Repository, user_id: UUID
    ) -> None:
        """The DB CHECK constraint guards this — `password_hash IS NULL OR is_public = true`."""
        from sqlalchemy.exc import IntegrityError

        created = await repo.create(
            user_id=user_id,
            name="BadShare",
            slug=f"bs-{secrets.token_hex(4)}",
            data=minimal_resume_data_v2(),
        )
        await _flush(raw_db)

        with pytest.raises(IntegrityError):
            await repo.set_sharing(
                created.id, user_id=user_id, is_public=False, password_hash="$2b$12$wontfly"
            )
            await _flush(raw_db)
        await raw_db.rollback()
