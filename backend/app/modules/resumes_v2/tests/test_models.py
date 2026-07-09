"""T016 — Resume v2 ORM model tests.

Covers:
- Table columns exist with correct types
- `version` default is 0
- `password_hash` is nullable
- CHECK constraint `password_hash IS NULL OR is_public = true`
- Cascade delete from user -> resumes_v2 -> statistics + analysis
- RLS policy is active (a non-owner session sees 0 rows)
- Indexes `idx_resumes_v2_user_updated` and `uq_resumes_v2_user_slug` exist

All tests use the real PostgreSQL database (migration 0022 already applied).
We do NOT mock the DB. Failures here mean either (a) the migration drift
detected a column/index difference, or (b) the cascade / RLS behavior is
broken — both are storage-layer contract bugs.

T016 — authored in Wave 2, awaiting US1 implementation. The 16 endpoint
stubs return 501, but model-level tests should pass once migration 0022
is applied and the ORM models are wired (which it is).
"""
from __future__ import annotations

import secrets
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resumes_v2.tests.conftest import (
    create_real_user,
    insert_analysis_raw,
    insert_resume_v2_raw,
    insert_stats_raw,
    minimal_resume_data_v2,
)


pytestmark = pytest.mark.integration


# ── 1. Table columns exist with correct types ──────────────────────────────

class TestResumeV2Columns:
    async def test_resumes_v2_columns_present(self, raw_db: AsyncSession) -> None:
        """All FR-001 columns must exist on resumes_v2."""
        expected = {
            "id", "user_id", "name", "slug", "tags",
            "is_public", "is_locked", "password_hash",
            "data", "version", "created_at", "updated_at",
        }
        result = await raw_db.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'resumes_v2'"
            )
        )
        cols = {row[0] for row in result.all()}
        missing = expected - cols
        assert not missing, f"resumes_v2 missing columns: {missing}"

    async def test_resume_statistics_v2_columns_present(self, raw_db: AsyncSession) -> None:
        result = await raw_db.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'resume_statistics_v2'"
            )
        )
        cols = {row[0] for row in result.all()}
        assert {"resume_id", "views", "downloads", "last_viewed_at", "last_downloaded_at"} <= cols

    async def test_resume_analysis_v2_columns_present(self, raw_db: AsyncSession) -> None:
        result = await raw_db.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'resume_analysis_v2'"
            )
        )
        cols = {row[0] for row in result.all()}
        assert {"resume_id", "analysis", "status", "failure_reason", "updated_at"} <= cols


# ── 2. version default is 0 ────────────────────────────────────────────────

class TestVersionDefault:
    async def test_version_default_zero(self, raw_db: AsyncSession) -> None:
        """Insert without specifying version must yield version=0."""
        from app.core.db import set_rls_user_id

        uid = await create_real_user(raw_db)
        await raw_db.commit()

        rid = await insert_resume_v2_raw(raw_db, user_id=uid, name="Version Default")
        await raw_db.commit()

        # Rebind RLS — the SET LOCAL from create_real_user is gone after commit.
        await set_rls_user_id(raw_db, uid)
        result = await raw_db.execute(
            sa.text("SELECT version FROM resumes_v2 WHERE id = :id"), {"id": str(rid)}
        )
        version = result.scalar_one()
        assert version == 0, f"version default should be 0, got {version}"

        # Cleanup
        await raw_db.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
        await raw_db.commit()

    async def test_version_column_is_not_null(self, raw_db: AsyncSession) -> None:
        result = await raw_db.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'resumes_v2' AND column_name = 'version'"
            )
        )
        is_nullable = result.scalar_one()
        assert is_nullable == "NO", "version column must be NOT NULL"


# ── 3. password_hash nullable + CHECK constraint ──────────────────────────

class TestPasswordHashConstraint:
    async def test_password_hash_is_nullable(self, raw_db: AsyncSession) -> None:
        result = await raw_db.execute(
            sa.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'resumes_v2' AND column_name = 'password_hash'"
            )
        )
        assert result.scalar_one() == "YES", "password_hash must be nullable"

    async def test_check_constraint_password_only_when_public(
        self, raw_db: AsyncSession
    ) -> None:
        """Insert with password_hash set AND is_public=false must be rejected."""
        uid = await create_real_user(raw_db)
        await raw_db.commit()

        with pytest.raises(IntegrityError):
            await insert_resume_v2_raw(
                raw_db,
                user_id=uid,
                name="Bad Pwd",
                is_public=False,
                password_hash="$2b$12$" + secrets.token_hex(22),
            )
            await raw_db.flush()
        await raw_db.rollback()

        # Cleanup user
        await raw_db.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
        await raw_db.commit()

    async def test_password_with_is_public_true_accepted(
        self, raw_db: AsyncSession
    ) -> None:
        """Insert with password_hash + is_public=true must succeed."""
        from app.core.db import set_rls_user_id

        uid = await create_real_user(raw_db)
        await raw_db.commit()

        rid = await insert_resume_v2_raw(
            raw_db,
            user_id=uid,
            name="Public With Pwd",
            is_public=True,
            password_hash="$2b$12$" + secrets.token_hex(22),
        )
        await raw_db.commit()

        # Rebind RLS for the post-commit SELECT
        await set_rls_user_id(raw_db, uid)
        result = await raw_db.execute(
            sa.text("SELECT is_public, password_hash IS NOT NULL FROM resumes_v2 WHERE id = :id"),
            {"id": str(rid)},
        )
        is_public, has_pwd = result.one()
        assert is_public is True
        assert has_pwd is True

        # Cleanup
        await raw_db.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
        await raw_db.commit()

    async def test_no_password_with_is_public_true_accepted(
        self, raw_db: AsyncSession
    ) -> None:
        """Public resume with NULL password_hash is fine (data-model.md §2)."""
        from app.core.db import set_rls_user_id

        uid = await create_real_user(raw_db)
        await raw_db.commit()

        rid = await insert_resume_v2_raw(
            raw_db, user_id=uid, name="Public No Pwd", is_public=True, password_hash=None
        )
        await raw_db.commit()

        await set_rls_user_id(raw_db, uid)
        result = await raw_db.execute(
            sa.text("SELECT is_public FROM resumes_v2 WHERE id = :id"), {"id": str(rid)}
        )
        assert result.scalar_one() is True

        # Cleanup
        await raw_db.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
        await raw_db.commit()


# ── 4. Cascade delete from user ────────────────────────────────────────────

class TestCascadeDelete:
    async def test_user_delete_cascades_to_resume_and_children(
        self, raw_db: AsyncSession
    ) -> None:
        """Deleting a user must CASCADE to their resumes + statistics + analysis."""
        from app.core.db import set_rls_user_id

        # Pre-create a real user; the raw insert flow handles the chicken-and-egg
        # by binding RLS to the new id before INSERT.
        uid = await create_real_user(raw_db)
        await raw_db.commit()

        rid = await insert_resume_v2_raw(raw_db, user_id=uid, name="Cascade Test")
        await insert_stats_raw(raw_db, rid)
        await insert_analysis_raw(raw_db, rid)
        await raw_db.commit()

        # Rebind RLS for the post-commit SELECTs (SET LOCAL is tx-scoped)
        await set_rls_user_id(raw_db, uid)

        # Pre-check: rows exist
        for table, col in (
            ("resumes_v2", "id"),
            ("resume_statistics_v2", "resume_id"),
            ("resume_analysis_v2", "resume_id"),
        ):
            count = (
                await raw_db.execute(
                    sa.text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :rid"),
                    {"rid": str(rid)},
                )
            ).scalar_one()
            assert count == 1, f"{table} should have 1 row before delete"

        # Delete the user — must cascade to resume + children.
        # NOTE: RLS on users table requires app.user_id to be a valid UUID OR
        # for the deletion to come from a "service role" connection. Since we
        # bound RLS to the user being deleted, the DELETE works (the user
        # passes the WITH CHECK).
        await raw_db.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
        await raw_db.commit()

        # Rebind for the post-check (though the rows should be gone)
        await set_rls_user_id(raw_db, uid)

        # Post-check: all gone
        for table, col in (
            ("resumes_v2", "id"),
            ("resume_statistics_v2", "resume_id"),
            ("resume_analysis_v2", "resume_id"),
        ):
            count = (
                await raw_db.execute(
                    sa.text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :rid"),
                    {"rid": str(rid)},
                )
            ).scalar_one()
            assert count == 0, f"{table} still has rows after user delete (cascade broken)"


# ── 5. RLS policy is active ────────────────────────────────────────────────

class TestRlsPolicyActive:
    async def test_rls_enabled_on_resumes_v2(self, raw_db: AsyncSession) -> None:
        """The migration must have enabled RLS and forced it on resumes_v2."""
        result = await raw_db.execute(
            sa.text(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname = 'resumes_v2'"
            )
        )
        rls_enabled, rls_forced = result.one()
        assert rls_enabled is True, "RLS must be enabled on resumes_v2"
        assert rls_forced is True, "RLS must be forced on resumes_v2 (so owner is also gated)"

    async def test_rls_policy_named_correctly(self, raw_db: AsyncSession) -> None:
        result = await raw_db.execute(
            sa.text(
                "SELECT policyname FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = 'resumes_v2'"
            )
        )
        names = {row[0] for row in result.all()}
        assert "resumes_v2_user_isolation" in names, (
            f"expected resumes_v2_user_isolation policy, got {names}"
        )

    async def test_non_owner_session_sees_zero_rows(
        self, raw_db: AsyncSession
    ) -> None:
        """When a session binds app.user_id to a user that did NOT own the row,
        the row must be invisible (USING clause enforces user_id match)."""
        from app.core.db import _session_cm, set_rls_user_id

        owner_id = await create_real_user(raw_db)
        await raw_db.commit()
        rid = await insert_resume_v2_raw(raw_db, user_id=owner_id, name="Owned by A")
        await raw_db.commit()

        # Open a fresh session and bind app.user_id to a DIFFERENT (real) user
        other_id = await create_real_user(raw_db, email=f"other_{secrets.token_hex(4)}@test.local")
        await raw_db.commit()

        async with _session_cm() as other_session:
            await set_rls_user_id(other_session, other_id)
            count = (
                await other_session.execute(
                    sa.text("SELECT COUNT(*) FROM resumes_v2 WHERE id = :rid"),
                    {"rid": str(rid)},
                )
            ).scalar_one()
            assert count == 0, "RLS must hide the row from a non-owner session"

        # Cleanup
        await raw_db.execute(
            sa.text("DELETE FROM users WHERE id IN (:a, :b)"),
            {"a": str(owner_id), "b": str(other_id)},
        )
        await raw_db.commit()

    async def test_owner_session_sees_their_row(
        self, raw_db: AsyncSession
    ) -> None:
        """When a session binds app.user_id to the OWNER, the row must be visible."""
        from app.core.db import _session_cm, set_rls_user_id

        owner_id = await create_real_user(raw_db)
        await raw_db.commit()
        rid = await insert_resume_v2_raw(raw_db, user_id=owner_id, name="Owned visible")
        await raw_db.commit()

        async with _session_cm() as owner_session:
            await set_rls_user_id(owner_session, owner_id)
            count = (
                await owner_session.execute(
                    sa.text("SELECT COUNT(*) FROM resumes_v2 WHERE id = :rid"),
                    {"rid": str(rid)},
                )
            ).scalar_one()
            assert count == 1, "Owner must see their own row"

        await raw_db.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": str(owner_id)})
        await raw_db.commit()


# ── 6. Indexes ─────────────────────────────────────────────────────────────

class TestIndexes:
    async def test_user_updated_index_exists(self, raw_db: AsyncSession) -> None:
        result = await raw_db.execute(
            sa.text("SELECT indexname FROM pg_indexes WHERE tablename = 'resumes_v2'")
        )
        names = {row[0] for row in result.all()}
        # The migration uses idx_resumes_v2_user_updated
        assert "idx_resumes_v2_user_updated" in names, (
            f"expected idx_resumes_v2_user_updated in {names}"
        )

    async def test_unique_user_slug_constraint_exists(self, raw_db: AsyncSession) -> None:
        result = await raw_db.execute(
            sa.text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'resumes_v2'::regclass AND contype = 'u'"
            )
        )
        names = {row[0] for row in result.all()}
        assert "uq_resumes_v2_user_slug" in names, (
            f"expected UNIQUE (user_id, slug) constraint, got {names}"
        )

    async def test_unique_user_slug_prevents_collision(
        self, raw_db: AsyncSession
    ) -> None:
        """Two rows with the same (user_id, slug) must violate the unique index."""
        uid = await create_real_user(raw_db)
        await raw_db.commit()
        slug = f"collide-{secrets.token_hex(4)}"
        await insert_resume_v2_raw(raw_db, user_id=uid, name="First", slug=slug)
        await raw_db.commit()
        with pytest.raises(IntegrityError):
            await insert_resume_v2_raw(raw_db, user_id=uid, name="Second", slug=slug)
            await raw_db.flush()
        await raw_db.rollback()
        # Cleanup
        await raw_db.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
        await raw_db.commit()
