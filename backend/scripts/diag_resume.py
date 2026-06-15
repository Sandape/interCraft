"""Diagnose why HTTP /resume returns empty state when direct graph call works."""
import asyncio
import re
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agents.checkpointer import get_graph_config
from app.agents.interview.graph import get_interview_graph
from app.core.db import get_session_factory
from app.modules.interviews.repository import InterviewSessionRepository
from app.modules.interviews.service import InterviewSessionService
from app.domain.rls import set_user_context


async def main() -> None:
    sid = "d0ace8b2-9698-4b78-87be-d385bc95e75b"
    user_id = "019ec72b-09d0-781d-b1d4-1e3cfba84660"

    print("=" * 60)
    print("Step 1: Read session from DB")
    print("=" * 60)
    factory = get_session_factory()
    async with factory() as db:
        await set_user_context(db, user_id)
        repo = InterviewSessionRepository(db)
        session = await repo.get(UUID(sid), UUID(user_id))
        print(f"  session.thread_id = {session.thread_id!r}")
        print(f"  session.id        = {session.id}")
        print(f"  session.status    = {session.status}")

    print()
    print("=" * 60)
    print("Step 2: Direct graph.get_current_state (sid)")
    print("=" * 60)
    graph = get_interview_graph()
    direct = await graph.get_current_state(sid)
    print(f"  current_question = {direct.get('current_question')}")
    print(f"  next             = {direct.get('next')}")
    print(f"  values keys      = {list(direct.get('values', {}).keys())}")
    print(f"  questions count  = {len(direct.get('values', {}).get('questions', []))}")
    print(f"  scores count     = {len(direct.get('values', {}).get('scores', []))}")
    print(f"  messages count   = {len(direct.get('values', {}).get('messages', []))}")

    print()
    print("=" * 60)
    print("Step 3: Through InterviewSessionService.resume (HTTP path)")
    print("=" * 60)
    async with factory() as db:
        await set_user_context(db, user_id)
        svc = InterviewSessionService(db)
        try:
            result = await svc.resume(UUID(sid), UUID(user_id))
            print(f"  result type      = {type(result)}")
            print(f"  result keys      = {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            print(f"  current_question = {result.get('current_question')}")
            print(f"  next             = {result.get('next')}")
            values = result.get('values', {})
            print(f"  values keys      = {list(values.keys())}")
            print(f"  questions count  = {len(values.get('questions', []))}")
            print(f"  scores count     = {len(values.get('scores', []))}")
            print(f"  messages count   = {len(values.get('messages', []))}")
        except Exception as exc:
            print(f"  EXCEPTION: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
