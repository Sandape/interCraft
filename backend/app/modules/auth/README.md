# M04 — Account / Auth

**Purpose**: Email registration, password login, JWT issuance, profile read/update.

**Public API**:
- `POST /api/v1/auth/register` — create user + auto-login.
- `POST /api/v1/auth/login` — email + password → token pair.
- `POST /api/v1/auth/refresh` — rotate refresh token.
- `POST /api/v1/auth/logout` — revoke current session.
- `GET  /api/v1/auth/me` — current user profile.
- `PATCH /api/v1/auth/me` — update display_name / title / years_of_experience / target_role / bio.

**Config keys**: `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TTL`, `REFRESH_TTL`, `BCRYPT_COST_ROUNDS`.

**CLI** (Constitution II):
```bash
uv run python -m app.modules.auth.cli register --email a@b.com --password 'P@ss1234' --name "Lin"
uv run python -m app.modules.auth.cli login    --email a@b.com --password 'P@ss1234' --json
uv run python -m app.modules.auth.cli whoami   --token <ACCESS>
uv run python -m app.modules.auth.cli replay   fixtures/auth_login.json
```

**Exit codes**:
- `0` — success
- `2` — argument / fixture error
- `1` — service failure (DB / etc.)

**Notes**:
- Password policy: ≥ 8 chars, ≥ 1 digit, ≥ 1 letter (spec FR-001, plan DEC-8).
- bcrypt cost defaults to 12; tunable via `BCRYPT_COST_ROUNDS`.
- 5-device limit is enforced inside `AuthService.login` via `SessionService.register_session`.
- Refresh tokens use rotation + reuse detection (see M05).
