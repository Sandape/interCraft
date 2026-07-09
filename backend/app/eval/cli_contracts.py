"""Shared CLI contracts for REQ-045 eval automation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class CLIExitCode(IntEnum):
    SUCCESS = 0
    OPERATIONAL_FAILURE = 1
    INVALID_ARGUMENTS = 2
    POLICY_VIOLATION = 3
    EVAL_GATE_FAILED = 4


@dataclass(frozen=True)
class CLIResult:
    exit_code: CLIExitCode
    payload: dict[str, Any]


def build_error_payload(
    *,
    error: str,
    message: str,
    violations: list[str] | None = None,
    code: CLIExitCode = CLIExitCode.POLICY_VIOLATION,
) -> dict[str, Any]:
    return {
        "error": error,
        "code": int(code),
        "message": message,
        "violations": list(violations or []),
    }


def print_json_result(result: CLIResult) -> int:
    print(json.dumps(result.payload, ensure_ascii=False))
    return int(result.exit_code)


__all__ = [
    "CLIExitCode",
    "CLIResult",
    "build_error_payload",
    "print_json_result",
]
