"""A2A framework CLI (REQ-031 US1, T014).

Constitution II (CLI Interface): the framework exposes a CLI that
accepts a JSON declaration of agents + routing rules and emits the
resulting graph topology + compile status.

Usage::

    python -m app.agents.a2a.cli --agents agents.json
    python -m app.agents.a2a.cli --agents agents.json --check-only

Schema for ``agents.json``::

    {
      "agents": [
        {"name": "hint_ladder", "role": "...", "timeout_seconds": 10.0},
        {"name": "recommendation", "role": "...", "timeout_seconds": 15.0}
      ],
      "routing_rules": [
        {"from": "hint_ladder", "to": "recommendation", "when": "stuck"}
      ],
      "default_timeout_seconds": 30.0,
      "max_delegation_depth": 3
    }

Exit codes:

- ``0`` — graph topology validated + compiled.
- ``1`` — input validation failed (unknown agent, cycle, depth exceeded).
- ``2`` — usage error (no --agents arg, file not found).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.agents.a2a.routing import (
    CycleDetectedError,
    DepthExceededError,
    UnknownAgentError,
    check_cycle,
    enforce_depth,
)
from app.agents.a2a.schemas import AgentDefinition, RoutingDecision, SupervisorConfig


def _load_agents_file(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"agents file not found: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def _build_agents(agents_data: list[dict[str, Any]]) -> list[AgentDefinition]:
    agents: list[AgentDefinition] = []
    for entry in agents_data:
        agents.append(
            AgentDefinition(
                name=entry["name"],
                role=entry.get("role", ""),
                timeout_seconds=entry.get("timeout_seconds"),
            )
        )
    return agents


def _build_routing_fn(rules: list[dict[str, Any]]) -> Any:
    """Build a routing function from the declarative rule list.

    The function evaluates rules in order; the first whose ``when``
    matches the state wins. If no rule matches, returns
    ``RoutingDecision(next_agent=None)`` (end the graph).

    ``when`` semantics:

    - ``"always"`` — match unconditionally.
    - ``"stuck"`` — match when ``attempt_count >= 3``.
    - ``"never"`` — never match (used for opt-out routes).
    - ``"<lambda_name>"`` — placeholder for custom lambdas; we do
      not implement custom lambdas in US1.
    """
    def _routing_fn(state: dict[str, Any]) -> RoutingDecision:
        for rule in rules:
            when = rule.get("when", "always")
            target = rule.get("to")
            if target is None:
                continue
            if when == "always":
                return RoutingDecision(next_agent=target, reason=f"rule {rule.get('from')}->{target}")
            if when == "stuck" and int(state.get("attempt_count", 0)) >= 3:
                return RoutingDecision(next_agent=target, reason="stuck")
            if when == "never":
                continue
            # Unknown when-clause → skip (defensive).
        return RoutingDecision(next_agent=None, reason="no matching rule → END")

    return _routing_fn


def _print_topology(config: SupervisorConfig) -> None:
    print(f"Supervisor topology ({len(config.agents)} agents):")
    for agent in config.agents:
        timeout = agent.timeout_seconds or config.default_timeout_seconds
        print(f"  - {agent.name}: role={agent.role!r}, timeout={timeout}s")
    print(f"  Default timeout: {config.default_timeout_seconds}s")
    print(f"  Max delegation depth: {config.max_delegation_depth}")
    print(f"  Cycle detection: {config.enable_cycle_detection}")
    print(f"  Parent agent: {config.parent_agent}")


def _validate_topology(config: SupervisorConfig, rules: list[dict[str, Any]]) -> list[str]:
    """Return a list of validation errors; empty list = topology OK."""
    errors: list[str] = []
    available = {a.name for a in config.agents}

    visited: list[str] = []
    depth = 0
    for rule in rules:
        target = rule.get("to")
        if target is None:
            continue
        if target not in available:
            errors.append(f"Unknown target agent {target!r}; available: {sorted(available)}")
            continue
        try:
            check_cycle(visited, target)
        except CycleDetectedError as exc:
            errors.append(f"Cycle: {exc}")
            break
        try:
            enforce_depth(depth, config.max_delegation_depth, visited[-1] if visited else "__supervisor__", target)
        except DepthExceededError as exc:
            errors.append(f"Depth: {exc}")
            break
        visited.append(target)
        depth += 1
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="a2a-supervisor",
        description="A2A Supervisor CLI — validate / compile a multi-agent graph",
    )
    parser.add_argument(
        "--agents",
        required=True,
        help="Path to a JSON file declaring agents + routing rules.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate topology without compiling the graph.",
    )
    args = parser.parse_args(argv)

    try:
        data = _load_agents_file(args.agents)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 2

    agents = _build_agents(data.get("agents", []))
    rules = data.get("routing_rules", [])
    routing_fn = _build_routing_fn(rules)

    try:
        config = SupervisorConfig(
            agents=agents,
            routing_fn=routing_fn,
            default_timeout_seconds=data.get("default_timeout_seconds", 30.0),
            max_delegation_depth=data.get("max_delegation_depth", 3),
            enable_cycle_detection=data.get("enable_cycle_detection", True),
        )
    except (ValueError, UnknownAgentError) as exc:
        print(f"error: config invalid: {exc}", file=sys.stderr)
        return 1

    errors = _validate_topology(config, rules)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    _print_topology(config)

    if args.check_only:
        print("\nstatus: check-only passed (graph not compiled)")
        return 0

    print("\nstatus: topology valid; graph would compile (skipped in CLI mode).")
    print("note: invoke Supervisor.compile_state_graph(state_cls) in code to produce a runnable graph.")
    return 0


if __name__ == "__main__":
    sys.exit(main())