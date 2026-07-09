# Quickstart Validation Guide: Personal Agent + WeChat Channel

**Feature**: REQ-052 | **Date**: 2026-07-07

## Prerequisites

1. InterCraft backend running (`uv run uvicorn app.main:app`)
2. PostgreSQL + Redis available (local or remote)
3. iLink API access (`https://ilinkai.weixin.qq.com`) — API key/application approved
4. WeChat app on mobile (iOS 8.0.70+ / Android latest) for QR scan testing
5. Test InterCraft user account (e.g., `demo@intercraft.io`)

## Validation Scenarios

### VS-1: Agent Entity Auto-Creation

```bash
# Register a new user via API — verify agent is auto-created
curl -s http://localhost:8000/api/v1/agent/status \
  -H "Authorization: Bearer <token>" | python -m json.tool
# Expected: {"status": "dormant", "wechat_bound": false}
```

### VS-2: QR Code Binding Flow

```bash
# 1. Get QR code (authenticated)
curl -s http://localhost:8000/api/v1/agent/wechat/qrcode \
  -H "Authorization: Bearer <token>" | python -m json.tool
# Expected: {"qrcode_token": "...", "qrcode_url": "https://liteapp.weixin.qq.com/q/...", "qrcode_image_url": "/api/v1/agent/wechat/qrcode/image?...", "expires_in_sec": 300}

# 2. Poll status (until user scans)
curl -s "http://localhost:8000/api/v1/agent/wechat/qrcode/status?qrcode_token=<token>" \
  -H "Authorization: Bearer <token>"
# Expected: {"status": "waiting"} → "scanned" → "confirmed"

# 3. Verify binding
curl -s http://localhost:8000/api/v1/agent/wechat/binding \
  -H "Authorization: Bearer <token>"
# Expected: {"bound": true, "agent_status": "active", "wechat_nickname": "..."}
```

### VS-3: Send Test Message via CLI

```bash
python -m app.modules.agent.cli send-test-message <user_id> "Hello from InterCraft Agent!"
# Expected: Message appears in user's WeChat within 10 seconds
# Verify in DB: SELECT status FROM agent_messages WHERE user_id = '<user_id>' ORDER BY created_at DESC LIMIT 1;
# Expected: status = 'sent'
```

### VS-4: Receive WeChat Message

```bash
# 1. User sends a text message in WeChat to the bound Agent
# 2. Verify in DB within 60 seconds:
SELECT direction, content, message_type, received_at
FROM agent_messages
WHERE user_id = '<user_id>' AND direction = 'inbound'
ORDER BY created_at DESC LIMIT 1;
# Expected: direction='inbound', message_type='text', content matches sent text
```

### VS-5: Connection Recovery After Restart

```bash
# 1. Verify agent is active
curl -s http://localhost:8000/api/v1/agent/status \
  -H "Authorization: Bearer <token>" | python -m json.tool
# Expected: {"status": "active"}

# 2. Restart the backend service
# (Ctrl+C → restart)

# 3. Wait 30 seconds, then check status again
curl -s http://localhost:8000/api/v1/agent/status \
  -H "Authorization: Bearer <token>"
# Expected: {"status": "active"} (auto-recovered from wechat_credentials)
```

### VS-6: Long Message Split

```bash
# Send a 2000-char message via CLI
python -m app.modules.agent.cli send-test-message <user_id> "$(python -c "print('测试内容\n\n' * 150)")"
# Expected: User receives ~4 segments in WeChat, each with (n/4) label
# Verify: SELECT segments_total, COUNT(*) FROM agent_messages WHERE client_id = '<client_id>' GROUP BY segments_total;
# Expected: segments_total = 4, count = 4
```

### VS-7: Quiet Hours Delay

```bash
# Set quiet hours to cover current time
curl -s -X PATCH http://localhost:8000/api/v1/agent/preferences \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"quiet_hours_start": "00:00", "quiet_hours_end": "23:59"}'

# Trigger a message
python -m app.modules.agent.cli send-test-message <user_id> "Should be delayed"

# Verify message is queued not sent
SELECT status FROM agent_messages WHERE user_id = '<user_id>' ORDER BY created_at DESC LIMIT 1;
# Expected: status = 'pending' (not 'sent')

# Reset preferences
curl -s -X PATCH http://localhost:8000/api/v1/agent/preferences \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"quiet_hours_start": null, "quiet_hours_end": null}'
```

### VS-8: Agent Unbind Flow

```bash
# 1. Unbind
curl -s -X DELETE http://localhost:8000/api/v1/agent/wechat/binding \
  -H "Authorization: Bearer <token>"
# Expected: {"message": "微信绑定已解除"}

# 2. Verify dormant
curl -s http://localhost:8000/api/v1/agent/status \
  -H "Authorization: Bearer <token>"
# Expected: {"status": "dormant", "wechat_bound": false}

# 3. Verify credentials revoked
# Check DB: SELECT status FROM wechat_credentials WHERE user_id = '<user_id>';
# Expected: status = 'revoked'
```

## E2E Test Flow

Run Playwright tests:
```bash
cd tests/e2e
npx playwright test agent-wechat/
```

Expected coverage:
- `agent-binding.spec.ts` — QR code binding + unbind flow (mock iLink API)
- `agent-messaging.spec.ts` — Send/receive text messages via mock
- `agent-lifecycle.spec.ts` — Status transitions (dormant → active → degraded → dormant)
- `agent-preferences.spec.ts` — Quiet hours, display name, notification mode
