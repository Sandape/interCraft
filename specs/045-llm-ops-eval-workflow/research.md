# Research: REQ-045 LLM Ops Eval Workflow

## Sources Reviewed

- LangSmith OpenTelemetry tracing: <https://docs.langchain.com/langsmith/trace-with-opentelemetry>
- LangSmith evaluation with OpenTelemetry: <https://docs.langchain.com/langsmith/evaluate-with-opentelemetry>
- LangSmith OTel gateway redaction: <https://docs.langchain.com/langsmith/otel-gateway-trace-redaction>
- OpenTelemetry Python instrumentation: <https://opentelemetry.io/docs/languages/python/instrumentation/>
- OpenTelemetry Collector configuration: <https://opentelemetry.io/docs/collector/configuration/>

## Decision 1: OTel Is Canonical, LangSmith Is Assisted

**Decision**: Treat OpenTelemetry-compatible trace identity as the canonical
correlation layer. LangSmith receives traces and eval evidence as an assisted AI
workbench, not as the only observability store.

**Rationale**: REQ-045 needs company-wide system monitoring and AI-specific
debugging. OTel gives vendor-neutral trace propagation, collector fanout, and
compatibility with traditional monitoring. LangSmith adds LLM-specialized
dataset, experiment, run, and evaluator workflows.

**Alternatives considered**:

- LangSmith-only tracing: rejected because system stability, HTTP/WS/ARQ
  propagation, and non-LLM telemetry still need a neutral observability layer.
- Traditional monitoring only: rejected because generic traces do not provide
  enough AI-specific dataset, experiment, and judge workflows.

## Decision 2: Collector/Fanout Topology For External Trace Export

**Decision**: Plan for application spans to be exported through an
OTLP-compatible path that can fan out to generic observability backends and
LangSmith. Direct LangSmith API usage is reserved for dataset, experiment,
feedback, and deep-link enrichment when OTLP alone is not enough.

**Rationale**: A collector/fanout boundary keeps app code from knowing every
destination, allows destination policy decisions, and preserves the OTel-first
model. LangSmith-specific APIs are still useful for experiment metadata and
judge feedback that are not pure trace spans.

**Alternatives considered**:

- Direct in-process export to every backend: rejected because it couples app
  runtime to destination-specific logic and makes policy enforcement harder.
- Collector-only for all LangSmith concepts: rejected because datasets,
  experiments, and feedback are LangSmith domain objects, not just spans.

## Decision 3: Production Full-Content LangSmith Export Is Allowed By Policy

**Decision**: Production LangSmith export may include complete unredacted AI
payloads when an explicit full-content destination policy is enabled. Operational
secrets, access tokens, credentials, and infrastructure passwords remain
non-exportable.

**Rationale**: The user clarified that production LangSmith should support full
debug fidelity. The safe boundary is therefore not "always redact production",
but "authorize the destination and representation level explicitly, audit it,
and keep operational secrets out."

**Alternatives considered**:

- Production metadata-only: rejected by clarified product requirement.
- Full-content export to any external destination: rejected because generic
  observability backends and accidental destinations should not receive raw AI
  payloads without explicit authorization.

## Decision 4: Local Eval Artifacts Stay Canonical

**Decision**: Local JSON/Markdown eval reports and repository-managed datasets
remain the CI source of truth. LangSmith sync status is recorded separately and
does not change local verdicts.

**Rationale**: CI must work without external credentials, network availability,
or LangSmith service health. LangSmith adds drilldown and collaboration value
but should not make local regression protection brittle.

**Alternatives considered**:

- Make LangSmith the only eval store: rejected because disabled/offline and CI
  reproducibility paths are mandatory.
- Skip LangSmith sync for CI: rejected because deep links and experiment history
  are central to REQ-045.

## Decision 5: Trace/Run Identity Must Be Explicit In Records

**Decision**: Every covered eval case and AI invocation should carry explicit
run id and trace id fields. W3C trace context is the propagation standard;
existing `X-Trace-Id` behavior is treated as backward-compatible display or
ingress compatibility, not the canonical context model.

**Rationale**: Reports, logs, metrics, traces, AI invocation records, PM
dashboards, and LangSmith runs need a stable join key. Current custom trace
headers are useful but insufficient without OTel context propagation.

**Alternatives considered**:

- Generate separate IDs per subsystem: rejected because drilldown requires
  one correlation envelope.
- Infer trace ids from logs after the fact: rejected because missing IDs are
  exactly what this feature must prevent.

## Decision 6: Deterministic Checks Block First, Judge Blocks Later

**Decision**: Deterministic eval checks remain the primary blocking gate. LLM
judge rubrics are report-only until they meet calibration thresholds or have an
explicit owner waiver.

**Rationale**: LLM-as-Judge is valuable for subjective quality dimensions, but
uncalibrated judge output can create false confidence or noisy gates.

**Alternatives considered**:

- Judge as immediate merge gate: rejected because calibration and human labels
  are required by the spec.
- Deterministic-only forever: rejected because coaching usefulness,
  groundedness, and agent task success are not fully captured by deterministic
  checks.

## Decision 7: Experiment Comparison Is A First-Class Artifact

**Decision**: Baseline/candidate comparison should produce a durable report
that includes quality, regression, cost, latency, judge feedback, confidence
warnings, and source revision fields.

**Rationale**: REQ-045 is not just observability. It should support product and
AI iteration decisions by comparing variants against the same datasets.

**Alternatives considered**:

- Dashboard-only comparison: rejected because CI and review workflows need
  portable artifacts.
- LangSmith-only comparison: rejected because local artifacts are canonical.

## Decision 8: Badcase Promotion Is Candidate-First

**Decision**: Production/staging badcases become candidate eval cases first.
They may appear in report-only datasets, but cannot block merges until accepted
as golden cases.

**Rationale**: Real-world failures are valuable but can be noisy, sensitive, or
non-reproducible. Candidate-first promotion gives humans a quality gate.

**Alternatives considered**:

- Auto-promote every badcase to golden: rejected due to noise and governance.
- Manual golden-only authoring: rejected because production feedback would not
  reliably close the loop.

## Decision 9: Prompt Improvements Remain Human-Approved

**Decision**: Failed eval clusters and judge feedback may generate prompt or
rubric proposals, but proposals cannot auto-deploy or auto-refresh baselines.

**Rationale**: This delivers the self-improvement loop without turning it into
an uncontrolled autonomous prompt deployment system.

**Alternatives considered**:

- Automatic prompt deployment: rejected by REQ-045 scope.
- No proposal workflow: rejected because evidence-backed iteration is a core
  value of the system.
