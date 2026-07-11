"""Agent CLI — REQ-052 FR-025 + REQ-054/060 dev ingress.

Usage:
  uv run python -m app.modules.agent.cli chat <user_id> --text "..." [--json] [--idempotency-key KEY]
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
from uuid import UUID, uuid4

from app.channels.message_handler import enqueue_outbound_message
from app.core.db import get_session_context
from app.main import app as _fastapi_app  # noqa: F401 — register all ORM models for CLI
from app.modules.agent.service import AgentService, DevChatResult, DevInboundError


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
    """Legacy cross-tenant listing is disabled; use authenticated admin API."""
    print("list-bindings is disabled; use the authenticated admin API.", file=sys.stderr)


async def _consumer_status(*, as_json: bool) -> int:
    from datetime import datetime, timezone

    from app.core.config import get_settings
    from app.modules.agent.models import WeChatConsumerLease
    from app.modules.agent.runtime.telemetry import privacy_ref

    settings = get_settings()
    payload: dict[str, object] = {
        "enabled": settings.wechat_agent_consumer_enabled,
        "state": "disabled",
    }
    if settings.wechat_agent_consumer_enabled:
        async with get_session_context() as session:
            lease = await session.get(WeChatConsumerLease, "wechat-agent-ilink")
        active = bool(lease and lease.owner_id and lease.lease_until and lease.lease_until > datetime.now(timezone.utc))
        payload = {
            "enabled": True,
            "state": "active" if active else "standby",
            "owner_ref": privacy_ref(str(lease.owner_id), salt=settings.master_key) if active else None,
            "fencing_token": lease.fencing_token if active else None,
            "lease_until": lease.lease_until.isoformat() if active else None,
        }
    print(json.dumps(payload, ensure_ascii=False) if as_json else " ".join(f"{k}={v}" for k, v in payload.items()))
    return 0


async def _consumer_lease_probe(*, as_json: bool) -> int:
    """Exercise acquire/renew/fence/release without exposing the runtime owner."""
    from app.channels.consumer_lease import ConsumerLeaseManager
    from app.core.config import get_settings

    settings = get_settings()
    manager = ConsumerLeaseManager(ttl_seconds=settings.wechat_agent_lease_ttl_seconds)
    owner_id = uuid4()
    fencing_token: int | None = None
    payload: dict[str, object] = {
        "status": "failed",
        "acquired": False,
        "renewed": False,
        "fence_valid": False,
        "released": False,
        "fencing_token": None,
    }
    try:
        acquired = await manager.try_acquire_or_renew(owner_id)
        payload["acquired"] = acquired.acquired
        fencing_token = acquired.fencing_token
        payload["fencing_token"] = fencing_token
        if not acquired.acquired or fencing_token is None:
            _print_cli_payload(payload, as_json=as_json)
            return 1

        renewed = await manager.try_acquire_or_renew(
            owner_id, expected_fencing_token=fencing_token
        )
        payload["renewed"] = bool(
            renewed.acquired and renewed.fencing_token == fencing_token
        )
        payload["fence_valid"] = await manager.validate_fence(
            owner_id, fencing_token
        )
    except Exception as exc:
        print(
            f"consumer lease probe failed: {type(exc).__name__}",
            file=sys.stderr,
        )
    finally:
        if fencing_token is not None:
            try:
                payload["released"] = await manager.release(
                    owner_id, fencing_token
                )
            except Exception as exc:
                print(
                    f"consumer lease release failed: {type(exc).__name__}",
                    file=sys.stderr,
                )

    passed = all(
        payload[key]
        for key in ("acquired", "renewed", "fence_valid", "released")
    )
    payload["status"] = "passed" if passed else "failed"
    _print_cli_payload(payload, as_json=as_json)
    return 0 if passed else 1


def _print_cli_payload(payload: dict[str, object], *, as_json: bool) -> None:
    print(
        json.dumps(payload, ensure_ascii=False)
        if as_json
        else " ".join(f"{key}={value}" for key, value in payload.items())
    )


def _list_tools(*, as_json: bool) -> int:
    from app.modules.agent.tools.factory import build_production_registry

    registry = build_production_registry()
    payload = [registry.describe(name) for name in registry.names()]
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for item in payload:
            print(f"{item['name']} {item['version']} {item['side_effect']} confirmation={item['confirmation']}")
    return 0


async def _task_command(command: str, task_id: str, user_id: str, *, as_json: bool) -> int:
    from app.modules.agent.repository import AgentTaskRepository

    uid = UUID(user_id)
    tid = UUID(task_id)
    async with get_session_context(user_id=uid) as session:
        repo = AgentTaskRepository(session)
        if command == "task-status":
            row = await repo.get_by_id(uid, tid)
        elif command == "task-cancel":
            row = await repo.request_cancel(uid, tid)
        else:
            row = await repo.resume_task(uid, tid)
    if row is None:
        return 3 if command == "task-status" else 4
    payload = {"id": str(row.id), "status": row.status, "stage": row.stage}
    print(json.dumps(payload, ensure_ascii=False) if as_json else " ".join(f"{k}={v}" for k, v in payload.items()))
    return 0


async def _replay_message(message_id: str, user_id: str, *, as_json: bool) -> int:
    from app.modules.agent.repository import AgentTaskRepository

    uid = UUID(user_id)
    mid = UUID(message_id)
    async with get_session_context(user_id=uid) as session:
        replay = await AgentTaskRepository(session).replay_message(uid, mid)
    if replay is None:
        return 4
    payload = {
        "id": str(replay.id),
        "status": replay.status,
        "stage": replay.stage,
        "resume_from_task_id": str(replay.resume_from_task_id),
    }
    _print_cli_payload(payload, as_json=as_json)
    return 0


async def _reconcile_delivery(
    message_id: str, user_id: str, *, as_json: bool
) -> int:
    """Inspect an owner-scoped delivery without guessing an ambiguous result."""
    from sqlalchemy import select

    from app.modules.agent.models import AgentMessage

    uid = UUID(user_id)
    mid = UUID(message_id)
    async with get_session_context(user_id=uid) as session:
        row = await session.scalar(
            select(AgentMessage).where(
                AgentMessage.id == mid,
                AgentMessage.user_id == uid,
                AgentMessage.direction == "outbound",
            )
        )
    if row is None:
        return 3
    unresolved = row.delivery_status == "unknown_delivery"
    payload = {
        "id": str(row.id),
        "delivery_status": row.delivery_status,
        "attempt_count": row.attempt_count,
        "error_category": row.error_category,
        "reconciliation": (
            "manual_confirmation_required" if unresolved else "not_required"
        ),
        "mutated": False,
    }
    _print_cli_payload(payload, as_json=as_json)
    return 5 if unresolved else 0


async def _dead_letter_status(user_id: str, *, as_json: bool) -> int:
    from sqlalchemy import func, select

    from app.modules.agent.models import (
        AgentCommandOutbox,
        AgentTask,
        WeChatInbox,
    )

    uid = UUID(user_id)
    async with get_session_context(user_id=uid) as session:
        task_count = await session.scalar(
            select(func.count()).select_from(AgentTask).where(
                AgentTask.user_id == uid, AgentTask.status == "dead_letter"
            )
        )
        inbox_count = await session.scalar(
            select(func.count()).select_from(WeChatInbox).where(
                WeChatInbox.user_id == uid,
                WeChatInbox.processing_status == "dead_letter",
            )
        )
        command_count = await session.scalar(
            select(func.count()).select_from(AgentCommandOutbox).where(
                AgentCommandOutbox.user_id == uid,
                AgentCommandOutbox.status == "dead_letter",
            )
        )
    _print_cli_payload(
        {
            "task_dead_letters": int(task_count or 0),
            "inbox_dead_letters": int(inbox_count or 0),
            "command_dead_letters": int(command_count or 0),
        },
        as_json=as_json,
    )
    return 0


def _redaction_check(*, as_json: bool) -> int:
    from app.modules.agent.runtime.telemetry import build_event

    sentinel = "Bearer redaction-sentinel"
    payload = build_event(
        "agent.run.completed",
        status=sentinel,
        prompt=sentinel,
        terminal_reason="check",
        duration_ms=1,
    )
    passed = sentinel not in json.dumps(payload, ensure_ascii=False)
    _print_cli_payload({"status": "passed" if passed else "failed"}, as_json=as_json)
    return 0 if passed else 1


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


def _dev_chat_payload(result: DevChatResult) -> dict[str, object]:
    return {
        "reply": result.reply,
        "inbound_message_id": str(result.inbound_message_id),
        "outbound_message_id": (
            str(result.outbound_message_id) if result.outbound_message_id else None
        ),
        "task_id": str(result.task_id) if result.task_id else None,
        "correlation_id": result.correlation_id,
        "status": result.status,
        "pending_confirmation": result.pending_confirmation,
        "idempotent_replay": result.idempotent_replay,
    }


def _print_json(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


async def _chat(
    user_id: str,
    text: str,
    *,
    as_json: bool,
    idempotency_key: str | None,
) -> int:
    uid = UUID(user_id)
    try:
        async with get_session_context(user_id=uid) as session:
            result = await AgentService(session).process_dev_inbound(
                uid,
                text,
                idempotency_key=idempotency_key,
            )
    except DevInboundError as exc:
        print(exc.message, file=sys.stderr)
        if as_json:
            print(json.dumps({"error": exc.code, "message": exc.message}, ensure_ascii=False))
        return 2 if exc.code in {"no_binding", "empty_text", "invalid_idempotency_key"} else 1
    except Exception as exc:
        print(f"chat failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    payload = _dev_chat_payload(result)
    if as_json:
        _print_json(payload)
    else:
        print(payload["reply"])
    return 0


async def _simulate_chat(user_id: str, *, json_lines: bool) -> int:
    """Interactive REPL through the production runtime (no iLink).

    WARNING: write ops hit the real DB after confirmation. Not accepted as
    real WeChat acceptance evidence.
    """
    uid = UUID(user_id)
    print(
        "simulate-chat — 输入消息后回车；quit / EOF 退出。"
        "写操作确认后会真实写入数据库。",
        file=sys.stderr,
    )
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
        code = await _chat(str(uid), line, as_json=json_lines, idempotency_key=None)
        if code != 0:
            return code
        if not json_lines:
            print("---")


def _parse_chat_args(argv: list[str]) -> tuple[str, str, bool, str | None]:
    if len(argv) < 2:
        raise ValueError("missing user_id")
    user_id = argv[0]
    as_json = "--json" in argv
    idempotency_key: str | None = None
    text: str | None = None
    index = 1
    while index < len(argv):
        token = argv[index]
        if token == "--json":
            index += 1
            continue
        if token == "--text":
            if index + 1 >= len(argv):
                raise ValueError("missing --text value")
            text = argv[index + 1]
            index += 2
            continue
        if token == "--idempotency-key":
            if index + 1 >= len(argv):
                raise ValueError("missing --idempotency-key value")
            idempotency_key = argv[index + 1]
            index += 2
            continue
        raise ValueError(f"unknown argument: {token}")
    if not text:
        raise ValueError("missing --text")
    return user_id, text, as_json, idempotency_key


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python -m app.modules.agent.cli chat <user_id> --text "..." [--json] [--idempotency-key KEY]')
        print("  python -m app.modules.agent.cli send-test-message <user_id> <text>")
        print("  python -m app.modules.agent.cli agent-status <user_id>")
        print("  python -m app.modules.agent.cli list-bindings")
        print("  python -m app.modules.agent.cli parse-intent \"<message>\" [--json]")
        print("  python -m app.modules.agent.cli simulate-chat <user_id> [--json-lines]")
        print("  python -m app.modules.agent.cli consumer-status [--json]")
        print("  python -m app.modules.agent.cli consumer-lease-probe [--json]")
        print("  python -m app.modules.agent.cli list-tools [--json]")
        print("  python -m app.modules.agent.cli task-status|task-cancel|task-resume <task_id> <user_id> [--json]")
        print("  python -m app.modules.agent.cli replay-message <message_id> <user_id> [--json]")
        print("  python -m app.modules.agent.cli reconcile-delivery <message_id> <user_id> [--json]")
        print("  python -m app.modules.agent.cli dead-letter-status <user_id> [--json]")
        print("  python -m app.modules.agent.cli redaction-check [--json]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "chat":
        try:
            user_id, text, as_json, idempotency_key = _parse_chat_args(sys.argv[2:])
        except ValueError as exc:
            print(f"Usage: chat <user_id> --text \"...\" [--json] [--idempotency-key KEY]", file=sys.stderr)
            print(str(exc), file=sys.stderr)
            sys.exit(2)
        sys.exit(asyncio.run(_chat(user_id, text, as_json=as_json, idempotency_key=idempotency_key)))

    elif cmd == "send-test-message":
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

    elif cmd == "consumer-status":
        sys.exit(asyncio.run(_consumer_status(as_json="--json" in sys.argv[2:])))

    elif cmd == "consumer-lease-probe":
        sys.exit(
            asyncio.run(
                _consumer_lease_probe(as_json="--json" in sys.argv[2:])
            )
        )

    elif cmd == "list-tools":
        sys.exit(_list_tools(as_json="--json" in sys.argv[2:]))

    elif cmd in {"task-status", "task-cancel", "task-resume"}:
        args = [value for value in sys.argv[2:] if value != "--json"]
        if len(args) != 2:
            print(f"Usage: {cmd} <task_id> <user_id> [--json]", file=sys.stderr)
            sys.exit(2)
        sys.exit(asyncio.run(_task_command(cmd, args[0], args[1], as_json="--json" in sys.argv[2:])))

    elif cmd == "replay-message":
        args = [value for value in sys.argv[2:] if value != "--json"]
        if len(args) != 2:
            print(
                "Usage: replay-message <message_id> <user_id> [--json]",
                file=sys.stderr,
            )
            sys.exit(2)
        sys.exit(
            asyncio.run(
                _replay_message(
                    args[0], args[1], as_json="--json" in sys.argv[2:]
                )
            )
        )

    elif cmd == "reconcile-delivery":
        args = [value for value in sys.argv[2:] if value != "--json"]
        if len(args) != 2:
            print(
                "Usage: reconcile-delivery <message_id> <user_id> [--json]",
                file=sys.stderr,
            )
            sys.exit(2)
        sys.exit(
            asyncio.run(
                _reconcile_delivery(
                    args[0], args[1], as_json="--json" in sys.argv[2:]
                )
            )
        )

    elif cmd == "dead-letter-status":
        args = [value for value in sys.argv[2:] if value != "--json"]
        if len(args) != 1:
            print("Usage: dead-letter-status <user_id> [--json]", file=sys.stderr)
            sys.exit(2)
        sys.exit(
            asyncio.run(
                _dead_letter_status(args[0], as_json="--json" in sys.argv[2:])
            )
        )

    elif cmd == "redaction-check":
        sys.exit(_redaction_check(as_json="--json" in sys.argv[2:]))

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
