"""EvalRunner — replays golden cases through real graph nodes (T030/T031/T032).

For each GoldenCase:
1. Run ChineseFidelityChecker on the case's `llm_response` → fidelity metric
2. Patch `get_llm_client` to return a stub yielding `case.llm_response`
3. Patch `_sink_to_error_book` to a no-op (avoid DB dependency in eval)
4. Invoke the real node function (score_node / report_node) — this tests
   the full prompt assembly + JSON parsing + state shape logic
5. Validate `expected_contains` keywords appear in actual output
6. Validate `expected_score_range` / `expected_overall_score_range`
7. Handle `expected_fidelity_pass=False` reverse-assertion (regression cases
   that the checker should flag — if it doesn't, that's a checker regression)

Produces per-case CaseResult + aggregate EvalReport (FR-010, FR-013).

Mock mode (default): patches LLM client with deterministic stub.
Real mode (opt-in): does NOT patch — uses real DeepSeek V4 Pro. Real mode
requires `DEEPSEEK_API_KEY` env var and burns real quota; not run in CI.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import structlog

from app.eval.checker import ChineseFidelityChecker, ChineseFidelityResult
from app.eval.golden_loader import GoldenCase
from app.eval.prompt_fingerprint import (
    compute_prompt_fingerprint,
)
from app.modules.telemetry_contracts.schemas import VersionContext

logger = structlog.get_logger("eval.runner")


@dataclass
class CaseResult:
    """Per-case verdict from EvalRunner.run_case().

    REQ-033 Sub-batch 1: ``run_id`` lets downstream consumers join each
    per-case row back to the aggregate ``EvalReport.run_id`` and
    (future) LangSmith experiment / trace.

    REQ-035 Sub-batch: ``trace_id``, ``llm_call_id``, ``badcase_id``,
    ``score_dimensions``, ``regression_delta``, ``prompt_tokens``,
    ``completion_tokens``, ``estimated_cost``, and ``latency_ms`` let
    downstream consumers (PM dashboard, badcase review, CI artifact diff)
    join each per-case row to its OTel trace, LLM call, badcase, score
    breakdown, usage, and cost — without walking the ``metrics`` dict.

    All REQ-035 fields have safe defaults (empty string / zero / None) so
    every existing constructor call continues to work unchanged.
    """

    case_id: str
    node: str
    passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    actual_output: dict[str, Any] = field(default_factory=dict)
    failure_reasons: list[str] = field(default_factory=list)
    label: str = ""
    expected_fidelity_pass: bool = True
    run_id: UUID | None = None
    # REQ-035 fields (backward-compatible defaults).
    trace_id: str = ""
    llm_call_id: str = ""
    badcase_id: str = ""
    score_dimensions: dict[str, float] = field(default_factory=dict)
    regression_delta: float | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: int = 0


@dataclass
class EvalReport:
    """Aggregate eval report (FR-013 + REQ-033 Sub-batch 1 + US9 fields).

    REQ-033 Sub-batch 1 additions (backward-compatible: all default to
    auto-generated values so 026 callers keep working):
    - ``run_id`` — stable UUID shared across local report, CI artifact,
      (future) LangSmith experiment, and badcase evidence.
    - ``started_at`` / ``finished_at`` — explicit ISO 8601 wall-clock
      timestamps (the legacy single ``timestamp`` field is preserved as
      an alias for ``finished_at``).
    - ``model_version`` — explicit versioned model identifier (e.g.
      ``"deepseek-v4-pro"``). Kept distinct from ``model`` which is the
      legacy mode-name string.

    REQ-033 US9 additions (T038):
    - ``version_context`` — full VersionContext (SC-010 unknown defaults).
    - ``aggregate_pass_rate`` — float in [0.0, 1.0], ``passed / total``.
    - ``known_regression_recall`` — float in [0.0, 1.0] (1.0 if no known
      regression cases in the suite; ``"unknown"`` if config is missing).
    - ``stale_case_count`` — int count of cases with status != 'active'.
    - ``source_revision`` — git SHA or "unknown" (FR-015).
    - ``branch`` — git branch or "unknown" (FR-015).
    - ``prompt_fingerprint`` — derived from prompt + tool defs + messages;
      ``"unknown"`` if derivation fails.
    - ``rubric_version`` — propagated from runner constructor.
    """

    timestamp: str
    git_sha: str
    model: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    skipped_cases: int
    per_node: dict[str, dict[str, float]] = field(default_factory=dict)
    case_results: list[CaseResult] = field(default_factory=list)
    # REQ-033 Sub-batch 1 fields (defaulted for backward compat).
    run_id: UUID = field(default_factory=uuid4)
    started_at: str = ""
    finished_at: str = ""
    model_version: str = ""
    # REQ-033 US9 fields (T038).
    version_context: VersionContext = field(
        default_factory=lambda: VersionContext.unknown(environment="LOCAL")
    )
    aggregate_pass_rate: float = 0.0
    known_regression_recall: float = 1.0
    stale_case_count: int = 0
    source_revision: str = "unknown"
    branch: str = "unknown"
    prompt_fingerprint: str = "unknown"
    rubric_version: str = "unknown"
    dataset_version: str = "golden-v1"
    langsmith_export_status: str = "DISABLED"
    langsmith_url: str = "unavailable"
    export_policy_decision_id: str | None = None
    # REQ-033 US5 (T049): nightly real-model budget tracking.
    total_budget: str = "unknown"
    budget_tokens_used: int = 0
    budget_cost_used_usd: float = 0.0
    nightly_real_model: bool = False
    environment: str = "LOCAL"
    # REQ-033 US5: explicit status (T049). Mirrors data-model.md §EvalRun
    # status enum: STARTED / PASSED / FAILED / INCOMPLETE / SYNCED /
    # SYNC_FAILED. ``None`` means "derive from failed_cases" (legacy
    # callers).
    status: str | None = None

    def to_json(self) -> str:
        """Serialize to JSON string per FR-013."""
        # asdict() recursively converts CaseResult dataclasses to dicts, so
        # the default fallback only handles unexpected non-serializable types.
        # ``run_id`` (UUID) is stringified explicitly for JSON safety.
        # ``version_context`` is a Pydantic model — convert via model_dump
        # to a camelCase dict for JSON consumers.
        payload = asdict(self)
        payload["run_id"] = str(self.run_id)
        # Replace the dataclass-as-dict rendering of VersionContext with
        # its proper to_dict() output (camelCase keys, JSON-safe).
        if isinstance(self.version_context, VersionContext):
            payload["version_context"] = self.version_context.to_dict()
        return json.dumps(
            payload,
            default=lambda obj: str(obj),
            ensure_ascii=False,
            indent=2,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return as plain dict (for structlog / programmatic consumers)."""
        result: dict[str, Any] = json.loads(self.to_json())
        return result


class _StubLLMClient:
    """Deterministic stub LLM client — yields the case's `llm_response`.

    Mimics the LLMResponse TypedDict shape so node code that does
    `result["content"]` works.
    """

    def __init__(self, response_content: str) -> None:
        self._content = response_content

    async def invoke(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "content": self._content,
            "model": "mock-llm",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "duration_ms": 0,
            "checkpoint_id": kwargs.get("checkpoint_id"),
        }

    async def invoke_stream(self, **kwargs: Any) -> Any:  # pragma: no cover
        yield self._content


class EvalRunner:
    """Replays golden cases through real graph nodes; produces EvalReport."""

    def __init__(
        self,
        cases: list[GoldenCase],
        mode: str = "mock",
        model_name: str = "mock-llm",
        *,
        environment: str = "LOCAL",
        release_stage: str = "DEVELOPMENT",
        app_version: str | None = None,
        schema_version: str = "v1",
        rubric_version: str = "unknown",
        dataset_version: str = "golden-v1",
        system_prompt: str = "",
        tool_defs: list[dict[str, Any]] | None = None,
        messages: list[dict[str, Any]] | None = None,
        branch: str | None = None,
        nightly_real_model: bool = False,
        budget_tokens: int | None = None,
        budget_cost_usd: float | None = None,
    ) -> None:
        self.cases = cases
        self.mode = mode
        self.model_name = model_name
        self.checker = ChineseFidelityChecker()
        # US9: version attribution (T038).
        self.environment = environment
        self.release_stage = release_stage
        self.app_version = app_version or self._detect_app_version()
        self.schema_version = schema_version
        self.rubric_version = rubric_version or "unknown"
        self.dataset_version = dataset_version or "golden-v1"
        self.branch = branch or self._detect_branch()
        # US5: nightly real-model budget tracking (T049).
        self.nightly_real_model = nightly_real_model
        self.budget_tokens = budget_tokens
        self.budget_cost_usd = budget_cost_usd
        # US9: prompt fingerprint derivation.
        try:
            self.prompt_fingerprint = compute_prompt_fingerprint(
                system_prompt=system_prompt,
                tool_defs=tool_defs or [],
                messages=messages or [],
            )
        except Exception:  # pragma: no cover — fail-open per SC-010
            self.prompt_fingerprint = "unknown"

    def check_budget(self) -> tuple[bool, str]:
        """Return ``(within_budget, reason)`` for the nightly real-model caps.

        Per FR-022 / SC-011: about 5M tokens or $50 per night, $1000/month.
        When ``nightly_real_model=False`` we always report within budget
        (no gate). When True, we compare ``budget_tokens`` and
        ``budget_cost_usd`` against the global caps from
        ``Settings.eval_nightly_*``.

        Returns:
            (True, "ok")   — within budget, safe to run.
            (False, reason) — budget exhausted; caller should mark run
                              INCOMPLETE and exit 1 (contracts §Eval Run).
        """
        if not self.nightly_real_model:
            return True, "ok"
        try:
            from app.core.config import get_settings

            settings = get_settings()
        except Exception:  # pragma: no cover — defensive
            return True, "settings_unavailable"

        cap_tokens = int(settings.eval_nightly_token_budget)
        cap_cost = float(settings.eval_nightly_cost_budget_usd)

        # Zero / negative caps (e.g. ops disabled nightly by setting both
        # budgets to 0) → treat as exhausted so the CLI exits 1 with
        # INCOMPLETE rather than burning real-model quota.
        if cap_tokens <= 0 or cap_cost <= 0:
            return False, (
                f"nightly budget cap is zero or negative "
                f"(tokens={cap_tokens}, cost=${cap_cost:.2f})"
            )

        if self.budget_tokens is not None and self.budget_tokens > cap_tokens:
            return False, (
                f"nightly token budget exceeded: "
                f"{self.budget_tokens} > {cap_tokens}"
            )
        if self.budget_cost_usd is not None and self.budget_cost_usd > cap_cost:
            return False, (
                f"nightly cost budget exceeded: "
                f"${self.budget_cost_usd:.2f} > ${cap_cost:.2f}"
            )
        return True, "ok"

    def build_incomplete_report(self, reason: str) -> EvalReport:
        """Build a minimal INCOMPLETE EvalReport (no cases run).

        Used by the CLI's budget-exhausted path (US5 SC-011). The returned
        report is structurally valid but contains zero case results and the
        provided reason. ``status`` is set to ``"INCOMPLETE"``.

        The ``reason`` parameter is currently accepted for forward-compat
        with downstream consumers (audit log, override-record linkage) and
        is preserved in the docstring only — the dataclass field set does
        not yet expose a free-form reason slot.
        """
        del reason  # see docstring; reserved for future audit linkage

        started = datetime.now(UTC)
        finished = started
        return EvalReport(
            timestamp=finished.isoformat(),
            git_sha="unknown",
            model=self.model_name,
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            skipped_cases=0,
            per_node={},
            case_results=[],
            run_id=uuid4(),
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            model_version=self.model_name,
            version_context=VersionContext(
                app_version=self.app_version,
                release_stage=self.release_stage,
                environment=self.environment,
                schema_version=self.schema_version,
                prompt_fingerprint=self.prompt_fingerprint,
                rubric_version=self.rubric_version,
                model=self.model_name,
            ),
            aggregate_pass_rate=0.0,
            known_regression_recall=1.0,
            stale_case_count=0,
            source_revision="unknown",
            branch=self.branch,
            prompt_fingerprint=self.prompt_fingerprint,
            rubric_version=self.rubric_version,
            dataset_version=self.dataset_version,
            environment=self.environment,
            total_budget=(
                f"{self.budget_tokens} tokens / ${self.budget_cost_usd:.2f}"
                if self.budget_tokens is not None and self.budget_cost_usd is not None
                else "unknown"
            ),
            budget_tokens_used=self.budget_tokens or 0,
            budget_cost_used_usd=self.budget_cost_usd or 0.0,
            nightly_real_model=self.nightly_real_model,
            status="INCOMPLETE",
        )

    @staticmethod
    def _detect_app_version() -> str:
        """Return ``__version__`` if available, else ``"unknown"`` (SC-010)."""
        try:
            from app import __version__ as app_version

            return str(app_version)
        except (ImportError, AttributeError):
            return "unknown"

    @staticmethod
    def _detect_branch() -> str:
        """Return current git branch, else ``"unknown"`` (SC-010)."""
        env_branch = os.environ.get("GIT_BRANCH", "").strip()
        if env_branch:
            return env_branch
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                if branch and branch != "HEAD":
                    return branch
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        return "unknown"

    async def run_case(self, case: GoldenCase) -> CaseResult:
        """Run a single golden case through the real node function.

        Steps:
        1. Skip stale cases (status != "active").
        2. Run fidelity checker on case.llm_response.
        3. If mode="mock": patch get_llm_client with stub.
        4. Invoke real node function (score_node / report_node).
        5. Validate expected_contains / expected_score_range.
        6. Handle expected_fidelity_pass=False reverse-assertion.
        """
        if case.status != "active":
            return CaseResult(
                case_id=case.case_id,
                node=case.node,
                passed=False,
                metrics={},
                actual_output={},
                failure_reasons=[f"stale_case_skipped:{case.status}"],
                label=case.label,
                expected_fidelity_pass=case.expected_fidelity_pass,
            )

        # 1. Fidelity check
        fidelity: ChineseFidelityResult = self.checker.check(
            case.llm_response, expected_language=case.expected_language
        )

        failure_reasons: list[str] = []

        # 2. Reverse-assertion for regression cases
        if not case.expected_fidelity_pass:
            # Case represents known-bad output; checker SHOULD flag it.
            if fidelity.is_correct:
                # Checker passed → that's a regression in the checker itself!
                failure_reasons.append(
                    "checker_failed_to_flag_expected_regression"
                )
            # Don't add "chinese_fidelity" to failures — the case is designed
            # to fail fidelity, so it's expected.
        else:
            # Normal case — fidelity must pass.
            if not fidelity.is_correct:
                failure_reasons.append("chinese_fidelity")

        # 3. Invoke real node with patched LLM client
        actual_output: dict[str, Any] = {}
        node_error: str | None = None
        try:
            actual_output = await self._invoke_node(case)
        except Exception as exc:
            node_error = f"{type(exc).__name__}:{exc}"
            failure_reasons.append(f"node_invocation_error:{node_error}")

        # 4. Validate expected_contains
        if case.expected_contains and not node_error:
            missing = self._missing_keywords(
                case.expected_contains, actual_output
            )
            if missing:
                failure_reasons.append(f"expected_contains_missing:{missing}")

        # 5. Validate score range
        if case.expected_score_range and not node_error:
            score_ok, actual_score = self._check_score_range(case, actual_output)
            if not score_ok:
                failure_reasons.append(
                    f"score_range_violation:expected={case.expected_score_range},"
                    f"actual={actual_score}"
                )

        # 6. Validate overall_score range
        if case.expected_overall_score_range and not node_error:
            overall_score_ok, overall_actual_score = self._check_overall_score_range(
                case, actual_output
            )
            if not overall_score_ok:
                failure_reasons.append(
                    f"overall_score_range_violation:expected="
                    f"{case.expected_overall_score_range},actual={overall_actual_score}"
                )

        passed = len(failure_reasons) == 0
        metrics = {
            "chinese_fidelity": fidelity.score,
            "chinese_ratio": fidelity.chinese_ratio,
            "english_ratio": fidelity.english_ratio,
        }

        # REQ-035: extract debug/usage ids from case.input_state.
        trace_id = str(case.input_state.get("trace_id", ""))
        llm_call_id = str(case.input_state.get("llm_call_id", ""))
        badcase_id = str(case.input_state.get("badcase_id", ""))
        regression_delta: float | None = case.input_state.get("regression_delta")
        usage = case.input_state.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        estimated_cost = float(usage.get("estimated_cost", 0.0))
        latency_ms = int(usage.get("latency_ms", 0))

        # REQ-035: score_dimensions from actual_output + fidelity.
        score_dimensions: dict[str, float] = dict(
            actual_output.get("score_dimensions") or {}
        )
        score_dimensions["chinese_fidelity"] = fidelity.score

        return CaseResult(
            case_id=case.case_id,
            node=case.node,
            passed=passed,
            metrics=metrics,
            actual_output=actual_output,
            failure_reasons=failure_reasons,
            label=case.label,
            expected_fidelity_pass=case.expected_fidelity_pass,
            trace_id=trace_id,
            llm_call_id=llm_call_id,
            badcase_id=badcase_id,
            score_dimensions=score_dimensions,
            regression_delta=regression_delta,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
        )

    async def run_all(self) -> EvalReport:
        """Run all cases; return aggregate EvalReport.

        REQ-033 Sub-batch 1: assigns a stable ``run_id`` (UUID4) at the
        start of the run, stamps ``started_at`` / ``finished_at`` ISO
        timestamps, and attaches the same ``run_id`` to every per-case
        ``CaseResult.run_id`` so downstream consumers (CI artifact
        parser, future LangSmith reporter, badcase evidence) can join
        rows back to the parent run.

        REQ-033 US9 (T038): also computes aggregate fields
        (``aggregate_pass_rate``, ``known_regression_recall``,
        ``stale_case_count``) and stamps the ``version_context`` with
        the runner's environment / release stage / app version /
        model / rubric version / prompt fingerprint.
        """
        run_id = uuid4()
        started_at = datetime.now(UTC)
        results: list[CaseResult] = []
        for case in self.cases:
            result = await self.run_case(case)
            if result.run_id is None:
                result.run_id = run_id
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        skipped = sum(
            1 for r in results
            if any("stale_case_skipped" in fr for fr in r.failure_reasons)
        )
        failed = sum(
            1 for r in results
            if not r.passed
            and not any("stale_case_skipped" in fr for fr in r.failure_reasons)
        )

        per_node = self._aggregate_per_node(results)

        finished_at = datetime.now(UTC)

        # US9: aggregate pass rate (0.0 if no cases).
        total = len(results)
        aggregate_pass_rate = float(passed) / float(total) if total else 0.0

        # US9: stale case count = number of non-active cases that were skipped.
        stale_case_count = skipped

        # US9: known regression recall = fraction of
        # expected_fidelity_pass=False cases that were correctly flagged.
        # If no regression cases in the suite, default to 1.0 (no missed).
        regression_cases = [r for r in results if r.expected_fidelity_pass is False]
        if regression_cases:
            correctly_flagged = sum(
                1 for r in regression_cases
                if any("chinese_fidelity" in fr for fr in r.failure_reasons)
            )
            known_regression_recall = float(correctly_flagged) / float(
                len(regression_cases)
            )
        else:
            known_regression_recall = 1.0

        # US9: build version context from runner config.
        version_context = VersionContext(
            app_version=self.app_version,
            release_stage=self.release_stage,
            environment=self.environment,
            schema_version=self.schema_version,
            prompt_fingerprint=self.prompt_fingerprint,
            rubric_version=self.rubric_version,
            model=self.model_name,
        )

        return EvalReport(
            timestamp=finished_at.isoformat(),
            git_sha=_get_git_sha(),
            model=self.model_name,
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            skipped_cases=skipped,
            per_node=per_node,
            case_results=results,
            run_id=run_id,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            model_version=self.model_name,
            version_context=version_context,
            aggregate_pass_rate=aggregate_pass_rate,
            known_regression_recall=known_regression_recall,
            stale_case_count=stale_case_count,
            source_revision=_get_git_sha(),
            branch=self.branch,
            prompt_fingerprint=self.prompt_fingerprint,
            rubric_version=self.rubric_version,
            dataset_version=self.dataset_version,
            environment=self.environment,
            total_budget=(
                f"{self.budget_tokens} tokens / ${self.budget_cost_usd:.2f}"
                if self.nightly_real_model
                and self.budget_tokens is not None
                and self.budget_cost_usd is not None
                else "unknown"
            ),
            budget_tokens_used=self.budget_tokens or 0,
            budget_cost_used_usd=self.budget_cost_usd or 0.0,
            nightly_real_model=self.nightly_real_model,
        )

    # ------------------------------------------------------------------
    # Node invocation
    # ------------------------------------------------------------------
    async def _invoke_node(self, case: GoldenCase) -> dict[str, Any]:
        """Invoke the real node function with LLM client stubbed.

        The node function reads `state` (case.input_state), calls
        `get_llm_client().invoke(...)` which we patch to yield
        `case.llm_response`, and returns a state-update dict.

        REQ-040 US2 FR-004: ``score`` was split into ``score_llm`` (LLM)
        and ``sink_error`` (DB). The eval suite invokes the LLM-only
        ``score_llm`` directly; ``sink_error`` is not exercised here
        because it requires a real DB connection.
        """
        state = dict(case.input_state)
        node = case.node

        stub = _StubLLMClient(case.llm_response)

        if node == "interview.score" or node == "interview.score_llm":
            return await self._invoke_score_llm_node(state, stub)
        if node == "interview.report":
            return await self._invoke_report_node(state, stub)

        # REQ-061 US11 (T143): dispatch registered stub capabilities.
        # Interview live paths above are unchanged; stubs never call graphs.
        from app.eval.capability_registry import get_capability_registry

        registry = get_capability_registry()
        handler = registry.get_handler(node)
        if handler is not None:
            return await handler(state, llm_response=case.llm_response)
        entry = registry.get_by_node(node)
        if entry is not None and entry.stub:
            return {
                "node": node,
                "stub": True,
                "echo_state_keys": sorted(state.keys()),
                "status": "ok",
            }
        raise ValueError(f"unsupported_node:{node}")

    async def _invoke_score_llm_node(
        self, state: dict[str, Any], stub: _StubLLMClient
    ) -> dict[str, Any]:
        """Invoke interview.nodes.score_llm.score_llm_node with patched deps.

        REQ-040 US2 FR-004: ``score_llm_node`` is the LLM-only path; the
        DB write (``sink_error``) is a separate node and is NOT invoked
        from the eval suite.
        """
        from app.agents.interview.nodes.score_llm import score_llm_node

        with patch(
            "app.agents.interview.nodes.score_llm.get_llm_client", return_value=stub
        ):
            return await score_llm_node(state)

    async def _invoke_report_node(
        self, state: dict[str, Any], stub: _StubLLMClient
    ) -> dict[str, Any]:
        """Invoke interview.nodes.report.report_node with patched deps."""
        from app.agents.interview.nodes.report import report_node

        with patch(
            "app.agents.interview.nodes.report.get_llm_client", return_value=stub
        ):
            return await report_node(state)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _missing_keywords(
        keywords: list[str], actual_output: dict[str, Any]
    ) -> list[str]:
        """Return keywords that don't appear anywhere in actual_output's string repr."""
        # Flatten actual_output to a searchable string (handles nested dicts/lists).
        haystack = json.dumps(actual_output, ensure_ascii=False)
        return [kw for kw in keywords if kw not in haystack]

    @staticmethod
    def _check_score_range(
        case: GoldenCase, actual_output: dict[str, Any]
    ) -> tuple[bool, int | None]:
        """For score_node: extract last score's `score` and check range."""
        scores = actual_output.get("scores", [])
        if not scores:
            return False, None
        last_score = scores[-1].get("score")
        if last_score is None:
            return False, None
        lo, hi = case.expected_score_range or (0, 10)
        return lo <= int(last_score) <= hi, int(last_score)

    @staticmethod
    def _check_overall_score_range(
        case: GoldenCase, actual_output: dict[str, Any]
    ) -> tuple[bool, float | None]:
        """For report_node: extract overall_score and check range."""
        overall = actual_output.get("overall_score")
        if overall is None:
            return False, None
        lo, hi = case.expected_overall_score_range or (0.0, 10.0)
        return lo <= float(overall) <= hi, float(overall)

    @staticmethod
    def _aggregate_per_node(results: list[CaseResult]) -> dict[str, dict[str, float]]:
        """Per-node aggregate metrics: pass_rate + avg_fidelity."""
        per_node: dict[str, dict[str, float]] = {}
        node_buckets: dict[str, list[CaseResult]] = {}
        for r in results:
            node_buckets.setdefault(r.node, []).append(r)

        for node, bucket in node_buckets.items():
            total = len(bucket)
            passed = sum(1 for r in bucket if r.passed)
            avg_fidelity = (
                sum(r.metrics.get("chinese_fidelity", 0.0) for r in bucket) / total
                if total
                else 0.0
            )
            per_node[node] = {
                "total": float(total),
                "passed": float(passed),
                "pass_rate": round(passed / total, 4) if total else 0.0,
                "avg_chinese_fidelity": round(avg_fidelity, 4),
            }
        return per_node


async def _noop_sink(*args: Any, **kwargs: Any) -> None:
    """No-op replacement for `_sink_to_error_book` — eval suite skips DB.

    The real `_sink_to_error_book` writes low-scoring answers to
    `error_questions` table. Eval suite doesn't need DB, so we stub it out.
    """
    return None


def _get_git_sha() -> str:
    """Read current git SHA for eval report (FR-013).

    Tries `git rev-parse HEAD`; falls back to env var `GIT_SHA`; finally
    "unknown".
    """
    env_sha = os.environ.get("GIT_SHA", "").strip()
    if env_sha:
        return env_sha

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


__all__ = ["CaseResult", "EvalReport", "EvalRunner", "run_eval_suite"]


async def run_eval_suite(
    cases: list[GoldenCase],
    *,
    mode: str = "mock",
    model_name: str = "mock-llm",
    environment: str = "LOCAL",
    release_stage: str = "DEVELOPMENT",
    app_version: str | None = None,
    schema_version: str = "v1",
    rubric_version: str = "unknown",
    dataset_version: str = "golden-v1",
    system_prompt: str = "",
    tool_defs: list[dict[str, Any]] | None = None,
    messages: list[dict[str, Any]] | None = None,
    branch: str | None = None,
    nightly_real_model: bool = False,
    budget_tokens: int | None = None,
    budget_cost_usd: float | None = None,
) -> EvalReport:
    """Convenience wrapper: build an ``EvalRunner`` and run all cases.

    REQ-033 Sub-batch 1: a single function-level entry point so callers
    (CLI, CI scripts, future LangSmith reporter) don't need to know about
    the ``EvalRunner`` class itself. The returned ``EvalReport.run_id``
    is the single stable identifier to join across local + remote.

    REQ-033 US9 (T038): accepts the version attribution kwargs and
    forwards them to ``EvalRunner.__init__``. All kwargs are optional —
    legacy callers that pass only ``cases / mode / model_name`` continue
    to work and get ``"unknown"`` defaults for all version fields.

    REQ-033 US5 (T049): accepts ``nightly_real_model``,
    ``budget_tokens``, ``budget_cost_usd`` for budget-gated nightly
    runs. The runner checks caps via ``EvalRunner.check_budget`` and
    stamps ``total_budget`` / ``nightly_real_model`` fields on the
    report.
    """
    runner = EvalRunner(
        cases=cases,
        mode=mode,
        model_name=model_name,
        environment=environment,
        release_stage=release_stage,
        app_version=app_version,
        schema_version=schema_version,
        rubric_version=rubric_version,
        dataset_version=dataset_version,
        system_prompt=system_prompt,
        tool_defs=tool_defs,
        messages=messages,
        branch=branch,
        nightly_real_model=nightly_real_model,
        budget_tokens=budget_tokens,
        budget_cost_usd=budget_cost_usd,
    )
    return await runner.run_all()
