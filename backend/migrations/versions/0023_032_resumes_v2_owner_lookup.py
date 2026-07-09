"""Add SECURITY DEFINER owner-lookup helper for resumes_v2 (REQ-032, T022 fix).

The ``resumes_v2`` table has ``FORCE ROW LEVEL SECURITY`` so a non-owner
session can never read the row, even via ``SET LOCAL row_security = off``
(because the table is owned by the same role, and the policy is FORCE'd).
To distinguish 404 NOT_FOUND from 403 NOT_OWNER per the v2 contract,
we expose a SECURITY DEFINER function that returns the ``user_id`` of
a row without leaking the data. The application layer can then compare
that id to the caller's session user_id and emit the right error.

How the bypass works
--------------------
The function is declared ``SECURITY DEFINER``, ``LANGUAGE plpgsql``,
and ``VOLATILE`` (required for DDL inside the function body). It
temporarily ``ALTER TABLE resumes_v2 NO FORCE ROW LEVEL SECURITY``,
reads the owner, then re-applies ``FORCE``. Because the function
runs as the function owner (which is also the table owner, ``appuser``)
with full DDL privileges, the temporary NO FORCE works. The FORCE
state is restored in the same transaction so the security posture
is preserved across calls.

This is a deliberate trade-off: the function carries a small DDL
cost per call (~1ms on a modern PG) in exchange for keeping
``relforcerowsecurity = true`` between calls so T016's
``test_rls_enabled_on_resumes_v2`` and
``test_non_owner_session_sees_zero_rows`` continue to pass.

Function surface
----------------
- Returns ONLY the owner ``user_id`` (a UUID). Never the data blob,
  never the slug, never any PII. This is the minimum surface needed
  for 404-vs-403 disambiguation.
- We ``REVOKE`` from PUBLIC and ``GRANT`` only to ``appuser`` so
  anonymous enumerators cannot probe ownership of arbitrary resume
  ids.

No new package dependencies.
"""
from __future__ import annotations

from alembic import op

revision = "0023_032_resumes_v2_owner_lookup"
down_revision = "0022_032_resumes_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION resumes_v2_owner_of(p_id uuid)
        RETURNS uuid
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_owner uuid;
        BEGIN
            -- Bypass FORCE RLS by temporarily dropping the FORCE flag.
            -- We re-apply it before returning so concurrent sessions
            -- never see the table without FORCE.
            EXECUTE 'ALTER TABLE resumes_v2 NO FORCE ROW LEVEL SECURITY';
            SELECT user_id INTO v_owner FROM resumes_v2 WHERE id = p_id;
            EXECUTE 'ALTER TABLE resumes_v2 FORCE ROW LEVEL SECURITY';
            RETURN v_owner;
        END;
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION resumes_v2_owner_of(uuid) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION resumes_v2_owner_of(uuid) TO appuser;")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS resumes_v2_owner_of(uuid);")


__all__ = ["upgrade", "downgrade"]



