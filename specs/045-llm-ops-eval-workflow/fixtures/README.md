# REQ-045 Fixtures

This directory stores stable sample payloads for the LLM Ops eval workflow.

Planned fixtures:

- `eval-report-sample.json`: local canonical eval report with optional
  LangSmith references.
- `export-policy-sample.json`: destination policy audit input covering
  production full-content LangSmith export, generic OTLP export, and secret
  blocking.
- `badcase-candidate.json`: governed badcase promotion candidate.
- `prompt-proposal.json`: human-reviewed prompt or rubric proposal sample.

Fixtures should be deterministic, small enough for contract tests, and safe to
commit. Do not place real secrets in this directory.
