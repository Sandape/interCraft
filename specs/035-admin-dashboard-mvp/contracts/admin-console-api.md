# Admin Console API Contract

Base path: `/api/v1/admin-console`

All endpoints require authentication unless explicitly noted. Responses use the
project error envelope on failure:

```json
{
  "error": {
    "code": "admin.forbidden",
    "message": "Forbidden",
    "request_id": "req_..."
  }
}
```

## Roles And Capabilities

| Capability | Required For |
|---|---|
| `PM_DASHBOARD_VIEW` | Dashboard summary and metric panels. |
| `TRACE_VIEW` | Trace Explorer metadata and redacted trace views. |
| `MASKED_RAW_VIEW` | Masked raw payload reveal and cURL body reveal. |
| `EVAL_VIEW` | Eval Center read-only pages. |
| `SNAPSHOT_EXPORT` | Dashboard snapshot creation. |
| `PRIVACY_AUDIT_VIEW` | Privacy/audit page. |

## GET `/health`

Returns admin console module liveness. No sensitive data.

Response 200:

```json
{
  "status": "ok",
  "module": "admin_console"
}
```

## GET `/me`

Returns the current admin-console identity and capabilities.

Response 200:

```json
{
  "user_id": "019ef000-0000-7000-8000-000000000001",
  "display_name": "Internal Reviewer",
  "role_labels": ["reviewer"],
  "capabilities": ["TRACE_VIEW", "MASKED_RAW_VIEW", "EVAL_VIEW"],
  "environment_scope": "production",
  "session_expires_at": "2026-06-29T12:30:00Z"
}
```

Unauthorized/forbidden:

- 401 when unauthenticated.
- 403 when authenticated but no admin-console grant applies.

## GET `/dashboard/summary`

Returns dashboard-wide summary, freshness, and panel links for the admin landing
view. This endpoint may reuse REQ-033 PM dashboard services internally.

Query:

| Parameter | Required | Description |
|---|---|---|
| `date_from` | yes | ISO datetime/date. |
| `date_to` | yes | ISO datetime/date. |
| `environment` | no | `local`, `ci`, `staging`, `production`, `all`. |
| `feature_area` | no | Product area filter. |
| `agent_name` | no | Agent filter. |
| `model` | no | Model filter. |

Response 200:

```json
{
  "filters": {
    "date_from": "2026-06-01T00:00:00Z",
    "date_to": "2026-06-29T23:59:59Z",
    "environment": "production"
  },
  "freshness": {
    "freshness_at": "2026-06-29T23:50:00Z",
    "target_minutes": 15,
    "quality_state": "complete",
    "warnings": []
  },
  "summary_cards": [
    {
      "metric_id": "pm.active_users",
      "label": "Active users",
      "value": 128,
      "unit": "count",
      "definition": "Users with at least one product activity in the period."
    }
  ],
  "panels": [
    {
      "panel_id": "product_funnel",
      "title": "Core Funnel",
      "href": "/admin/dashboard/funnel",
      "quality_state": "complete"
    }
  ],
  "request_id": "req_..."
}
```

## POST `/dashboard/snapshots`

Creates a privacy-safe dashboard snapshot.

Required capability: `SNAPSHOT_EXPORT`.

Request:

```json
{
  "date_from": "2026-06-01T00:00:00Z",
  "date_to": "2026-06-29T23:59:59Z",
  "environment": "production",
  "format": "markdown",
  "include_warnings": true
}
```

Response 201:

```json
{
  "dashboard_snapshot_id": "snap_019ef...",
  "format": "markdown",
  "privacy_status": "safe",
  "created_at": "2026-06-29T23:59:00Z",
  "download_url": "/api/v1/admin-console/dashboard/snapshots/snap_019ef...",
  "warnings": []
}
```

## GET `/dashboard/snapshots/{dashboard_snapshot_id}`

Returns a stored snapshot. Snapshot payload contains aggregate/redacted data
only.

Response 200:

```json
{
  "dashboard_snapshot_id": "snap_019ef...",
  "format": "markdown",
  "content": "# Dashboard Snapshot\n...",
  "filters": {},
  "warnings": [],
  "created_at": "2026-06-29T23:59:00Z"
}
```

## GET `/audit-events`

Returns audit events for admin-console operations.

Required capability: `PRIVACY_AUDIT_VIEW`.

Query supports `actor_id`, `action`, `target_type`, `target_id`, `date_from`,
`date_to`, `limit`, and `cursor`.

Response 200:

```json
{
  "items": [
    {
      "audit_id": "audit_019ef...",
      "actor_id": "019ef000-0000-7000-8000-000000000001",
      "action": "payload.reveal",
      "target_type": "payload",
      "target_id": "payload_019ef...",
      "reason": "Investigating failed interview score",
      "visibility_mode": "masked_raw",
      "decision": "allowed",
      "created_at": "2026-06-29T23:59:00Z"
    }
  ],
  "next_cursor": null
}
```
