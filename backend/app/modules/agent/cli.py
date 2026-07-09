"""Agent CLI — REQ-052 FR-025 + REQ-054 parse-intent / simulate-chat.

Usage:
  uv run python -m app.modules.agent.cli send-test-message <user_id> <text>
  uv run python -m app.modules.agent.cli agent-status <user_id>
  uv run python -m app.modules.agent.cli list-bindings
  uv run python -m app.modules.agent.cli parse-intent "<message>" [--json]
  uv run python -m app.modules.agent.cli simulate-chat <user_id> [--json-lines]
"""

from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace
from uuid import UUID

from app.channels.message_handler import enqueue_outbound_message
from app.core.db import get_session_context
from app.modules.agent.service import AgentService


async def _send_test_message(user_id: str, text: str) -> None:
    """Send a test message to a user's WeChat."""
    uid = UUID(user_id)
    async with get_session_context(user_id=uid) as session:
        message_ids = await enqueue_outbound_message(
            uid, text, session=session, priority="high",
        )
        print(f"Message queued: {len(message_ids)} segment(s)")
        for mid in message_ids:
            print(f"  message_id: {mid}")


async def _agent_status(user_id: str) -> None:
    """Show Agent status for a user."""
    uid = UUID(user_id)
    async with get_session_context(user_id=uid) as session:
        svc = AgentService(session)
        status = await svc.get_agent_status(uid)
        print(f"user_id:           {status['user_id']}")
        print(f"status:            {status['status']}")
        print(f"display_name:      {status['display_name']}")
        print(f"wechat_bound:      {status['wechat_bound']}")
        print(f"last_heartbeat_at: {status['last_heartbeat_at']}")
        print(f"messages_sent:     {status['messages_sent_total']}")
        print(f"messages_received: {status['messages_received_total']}")


async def _list_bindings() -> None:
    """List all WeChat bindings (admin-only, bypasses RLS via SECURITY DEFINER)."""
    from app.core.db import get_db_session_no_rls
    from sqlalchemy import text as sa_text

    async for session in get_db_session_no_rls():
        await session.execute(sa_text("""
            CREATE OR REPLACE FUNCTION list_all_agents()
            RETURNS TABLE(
                user_id uuid, status text, wechat_uin text,
                last_heartbeat_at timestamptz, updated_at timestamptz
            )
            LANGUAGE sql STABLE SECURITY DEFINER
            AS $$ SELECT a.user_id, a.status, a.wechat_uin, a.last_heartbeat_at, a.updated_at
                  FROM public.agents a ORDER BY a.updated_at DESC $$
        """))
        await session.commit()
        break

    async for session in get_db_session_no_rls():
        result = await session.execute(
            sa_text("SELECT * FROM list_all_agents() LIMIT 100"),
        )
        rows = result.fetchall()
        if not rows:
            print("No agents found.")
            return
        print(f"{'USER_ID':<38} {'STATUS':<10} {'WECHAT_UIN':<30} {'LAST_HEARTBEAT'}")
        print("-" * 100)
        for row in rows:
            uid = str(row[0])
            status = row[1] or "-"
            uin = (row[2] or "-")[:28]
            hb = str(row[3])[:19] if row[3] else "-"
            print(f"{uid:<38} {status:<10} {uin:<30} {hb}")
        print(f"\nTotal: {len(rows)} agent(s)")
        break


async def _parse_intent(message: str, *, as_json: bool) -> int:
    """Parse intent without executing tools (REQ-054). Exit 2 if LLM unavailable."""
    from app.modules.agent.conversation.intent_parser import IntentParser

    # Synthetic user_id for quota/audit — CLI parse does not need a real user
    # when LLM is mocked; production still needs a valid UUID string.
    fake_uid = "00000000-0000-0000-0000-000000000001"
    parser = IntentParser()
    result = await parser.parse(message, user_id=fake_uid)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"intent:     {result.get('intent')}")
        print(f"confidence: {result.get('confidence')}")
        print(f"entities:   {json.dumps(result.get('entities') or {}, ensure_ascii=False)}")
        if result.get("alternatives"):
            print(f"alts:       {json.dumps(result['alternatives'], ensure_ascii=False)}")
        if result.get("error"):
            print(f"error:      {result['error']}")
    if result.get("error") == "llm_unavailable":
        return 2
    return 0


async def _simulate_chat(user_id: str, *, json_lines: bool) -> int:
    """Interactive REPL through ConversationOrchestrator (no iLink).

    WARNING: write ops (create/status) hit the real DB after confirmation.
    """
    from app.modules.agent.conversation import ConversationOrchestrator

    uid = UUID(user_id)
    print(
        "simulate-chat — 输入消息后回车；quit / EOF 退出。"
        "写操作确认后会真实写入数据库。",
        file=sys.stderr,
    )
    try:
        async with get_session_context(user_id=uid) as session:
            # Verify user exists via agent ensure
            svc = AgentService(session)
            await svc.ensure_agent_exists(uid)
    except Exception as exc:
        print(f"User load failed: {exc}", file=sys.stderr)
        return 1

    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            return 0
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            return 0
        async with get_session_context(user_id=uid) as session:
            orch = ConversationOrchestrator(session, uid)
            parsed = SimpleNamespace(text=line, context_token=None, from_user_id=None)
            reply = await orch.handle(parsed)
            await session.commit()
        if json_lines:
            print(json.dumps({"user": line, "reply": reply}, ensure_ascii=False))
        else:
            print(reply)
            print("---")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m app.modules.agent.cli send-test-message <user_id> <text>")
        print("  python -m app.modules.agent.cli agent-status <user_id>")
        print("  python -m app.modules.agent.cli list-bindings")
        print("  python -m app.modules.agent.cli parse-intent \"<message>\" [--json]")
        print("  python -m app.modules.agent.cli simulate-chat <user_id> [--json-lines]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "send-test-message":
        if len(sys.argv) < 4:
            print("Usage: send-test-message <user_id> <text>")
            sys.exit(1)
        user_id = sys.argv[2]
        text = " ".join(sys.argv[3:])
        asyncio.run(_send_test_message(user_id, text))

    elif cmd == "agent-status":
        if len(sys.argv) < 3:
            print("Usage: agent-status <user_id>")
            sys.exit(1)
        user_id = sys.argv[2]
        asyncio.run(_agent_status(user_id))

    elif cmd == "list-bindings":
        asyncio.run(_list_bindings())

    elif cmd == "parse-intent":
        args = sys.argv[2:]
        as_json = "--json" in args
        args = [a for a in args if a != "--json"]
        if not args:
            print('Usage: parse-intent "<message>" [--json]')
            sys.exit(1)
        message = " ".join(args)
        code = asyncio.run(_parse_intent(message, as_json=as_json))
        sys.exit(code)

    elif cmd == "simulate-chat":
        if len(sys.argv) < 3:
            print("Usage: simulate-chat <user_id> [--json-lines]")
            sys.exit(1)
        user_id = sys.argv[2]
        json_lines = "--json-lines" in sys.argv[3:]
        code = asyncio.run(_simulate_chat(user_id, json_lines=json_lines))
        sys.exit(code)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
