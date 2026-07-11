# WeChat Agent production runtime

This module implements the REQ-060 boundary between the existing iLink channel
and InterCraft domain services. PostgreSQL is authoritative for consumer
ownership, inbound deduplication, tasks, confirmations, tool executions,
command outbox and outbound delivery. Redis is only an accelerator.

## Runtime shape

1. `consumer_lease.py` elects one active consumer with a PostgreSQL lease and
   monotonically increasing fencing token. `WECHAT_AGENT_CONSUMER_ENABLED`
   defaults to `false`; production must opt in explicitly.
2. `app/channels/durable_inbox.py` commits the complete poll batch, encrypted
   raw payload and next cursor atomically. Active binding plus binding epoch is
   resolved before user-scoped work is created.
3. `service.py` creates/claims an owner-scoped `AgentTask`, constructs trusted
   `ToolContext`, restores bounded conversation history and invokes the
   production orchestrator.
4. `runtime/orchestrator.py` runs a bounded model/tool loop. The model may
   propose a call, but code validates schemas, strips authority fields,
   authorizes ownership, requires confirmation where configured and gates all
   success claims on persisted tool evidence.
5. Domain writes and `AgentToolExecution` completion share a savepoint.
   External/background work uses the transactional command outbox and a stable
   domain idempotency key.
6. Replies are claimed with `SKIP LOCKED`. Provider timeouts become
   `unknown_delivery` and are never blindly resent.

The correlated event path is `wechat.message.received` ->
`wechat.identity.resolved` -> `agent.llm.completed` -> `agent.tool.proposed` ->
`agent.tool.completed` -> `agent.db.committed` ->
`agent.run.completed` -> `wechat.delivery.completed`. The run event closes
model/tool work; the later delivery event records the independently claimed
channel effect. OTel spans contain only
allowlisted identifiers; prompt, reasoning, message, resume/JD and tool
payloads are not captured.

## State machines

- Task: `queued -> running -> awaiting_input|awaiting_confirmation|waiting_external
  -> succeeded|failed|cancelled|dead_letter`. Claims carry a generation;
  stale generations cannot commit. Resume creates an audited lineage rather
  than editing a terminal task.
- Confirmation: `pending -> approved|rejected|expired|superseded`. Only the
  HMAC hash and a short hint are stored. Approval uses compare-and-swap against
  task, arguments hash, version, owner, binding and epoch.
- Delivery: `pending|retry_wait -> sending -> sent|unknown_delivery|failed`.
  Only failures proven to be pre-effect may retry.
- Consumer: `disabled|standby|active|degraded`. Lease renewal failure stops
  polling before any later cursor/effect commit.

## Adding a Tool

1. Define strict Pydantic input/output contracts in `tools/catalog.py`; never
   include `user_id`, owner, permission, session, binding or trace authority in
   model-controlled arguments.
2. Implement a thin adapter under `tools/adapters/` that calls an existing
   domain service with `ToolContext.user_id` and returns `ToolResult` with
   truthful status, `committed`, resource refs and typed error.
3. Register it once in `tools/factory.py` with version, side-effect,
   confirmation and atomicity policies.
4. Add catalog/contract tests, owner-isolation tests, failure tests and a
   success-evidence assertion. Write operations must prove their committed
   resource and must not retry after the effect could have started.
5. Update `prompts/system-v2.md` only for a new interaction rule; tool
   descriptions remain the capability source of truth.

## Run and diagnose

From `backend/`:

```text
uv run alembic upgrade head
uv run python -m app.modules.agent.cli consumer-status --json
uv run python -m app.modules.agent.cli consumer-lease-probe --json
uv run python -m app.modules.agent.cli list-tools --json
uv run python -m app.modules.agent.cli task-status <task_id> <user_id> --json
uv run python -m app.modules.agent.cli dead-letter-status <user_id> --json
uv run python -m app.modules.agent.cli reconcile-delivery <message_id> <user_id> --json
uv run python -m app.modules.agent.cli redaction-check --json
```

## Dev ingress (non-WeChat)

For Cursor/Codex/Claude Code local testing without sending real WeChat messages:

```text
uv run python -m app.modules.agent.cli chat <user_id> --text "帮我记一个腾讯后端岗" --json
uv run python -m app.modules.agent.cli simulate-chat <user_id>
```

Requirements:

- the target user must already have an active WeChat binding (one-time `/agent` QR bind is enough);
- messages persist as `agent_messages.channel=cli` and run through the production orchestrator;
- replies are returned on stdout and are **not** enqueued to iLink;
- this path cannot substitute REQ-060 real-WeChat acceptance (T100–T104).

HTTP equivalent (development only, or `AGENT_DEV_INGRESS_ENABLED=true`):

```text
POST /api/v1/agent/dev/chat
Authorization: Bearer <access_token>
{"text":"查询我的岗位","idempotency_key":"optional-key"}
```

Diagnostics are owner-scoped and must not print body content, credentials,
tokens, cookies or raw provider responses. `reconcile-delivery` is deliberately
read-only until a trustworthy provider receipt API exists. Replay is allowed
only from an eligible terminal/dead-letter source and creates one durable audit
lineage.

Rollback the application before downgrading schema. Disable the consumer on
all instances, drain or reconcile `sending`/`unknown_delivery`, then run the
target Alembic downgrade. Never downgrade while a lease owner is polling.

## Data and retention boundary

Channel payloads are encrypted at rest and decrypted only inside an
owner-scoped execution path. Telemetry stores identifiers/hashes and bounded
status metadata, never message or business document content. RLS is forced on
tenant tables. REQ-060 does not invent a new retention duration: business and
message rows follow the existing product deletion/retention policy; operational
lease/queue metadata may be pruned only after terminal-state and audit needs
are satisfied. No automatic destructive retention job is introduced here.
