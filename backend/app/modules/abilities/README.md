# M09 — Ability Profile

6 维度能力画像(技术深度/架构能力/工程实践/沟通表达/算法能力/业务理解)。

## Public API

| Endpoint | Method | Purpose |
|---|---|---|
| `/ability-dimensions` | GET | List user dimensions |
| `/ability-dimensions/{key}` | GET | Get single dimension |
| `/ability-dimensions/{key}` | PATCH | Update scores / sub_scores |
| `/ability-dimensions/{key}/toggle` | POST | Enable/disable dimension |
| `/ability-dimensions/history` | GET | Time series data |
| `/ability-dimensions/dimensions-meta` | GET | Static metadata |

## Config

- No additional config; uses RLS via `app.user_id`

## CLI

```bash
uv run python -m app.modules.abilities.cli seed --user-id <uuid>
uv run python -m app.modules.abilities.cli list --user-id <uuid>
uv run python -m app.modules.abilities.cli list --user-id <uuid> --json
```
