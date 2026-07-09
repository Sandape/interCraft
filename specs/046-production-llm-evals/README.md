# REQ-046 Production-Grade LLM Evals

Status: active / draft

Source of truth: [spec.md](./spec.md)

## Purpose

REQ-046 raises the REQ-045 LLM Ops Eval foundation to a production-grade LLM
Evals operating system. REQ-045 proved local eval gates, OTel-first
correlation, governed export, run-level LangSmith sync, report-only judge,
experiment comparison, badcase promotion, and prompt proposals. REQ-046 defines
the missing production closure: real LangSmith Dataset + Experiment evidence,
stable URLs, release gates, SLOs, alerts, production export governance,
expanded coverage, calibrated judge promotion, and operator evidence views.

## Current Gap

- LangSmith upload has been verified as a trace/run-level record, but not yet
  as a complete Dataset + Experiment + Evaluation Results workflow.
- Current reports can show `url: unavailable`; production evidence needs
  clickable LangSmith URLs or explicit incomplete evidence state.
- Eval gates exist but need production release readiness semantics, owner
  decisions, nightly health, and full-suite blocker handling.
- Judge feedback is report-only; production blocking requires calibration,
  drift review, and human-owned promotion.
- Export policy allows production LangSmith full-content payloads, but ongoing
  access, retention, and secret-leak audit must be operationalized.
- Operators need one evidence view rather than stitching together local command
  output, screenshots, trace pages, and LangSmith pages.

## Scope Boundary

Included:

- Verified LangSmith Dataset / Experiment / Run / Feedback evidence
- Production release gates and release-candidate evidence
- Eval SLOs, health states, and alerts
- Production full-content export audit and retention/access review
- High-risk AI surface coverage inventory
- Judge calibration and drift governance
- Operator evidence view and production operation guide

Excluded:

- Automatic prompt deployment
- Automatic golden baseline refresh
- General admin console redesign
- Replacing local eval artifacts with LangSmith as the only source of truth

## Related Specs

- REQ-045 LLM Ops Eval Workflow
- REQ-033 Eval + PM Dashboard V1
- REQ-029 OpenTelemetry & LangGraph Distributed Trace
- REQ-038 LLM Structured Output Hardening
- REQ-043 Agent Production Refactor
- REQ-044 Admin Console Redesign
