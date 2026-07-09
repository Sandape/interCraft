from __future__ import annotations

import json

from app.eval.cli_contracts import (
    CLIExitCode,
    CLIResult,
    build_error_payload,
    print_json_result,
)


def test_cli_exit_code_values_are_stable() -> None:
    assert CLIExitCode.SUCCESS == 0
    assert CLIExitCode.OPERATIONAL_FAILURE == 1
    assert CLIExitCode.INVALID_ARGUMENTS == 2
    assert CLIExitCode.POLICY_VIOLATION == 3
    assert CLIExitCode.EVAL_GATE_FAILED == 4


def test_cli_result_serializes_success_payload(capsys) -> None:
    result = CLIResult(
        exit_code=CLIExitCode.SUCCESS,
        payload={"runId": "run-1", "status": "PASSED"},
    )

    assert print_json_result(result) == 0
    out = capsys.readouterr().out
    assert json.loads(out) == {"runId": "run-1", "status": "PASSED"}


def test_cli_result_serializes_error_payload(capsys) -> None:
    result = CLIResult(
        exit_code=CLIExitCode.POLICY_VIOLATION,
        payload=build_error_payload(
            error="policy_violation",
            message="full-content export missing owner",
            violations=["missing_owner"],
        ),
    )

    assert print_json_result(result) == 3
    body = json.loads(capsys.readouterr().out)
    assert body["error"] == "policy_violation"
    assert body["code"] == 3
    assert body["violations"] == ["missing_owner"]
