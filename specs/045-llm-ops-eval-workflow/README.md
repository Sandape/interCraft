# REQ-045 LLM Ops Eval Workflow

Status: active / draft

Source of truth: [spec.md](./spec.md)

## Purpose

REQ-045 turns the current partial eval, tracing, LangSmith, redaction,
dashboard, and badcase pieces into one explicit LLM Ops workflow requirement:
OpenTelemetry is the canonical correlation and observability layer, while
LangSmith is an optional AI debugging and evaluation workbench layered on top.

## Current Audit Summary

- Existing evals provide deterministic local reports for a narrow set of
  interview scoring/reporting cases.
- Existing trace helpers and node decorators provide a useful base, but runtime
  trace initialization, request/job propagation, LLM invocation correlation, and
  persisted trace ids are not yet complete end to end.
- Existing report contracts already expose trace id, artifact reference, and
  LangSmith URL fields, but LangSmith URLs still default to unavailable.
- Existing redaction and retention helpers are useful, but external export
  policy is not yet enforced as the mandatory pre-export path, including the
  newly clarified production full-content LangSmith export path.
- Existing PM/admin surfaces can display version and experiment concepts, but
  A/B assignment, judge feedback, and LangSmith experiment evidence are not yet
  fully connected.

## Scope Boundary

Included:

- Trace-linked eval reports
- OTel-first trace/run correlation
- Optional LangSmith dataset/experiment sync
- LLM-as-Judge rubrics and calibration
- Experiment comparison and A/B attribution
- Redaction, retention, and export audit
- Production full-content LangSmith export with explicit policy metadata
- Badcase-to-eval promotion
- Human-reviewed prompt/rubric improvement proposals

Excluded:

- Admin console redesign
- Checkpointer pooling
- Automatic prompt deployment
- Automatic golden baseline refresh
- Unrelated agent runtime refactors

## Production LangSmith Policy

Production is allowed to send complete unredacted AI payloads to LangSmith when
the destination policy is explicitly enabled. This includes resumes, job
descriptions, interview free text, LLM inputs, and LLM outputs. It still excludes
application secrets, credentials, access tokens, and infrastructure passwords.

## Related Specs

- REQ-026 Agent Eval-Driven Self-Improvement Loop
- REQ-029 OpenTelemetry & LangGraph Distributed Trace
- REQ-033 Eval + PM Dashboard V1
- REQ-043 Agent Production Refactor
- REQ-044 Admin Console Redesign
