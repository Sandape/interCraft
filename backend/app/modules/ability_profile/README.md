# ability_profile — Personal Ability Profile (M18)

Visual radar dashboard, self-assessment, share links, PDF export, admin view.

## CLI

```bash
uv run intercraft ability-profile list-links --user-id <UUID> [--json]
uv run intercraft ability-profile revoke-expired
uv run intercraft ability-profile list-exports --user-id <UUID> [--json]
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Error   |
