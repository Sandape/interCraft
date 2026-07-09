# WeChat Conversational Agent (REQ-054)

## Overview

Replaces the chat-only `PersonalAgentReply` path with a tool-calling
`ConversationOrchestrator`:

```
WeChat inbound → AgentService.process_inbound_reply
              → ConversationOrchestrator.handle
              → IntentParser (LLM, node_name=intent_parse)
              → tools / interview adapter (in-process JobService / InterviewSessionService)
              → Chinese reply text
```

## States (Redis `wechat:conversation:{user_id}`, TTL 24h)

| State | Behavior |
|-------|----------|
| `idle` | Parse intent → prepare write / execute read / interview |
| `awaiting_confirmation` | Only 确认/取消; other messages queued |
| `in_interview` | Default = answer; 暂停/结束/继续 are meta |

## Tools

| Tool | Confirm? | Service |
|------|----------|---------|
| `create_job` | yes | `JobService.create` |
| `update_status` | yes | `JobService.update_status` |
| `update_fields` | yes | `JobService.patch` (location/jd/notes only) |
| `query_jobs` | no | `JobService.list` |
| `query_reports` | no | `InterviewSessionService` |
| `query_ability` | no | `AbilityProfileService.get_dashboard` |

Delete / Offer → Web guide (no execute).

## CLI

```bash
cd backend
uv run python -m app.modules.agent.cli parse-intent "帮我记一个腾讯的后端岗" --json
uv run python -m app.modules.agent.cli simulate-chat <user_id>
```

## Tests

```bash
cd backend
uv run pytest tests/unit/agent/conversation/ -q
```

## Notes

- Relative times: fixed `Asia/Shanghai` (`time_parser.py`)
- Interview mutex: global pending/in_progress (`interview/mutex.py`)
- Never log raw user message text
- Per-user inbound serialization: `ilink_pool` asyncio.Lock dict
