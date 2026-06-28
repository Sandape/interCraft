"""Contract test fixtures for REQ-033 (T023).

Exposes the factory functions in :mod:`test_033_fixtures` so test
modules can do ``from tests.contract.fixtures import eval_run``.
"""
from __future__ import annotations

from tests.contract.fixtures.test_033_fixtures import (  # noqa: F401
    ai_invocation_record,
    ai_invocation_summary,
    badcase,
    badcase_review_action,
    eval_case_result,
    eval_run,
    langsmith_experiment_ref,
    metric_snapshot,
    metric_snapshot_dataclass,
    product_event,
    product_funnel_event,
    redaction_audit,
    redaction_policy,
    trace_run_ref,
)
