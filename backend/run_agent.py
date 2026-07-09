"""Manual Agent poll loop — processes messages and generates replies.

Usage: uv run python run_agent.py
"""
import asyncio
import time
import traceback
from uuid import UUID, uuid4

from app.main import app  # noqa: F401 — load all models
from app.core.db import get_session_context
from sqlalchemy import text
from app.channels.ilink_client import ILinkClient
from app.channels.message_handler import (
    parse_inbound_message, is_duplicate, generate_reply,
)
from app.modules.agent.service import decrypt_token


USER_ID = UUID("019ebc56-fb4f-7978-bf91-29abc5c13d93")
USER_STR = str(USER_ID)


async def main():
    print(f"Agent loop started for {USER_STR}", flush=True)
    print("Waiting for WeChat messages...\n", flush=True)

    while True:
        try:
            # Load credential
            async with get_session_context(user_id=USER_ID) as s:
                r = await s.execute(
                    text(
                        "SELECT bot_token_encrypted, cursor, base_url "
                        "FROM wechat_credentials WHERE user_id = :u"
                    ),
                    {"u": USER_STR},
                )
                cred = r.fetchone()
                if cred is None:
                    print("No credential found", flush=True)
                    await asyncio.sleep(5)
                    continue
                token = decrypt_token(cred[0])
                cursor = cred[1] or ""
                base_url = cred[2] if len(cred) > 2 else None
                base_url = base_url or "https://ilinkai.weixin.qq.com"

            # Long-poll for messages
            client = ILinkClient(bot_token=token, base_url=base_url)
            await client.start()
            try:
                data = await client.getupdates(cursor)
                msgs = data.get("msgs") or []
                new_cursor = data.get("get_updates_buf") or ""

                if new_cursor:
                    cursor = new_cursor
                    async with get_session_context(user_id=USER_ID) as s:
                        from app.modules.agent.repository import (
                            WeChatCredentialRepository,
                        )
                        await WeChatCredentialRepository(s).update_cursor(
                            USER_ID, new_cursor,
                        )

                if msgs:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] {len(msgs)} new msg(s)",
                        flush=True,
                    )

                for msg in msgs:
                    parsed = parse_inbound_message(msg)
                    if parsed is None or not parsed.text:
                        continue

                    print(f"  IN: {repr(parsed.text[:80])}", flush=True)

                    # Save context_token
                    if parsed.context_token:
                        async with get_session_context(user_id=USER_ID) as s:
                            from app.modules.agent.repository import (
                                WeChatCredentialRepository,
                            )
                            await WeChatCredentialRepository(s).update_context_token(
                                USER_ID, parsed.context_token,
                            )

                    # Dedup
                    if await is_duplicate(
                        USER_STR, parsed.context_token, parsed.msg_id,
                    ):
                        print("    SKIP duplicate", flush=True)
                        continue

                    # Persist inbound
                    from app.modules.agent.models import AgentMessage

                    async with get_session_context(user_id=USER_ID) as s:
                        s.add(
                            AgentMessage(
                                id=uuid4(),
                                user_id=USER_ID,
                                direction="inbound",
                                content=parsed.text,
                                status="received",
                                message_type=parsed.message_type,
                                context_token=parsed.context_token or None,
                                wechat_msg_id=parsed.msg_id or None,
                            ),
                        )
                        await s.flush()
                    print("    PERSISTED inbound", flush=True)

                    # Generate Agent reply
                    if parsed.from_user_id and parsed.context_token:
                        print("    Generating reply...", flush=True)
                        reply = await generate_reply(
                            parsed.text, user_id=USER_STR,
                        )
                        if reply:
                            print(f"    REPLY: {repr(reply[:80])}", flush=True)
                            send_resp = await client.send_text(
                                parsed.from_user_id, reply, parsed.context_token,
                            )
                            send_ret = (
                                send_resp.get("ret")
                                if isinstance(send_resp, dict)
                                else "?"
                            )
                            print(f"    SENT (ret={send_ret})", flush=True)

                            async with get_session_context(user_id=USER_ID) as s:
                                s.add(
                                    AgentMessage(
                                        id=uuid4(),
                                        user_id=USER_ID,
                                        direction="outbound",
                                        content=reply,
                                        status="sent",
                                        message_type="text",
                                        context_token=parsed.context_token,
                                    ),
                                )
                                await s.flush()
                            print("    SAVED outbound", flush=True)

                # Update heartbeat
                async with get_session_context(user_id=USER_ID) as s:
                    from app.modules.agent.repository import AgentRepository
                    await AgentRepository(s).update_heartbeat(USER_ID)

            finally:
                await client.stop()

        except asyncio.CancelledError:
            break
        except Exception:
            traceback.print_exc()
            await asyncio.sleep(5)

    print("Stopped.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
