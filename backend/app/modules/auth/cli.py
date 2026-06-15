"""M04 — top-level auth CLI (Constitution II: CLI Interface)."""
from __future__ import annotations

import asyncio
import json

import typer

from app.core.db import get_session_factory
from app.modules.auth.schemas import LoginInput, RegisterInput
from app.modules.auth.service import AuthService

app = typer.Typer(help="InterCraft auth CLI (M04)")


def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        for k, v in obj.items():
            typer.echo(f"{k}: {v}")


def _err(msg: str) -> None:
    typer.echo(msg, err=True)
    raise typer.Exit(code=2)


@app.command("register")
def cmd_register(
    email: str = typer.Option(..., "--email", "-e"),
    password: str = typer.Option(..., "--password", "-p", hide_input=True),
    display_name: str | None = typer.Option(None, "--name", "-n"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Register a new user."""

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:  # type: AsyncSession
            svc = AuthService(db)
            payload = RegisterInput(email=email, password=password, display_name=display_name)
            user, tokens = await svc.register(payload)
            return {
                "user_id": user.id,
                "email": user.email,
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_in": tokens.expires_in,
            }

    try:
        out = asyncio.run(_run())
    except Exception as e:
        _err(f"register failed: {e}")
    _emit(out, as_json)


@app.command("login")
def cmd_login(
    email: str = typer.Option(..., "--email", "-e"),
    password: str = typer.Option(..., "--password", "-p", hide_input=True),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Log in. Returns token pair (text or --json)."""

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = AuthService(db)
            payload = LoginInput(email=email, password=password, device_fingerprint="cli")
            user, tokens, evicted = await svc.login(payload)
            return {
                "user_id": user.id,
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_in": tokens.expires_in,
                "evicted_session_id": evicted,
            }

    try:
        out = asyncio.run(_run())
    except Exception as e:
        _err(f"login failed: {e}")
    _emit(out, as_json)


@app.command("whoami")
def cmd_whoami(
    token: str = typer.Option(..., "--token", "-t"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Decode an access token and print claims."""

    async def _run() -> dict:
        from app.core.security import decode_token

        try:
            payload = decode_token(token, expected_type="access")
        except Exception as e:
            return {"error": f"invalid token: {e}"}
        return {
            "sub": payload.sub,
            "session_id": payload.session_id,
            "iat": payload.iat,
            "exp": payload.exp,
            "type": payload.type,
        }

    _emit(asyncio.run(_run()), as_json)


@app.command("replay")
def cmd_replay(
    fixture: str = typer.Argument(..., help="Path to a JSON fixture captured from a previous request"),
    as_json: bool = typer.Option(True, "--json"),
) -> None:
    """Replay a captured request fixture for observability (Constitution V).

    Fixture shape: { "endpoint": "auth.login", "payload": {...} }
    """
    try:
        with open(fixture, encoding="utf-8") as f:
            blob = json.load(f)
    except Exception as e:
        _err(f"failed to read fixture: {e}")

    endpoint = blob.get("endpoint")
    payload = blob.get("payload", {})

    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = AuthService(db)
            if endpoint == "auth.login":
                inp = LoginInput(**payload)
                user, tokens, evicted = await svc.login(inp)
                return {
                    "user_id": user.id,
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "evicted_session_id": evicted,
                }
            if endpoint == "auth.register":
                inp = RegisterInput(**payload)
                user, tokens = await svc.register(inp)
                return {"user_id": user.id, "access_token": tokens.access_token}
            return {"error": f"unknown endpoint: {endpoint}"}

    try:
        out = asyncio.run(_run())
    except Exception as e:
        out = {"error": str(e)}
    _emit(out, as_json)


if __name__ == "__main__":  # pragma: no cover
    app()
