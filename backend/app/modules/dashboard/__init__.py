"""REQ-057 — Dashboard command-center summary aggregation."""

from __future__ import annotations

__all__ = ["router"]


def __getattr__(name: str):
    if name == "router":
        from app.modules.dashboard.api import router

        return router
    raise AttributeError(name)
