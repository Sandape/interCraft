# Contract: Dashboard Summary CLI

**Spec refs**: Constitution II (CLI Interface)  
**Module**: `backend/app/modules/dashboard/cli.py`

## Command

```bash
cd backend
uv run python -m app.modules.dashboard.cli dump-summary \
  --user-id <UUID> \
  --tz Asia/Shanghai \
  [--json]
```

## Behavior

1. Builds the same `DashboardSummary` as the HTTP handler (shared `service.build_summary`).
2. Default: human-readable sections (L0 today count, funnel counts, next_action id).
3. `--json`: full summary JSON to stdout.
4. Exit `0` on success; non-zero on missing user / invalid tz.
5. Does not require Redis; may print `cache=bypass`.

## Use cases

- Local debugging of today-filter / funnel rules
- CI fixture generation for contract tests
- Replaying a user’s summary without browser
