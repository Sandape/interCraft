"""InterCraft backend package.

On Windows, psycopg (used by langgraph-checkpoint-postgres) requires
SelectorEventLoop. We set the policy here — before any psycopg import
— so every subprocess (including uvicorn reloaders) gets the right loop.
"""
import platform
import sys

if platform.system() == "Windows":
    import asyncio
    import selectors

    # Force SelectorEventLoop regardless of current policy — psycopg's
    # check inspects the running loop, and set_event_loop_policy only
    # affects *new* loops. But we also force-set it to be safe.
    if isinstance(
        asyncio.get_event_loop_policy(),
        asyncio.WindowsProactorEventLoopPolicy,
    ):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Also set a per-process env hint that some psycopg versions respect
    sys.modules.setdefault("asyncio", asyncio)

__version__ = "0.3.0"
