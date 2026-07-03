"""[AC-040-US2 FR-006] @traced_node coverage + OTel span verification tests.

Coverage:
- AC-6.1: every LangGraph node function has @traced_node applied.
- AC-6.2: the @traced_node name parameter is `{agent}.{role}_{action}`
  (no `node.` prefix — that is added by the decorator).
- AC-6.3: each decorated node produces an OTel span named
  ``node.{agent}.{role}_{action}``.
- AC-6.4: @traced_node does not break existing node behavior
  (covered by the full backend pytest suite passing).
- AC-6.5: on exception, the OTel span is marked ERROR + record_exception
  + re-raised.

AC-3.5 / AC-E2E-2: span names visible in LangSmith follow the
``node.{agent}.{role}_{action}`` convention (single ``node.`` prefix).
"""
from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# AC-6.1 + AC-6.2: @traced_node presence + name format on every leaf node.
# ---------------------------------------------------------------------------


# Expected node-name → file path mapping (relative to backend/).
LEAF_NODE_FILES: list[tuple[str, str, str]] = [
    # (path, function_name, expected_traced_node_name)
    ("app/agents/interview/nodes/intake.py", "intake_node", "interview.intake_locate"),
    ("app/agents/interview/nodes/question_gen.py", "question_gen_node", "interview.question_gen"),
    ("app/agents/interview/nodes/score_llm.py", "score_llm_node", "interview.score_llm"),
    ("app/agents/interview/nodes/sink_error.py", "sink_error_node", "interview.sink_error"),
    ("app/agents/interview/nodes/report.py", "report_node", "interview.report"),
    ("app/agents/nodes/ability_diagnose/aggregate_scores.py", "aggregate_scores_node", "ability_diagnose.aggregate_scores"),
    ("app/agents/nodes/ability_diagnose/compare_baseline.py", "compare_baseline_node", "ability_diagnose.compare_baseline"),
    ("app/agents/nodes/ability_diagnose/generate_insight.py", "generate_insight_node", "ability_diagnose.generate_insight"),
    ("app/agents/nodes/ability_diagnose/update_dim_db.py", "update_dim_db_node", "ability_diagnose.update_dim_db"),
    ("app/agents/nodes/ability_diagnose/update_history.py", "update_history_node", "ability_diagnose.update_history"),
    ("app/agents/nodes/ability_diagnose/update_activities.py", "update_activities_node", "ability_diagnose.update_activities"),
    ("app/agents/nodes/ability_diagnose/ws_push.py", "ws_push_node", "ability_diagnose.ws_push"),
    ("app/agents/nodes/ability_diagnose/update_dim_error_log.py", "update_dim_error_log_node", "ability_diagnose.update_dim_error_log"),
    ("app/agents/nodes/error_coach/fetch_question.py", "fetch_question_node", "error_coach.fetch_question"),
    ("app/agents/nodes/error_coach/hint_ladder.py", "hint_ladder_node", "error_coach.hint_ladder"),
    ("app/agents/nodes/error_coach/evaluate.py", "evaluate_node", "error_coach.evaluate"),
    ("app/agents/nodes/error_coach/loop_or_finish.py", "loop_or_finish_node", "error_coach.loop_or_finish"),
    ("app/agents/nodes/general_coach/intent.py", "intent_node", "general_coach.intent"),
    ("app/agents/nodes/general_coach/route.py", "route_node", "general_coach.route"),
    ("app/agents/nodes/general_coach/respond.py", "respond_node", "general_coach.respond"),
    ("app/agents/nodes/resume_optimize/load_branch.py", "load_branch_node", "resume_optimize.load_branch"),
    ("app/agents/nodes/resume_optimize/diff_jd.py", "diff_jd_node", "resume_optimize.diff_jd"),
    ("app/agents/nodes/resume_optimize/suggest_blocks.py", "suggest_blocks_node", "resume_optimize.suggest_blocks"),
    ("app/agents/nodes/resume_optimize/apply_or_discard.py", "apply_or_discard_node", "resume_optimize.apply_or_discard"),
    ("app/agents/nodes/resume_optimize/snapshot.py", "snapshot_node", "resume_optimize.snapshot"),
]


@pytest.mark.parametrize(
    "rel_path,func_name,expected_name",
    LEAF_NODE_FILES,
    ids=[t[0] for t in LEAF_NODE_FILES],
)
def test_traced_node_present_on_each_leaf(rel_path: str, func_name: str, expected_name: str) -> None:
    """AC-6.1: every leaf node function is decorated with @traced_node."""
    src = Path(rel_path).read_text(encoding="utf-8")
    # Find the function definition line (not the decorator).
    fn_pattern = rf"^async def {func_name}\("
    fn_match = re.search(fn_pattern, src, re.MULTILINE)
    assert fn_match, f"{func_name} not found in {rel_path}"
    # Look for @traced_node("...") within the lines directly above the
    # function definition. Scan 10 lines back from the function header.
    fn_line_start = src.rfind("\n", 0, fn_match.start()) + 1
    # Walk backwards line-by-line, looking for the decorator.
    body = src[:fn_line_start]
    lines = body.splitlines()
    found = False
    for i in range(len(lines) - 1, max(len(lines) - 12, -1), -1):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@traced_node"):
            # Validate the name argument matches expected_name.
            decorator_match = re.match(
                rf'@traced_node\(\s*[\'\"]{re.escape(expected_name)}[\'\"]\s*\)',
                line,
            )
            if decorator_match:
                found = True
                break
        # Stop scanning once we hit a non-decorator, non-empty line.
        if not line.startswith("@"):
            break
    assert found, (
        f"{func_name} in {rel_path} is missing @traced_node('{expected_name}') "
        f"directly above the function definition"
    )


def test_traced_node_total_count_matches_leaf_files() -> None:
    """AC-6.1: every leaf-node file has exactly one @traced_node decorator.

    Actual count: 25 leaf nodes across 5 agents (interview: 5, ability_diagnose: 8,
    error_coach: 4, general_coach: 3, resume_optimize: 5). The AC matrix's
    "22 nodes" baseline pre-dates the FR-004 split (score_llm + sink_error)
    and the FR-005 split (update_dimensions → 4 + 1 error log). The exact
    count is therefore the number of leaf-node files enumerated in
    LEAF_NODE_FILES.
    """
    total = 0
    for rel_path, func_name, _ in LEAF_NODE_FILES:
        src = Path(rel_path).read_text(encoding="utf-8")
        # Match @traced_node(...) directly above async def <func_name>(
        pattern = rf'@traced_node\([^)]+\)\s*\nasync def {func_name}\('
        total += len(re.findall(pattern, src))
    assert total == len(LEAF_NODE_FILES), (
        f"expected {len(LEAF_NODE_FILES)} @traced_node decorators across leaf files, found {total}"
    )


def test_traced_node_name_format_no_node_prefix() -> None:
    """AC-6.2: name parameter does NOT include the literal 'node.' prefix."""
    bad: list[str] = []
    for rel_path, _, _ in LEAF_NODE_FILES:
        src = Path(rel_path).read_text(encoding="utf-8")
        for match in re.finditer(r'@traced_node\(\s*[\'"]([^\'"]+)[\'"]\s*\)', src):
            name = match.group(1)
            if name.startswith("node."):
                bad.append(f"{rel_path}: @traced_node('{name}')")
    assert not bad, "Decorators with leading 'node.' prefix found:\n" + "\n".join(bad)


# ---------------------------------------------------------------------------
# AC-6.5 + AC-3.5 / AC-E2E-2: OTel span verification (no fail-open noop).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_traced_node_marks_span_error_on_exception() -> None:
    """AC-6.5: when a node raises, the OTel span is marked ERROR + record_exception."""
    from app.observability import traced_node, init_tracing, TracingConfig, get_in_memory_exporter
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    # Initialize with in-memory exporter so we can inspect spans.
    init_tracing(TracingConfig(service_name="test", exporter="in_memory"))
    exporter = get_in_memory_exporter()
    assert isinstance(exporter, InMemorySpanExporter), "exporter must be initialized"
    exporter.clear()

    @traced_node("test.error_marker")
    async def raising_node(state: dict) -> dict:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await raising_node({"x": 1})

    spans = exporter.get_finished_spans()
    error_spans = [s for s in spans if s.name == "node.test.error_marker"]
    assert error_spans, f"expected a 'node.test.error_marker' span, got {[s.name for s in spans]}"
    span = error_spans[0]
    # Status should be ERROR (StatusCode.ERROR = 2).
    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR, (
        f"span status was {span.status.status_code}; expected ERROR"
    )
    # record_exception should have populated span.events with an exception event.
    exc_events = [e for e in span.events if e.name == "exception"]
    assert exc_events, "span must have an 'exception' event from record_exception"


@pytest.mark.asyncio
async def test_traced_node_span_names_match_naming_convention() -> None:
    """AC-3.5: span names follow ``node.{agent}.{role}_{action}`` (single ``node.``)."""
    from app.observability import traced_node, init_tracing, TracingConfig, get_in_memory_exporter
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    init_tracing(TracingConfig(service_name="test", exporter="in_memory"))
    exporter = get_in_memory_exporter()
    assert isinstance(exporter, InMemorySpanExporter), "exporter must be initialized"
    exporter.clear()

    @traced_node("acme.test_action")
    async def ok_node(state: dict) -> dict:
        return state

    @traced_node("acme.fail_action")
    async def fail_node(state: dict) -> dict:
        raise ValueError("nope")

    await ok_node({"x": 1})
    with pytest.raises(ValueError):
        await fail_node({"x": 1})

    span_names = {s.name for s in exporter.get_finished_spans()}
    assert "node.acme.test_action" in span_names, (
        f"expected 'node.acme.test_action' in span names, got {span_names}"
    )
    assert "node.acme.fail_action" in span_names, (
        f"expected 'node.acme.fail_action' in span names, got {span_names}"
    )
    # Must not contain double "node." prefix.
    assert "node.node.acme.test_action" not in span_names, (
        "span name must not have double 'node.' prefix"
    )


@pytest.mark.asyncio
async def test_all_nodes_produce_otel_span() -> None:
    """AC-6.3: every decorated node produces an OTel span with the expected name."""
    from app.observability import init_tracing, TracingConfig, get_in_memory_exporter
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    init_tracing(TracingConfig(service_name="test", exporter="in_memory"))
    exporter = get_in_memory_exporter()
    assert isinstance(exporter, InMemorySpanExporter), "exporter must be initialized"
    exporter.clear()

    # Invoke every leaf node via its module. We don't need real state — the
    # nodes that touch DB / LLM will fail at the first await; that's fine,
    # we only care that the span was opened.
    import importlib

    seen: set[str] = set()
    for rel_path, func_name, expected_name in LEAF_NODE_FILES:
        module_path = rel_path.removesuffix(".py").replace("/", ".")
        module = importlib.import_module(module_path)
        func = getattr(module, func_name, None)
        assert func is not None, f"{func_name} not found in {module_path}"
        # Reset exporter between nodes to isolate spans.
        exporter.clear()
        try:
            await func({})
        except Exception:
            pass
        span_names = {s.name for s in exporter.get_finished_spans()}
        expected_span_name = f"node.{expected_name}"
        if expected_span_name not in span_names:
            # Some nodes may complete instantly (no await); the span should
            # still be open. Try awaiting once more.
            pass
        seen.update(span_names)

    # Across all invocations we should have seen >= 21 of the 22 expected
    # span names. (Some nodes with side-effect-free branches may finish
    # before the span is recorded; the @traced_node decorator still
    # guarantees the span opens.)
    expected_spans = {f"node.{name}" for _, _, name in LEAF_NODE_FILES}
    missing = expected_spans - seen
    assert not missing, f"missing OTel spans for: {sorted(missing)}"


@pytest.mark.asyncio
async def test_all_node_spans_present_in_trace() -> None:
    """AC-E2E-2: spans for ALL 22 nodes are observable in the OTel exporter."""
    from app.observability import init_tracing, TracingConfig, get_in_memory_exporter
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    import importlib

    init_tracing(TracingConfig(service_name="test", exporter="in_memory"))
    exporter = get_in_memory_exporter()
    assert isinstance(exporter, InMemorySpanExporter), "exporter must be initialized"
    exporter.clear()

    expected_spans: set[str] = set()
    for _, _, name in LEAF_NODE_FILES:
        expected_spans.add(f"node.{name}")

    for rel_path, func_name, _ in LEAF_NODE_FILES:
        module_path = rel_path.removesuffix(".py").replace("/", ".")
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        try:
            await func({})
        except Exception:
            # Side-effect failure is acceptable; span was opened before raise.
            pass

    span_names = {s.name for s in exporter.get_finished_spans()}
    missing = expected_spans - span_names
    assert not missing, (
        f"AC-E2E-2: missing OTel spans for {len(missing)} nodes: {sorted(missing)[:10]}"
    )