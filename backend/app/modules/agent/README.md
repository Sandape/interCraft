# Agent Module (REQ-052)

Personal AI Agent — one per user. Manages WeChat iLink binding,
message send/receive, agent lifecycle, and preferences.

## Quick Start

```bash
# Check agent status
python -m app.modules.agent.cli agent-status <user_id>

# Send test message
python -m app.modules.agent.cli send-test-message <user_id> "Hello!"

# List all bindings (admin)
python -m app.modules.agent.cli list-bindings
```

## Architecture

```
modules/agent/         # Business logic (models, API, preferences)
channels/              # iLink protocol (ILinkClient, ILinkConnectionPool)
```

## API Endpoints

See `contracts/agent-api.yaml` in the spec directory.
