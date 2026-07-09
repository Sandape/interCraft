"""Optional LangSmith sync adapter for REQ-045.

The adapter is deliberately small and mock-friendly. Local eval artifacts stay
canonical; this module only reports auxiliary workbench sync status.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

SyncMode = Literal["never", "auto", "require"]


class LangSmithSyncError(RuntimeError):
    """Raised when required LangSmith sync cannot complete."""


@dataclass(frozen=True)
class LangSmithSyncResult:
    run_id: str
    sync_status: str
    project: str
    dataset: str = "unavailable"
    experiment_name: str = "unavailable"
    url: str = "unavailable"
    error_message: str = ""
    export_policy_decision_id: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "syncStatus": self.sync_status,
            "project": self.project,
            "dataset": self.dataset,
            "experimentName": self.experiment_name,
            "url": self.url,
            "errorMessage": self.error_message,
            "exportPolicyDecisionId": self.export_policy_decision_id,
        }


def _has_langsmith_credentials() -> bool:
    return bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY"))


def _default_project(project: str | None) -> str:
    if project:
        return project
    return os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT") or "intercraft-prod"


def _field(record: Any, name: str) -> Any:
    if isinstance(record, dict):
        return record.get(name) or record.get(_camel(name))
    return getattr(record, name, None)


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value or "")).upper()


def _report_environment(report: dict[str, Any]) -> str:
    return str(report.get("environment") or report.get("env") or "LOCAL").upper()


def _validate_export_policy(
    report: dict[str, Any],
    *,
    export_policy_decision: Any | None,
    export_policy_decision_id: str | None,
) -> str | None:
    env = _report_environment(report)
    if export_policy_decision is None:
        if env == "PRODUCTION" and not export_policy_decision_id:
            raise LangSmithSyncError(
                "export policy decision is required for production LangSmith sync"
            )
        return export_policy_decision_id

    destination = _enum_value(_field(export_policy_decision, "destination"))
    level = _enum_value(_field(export_policy_decision, "representation_level"))
    if destination != "LANGSMITH":
        raise LangSmithSyncError("export policy decision is not for LangSmith")
    if level == "BLOCKED":
        reason = _field(export_policy_decision, "blocked_reason") or "blocked"
        raise LangSmithSyncError(f"export policy decision is blocked: {reason}")
    return str(
        _field(export_policy_decision, "decision_id")
        or export_policy_decision_id
        or ""
    ) or None


def sync_report_to_langsmith(
    report: dict[str, Any],
    *,
    mode: SyncMode = "auto",
    project: str | None = None,
    client: Any | None = None,
    export_policy_decision_id: str | None = None,
    export_policy_decision: Any | None = None,
) -> LangSmithSyncResult:
    project_name = _default_project(project)
    run_id = str(report.get("runId") or report.get("run_id") or "unknown")

    if mode == "never":
        return LangSmithSyncResult(
            run_id=run_id,
            sync_status="DISABLED",
            project=project_name,
            export_policy_decision_id=export_policy_decision_id,
        )

    try:
        export_policy_decision_id = _validate_export_policy(
            report,
            export_policy_decision=export_policy_decision,
            export_policy_decision_id=export_policy_decision_id,
        )
    except LangSmithSyncError as exc:
        result = LangSmithSyncResult(
            run_id=run_id,
            sync_status="FAILED",
            project=project_name,
            error_message=str(exc),
            export_policy_decision_id=export_policy_decision_id,
        )
        if mode == "require":
            raise
        return result

    if client is None and not _has_langsmith_credentials():
        result = LangSmithSyncResult(
            run_id=run_id,
            sync_status="FAILED" if mode == "require" else "DISABLED",
            project=project_name,
            error_message="LangSmith credentials are not configured",
            export_policy_decision_id=export_policy_decision_id,
        )
        if mode == "require":
            raise LangSmithSyncError(result.error_message)
        return result

    try:
        if client is None:
            from langsmith import Client

            client = Client()
        if hasattr(client, "sync_report"):
            response = client.sync_report(report, project=project_name)
        else:
            # Minimal SDK fallback: create one run-level record. Dataset and
            # experiment APIs vary by SDK version, so rich sync is layered later.
            client.create_run(
                name=f"REQ-045 eval {run_id}",
                run_type="chain",
                inputs={"report": report},
                outputs={"status": report.get("status")},
                project_name=project_name,
            )
            response = {
                "dataset": report.get("datasetVersion", "unavailable"),
                "experimentName": f"req045-{run_id}",
                "url": "unavailable",
            }
        return LangSmithSyncResult(
            run_id=run_id,
            sync_status="SYNCED",
            project=project_name,
            dataset=str(response.get("dataset") or report.get("datasetVersion") or "unavailable"),
            experiment_name=str(response.get("experimentName") or f"req045-{run_id}"),
            url=str(response.get("url") or "unavailable"),
            export_policy_decision_id=export_policy_decision_id,
        )
    except Exception as exc:
        result = LangSmithSyncResult(
            run_id=run_id,
            sync_status="FAILED",
            project=project_name,
            error_message=str(exc),
            export_policy_decision_id=export_policy_decision_id,
        )
        if mode == "require":
            raise LangSmithSyncError(str(exc)) from exc
        return result


__all__ = [
    "LangSmithSyncError",
    "LangSmithSyncResult",
    "SyncMode",
    "sync_report_to_langsmith",
]
