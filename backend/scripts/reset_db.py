"""Reset all tables in the configured database (refuses on production).

Strategy: alembic downgrade base + alembic upgrade head. This drops and
re-creates all 6 tables + RLS policies without dropping the database
itself (safer on shared Postgres instances where the user lacks CREATEDB).

Idempotent. Run via:
    uv run python scripts/reset_db.py --yes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402


def _abort_if_production() -> None:
    s = get_settings()
    if s.app_env == "production":
        raise SystemExit("refusing to reset DB when APP_ENV=production")
    if "PLACEHOLDER" in s.database_url:
        raise SystemExit("DATABASE_URL is a placeholder. Configure backend/.env first.")


def _run_alembic_subprocess(args: list[str]) -> None:
    """Run alembic via subprocess (its env.py calls asyncio.run() at import)."""
    import subprocess

    cmd = ["uv", "run", "alembic", *args]
    res = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if res.returncode != 0:
        raise SystemExit(f"alembic {' '.join(args)} failed (rc={res.returncode})")


def run(*, yes: bool = False) -> None:
    _abort_if_production()
    if not yes:
        ans = input("Drop all tables and re-run migrations? Type 'yes' to continue: ")
        if ans.strip() != "yes":
            print("aborted")
            return
    _run_alembic_subprocess(["downgrade", "base"])
    print("reset_db: downgrade base OK")
    _run_alembic_subprocess(["upgrade", "head"])
    print("reset_db: upgrade head OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    run(yes=args.yes)
