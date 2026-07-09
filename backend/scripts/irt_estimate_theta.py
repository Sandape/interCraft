"""Standalone entry point for IRT θ estimation (REQ-030 US1).

Enables: `python -m scripts.irt_estimate_theta --user-id <uuid> --dimension <key>`

This is a thin wrapper over `app.modules.irt.cli:estimate_theta` so
debug / calibration scripts can call θ estimation without going
through the FastAPI stack or the ARQ worker. Output format matches
the CLI: one key=value line per dimension.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `app.*` importable when running from backend/ root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.modules.irt.cli import cli  # noqa: E402

if __name__ == "__main__":
    cli()
