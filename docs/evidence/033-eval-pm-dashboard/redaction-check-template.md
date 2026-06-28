# Redaction Audit Report — PRODUCTION

- **audit_id**: `redaction-YYYYMMDD-HHMMSS`
- **environment**: `PRODUCTION`
- **policy_version**: `v1`
- **sample_count**: `<int>`
- **forbidden_content_failures**: `<int>`
- **timestamp**: `<ISO 8601>`
- **evidence_ref**: `docs/evidence/033-eval-pm-dashboard/redaction-check-<audit_id>.md`

## Samples

| sample_id | privacy_class | redaction_status | verdict | violations |
|---|---|---|---|---|
| `<event_id or case_id>` | `PUBLIC_METADATA` \| `INTERNAL_METADATA` \| `SENSITIVE_USER_CONTENT` \| `SECRET` \| `REDACTED_SUMMARY` | `NOT_REQUIRED` \| `PENDING` \| `PASSED` \| `FAILED` \| `NOT_EXPORTABLE` | `PASS` \| `FAIL` | comma-separated forbidden keys, or `—` |

## Overall Result

**`<PASSED | FAILED>`** — `<N>` of `<M>` samples failed the redaction audit.

_forbidden keys checked: `['access_token', 'api_key', 'free_form_text',
'interview_answer', 'job_description', 'password', 'refresh_token',
'resume_text', 'secret']`_

---

## Reviewer

| Field | Value |
|---|---|
| Reviewer | `<name>` |
| Reviewed at | `<ISO 8601>` |
| Evidence ref | `docs/evidence/033-eval-pm-dashboard/redaction-check-<audit_id>.md` |
| Dual approval (FR-024) | `<pm-business-owner + technical-owner>` (required for production enablement) |

---

## Generation

This file is the canonical evidence artifact for SC-008
(``Production export privacy audit finds zero raw resumes, interview
answers, job descriptions, free-form user text, or secrets in exported
production payload samples before production export is enabled.``).

The audit is produced by:

```bash
cd backend && uv run python -m app.modules.telemetry_contracts.redaction_cli \
    --environment production \
    --sample docs/evidence/<run_id>/export-sample.json \
    --out docs/evidence/033-eval-pm-dashboard/redaction-check-<audit_id>.md \
    --json \
    --reviewer "<name>"
```

Exit codes (per ``contracts/eval-langsmith-cli.md`` §Shared CLI Rules):

- `0` — PASSED. Production export may proceed *after* dual approval
  from the PM business owner and technical owner is recorded.
- `1` — Operational failure (file IO, JSON parse).
- `2` — Invalid arguments (missing sample, unknown env).
- `3` — Policy violation (forbidden production content detected).

Warnings (deprecation / non-fatal notes) go to stderr.

## Sample JSON shape

The `--sample` JSON must be either a single export-payload dict or a
list of such dicts. The exporter-side ``properties`` / ``metadata``
bags are scanned for the forbidden-key set listed above.

```json
{
  "event_id": "evt-001",
  "name": "eval.case_result",
  "occurred_at": "2026-06-26T12:00:00Z",
  "environment": "production",
  "release_stage": "RELEASE_CANDIDATE",
  "app_version": "0.33.0",
  "feature_area": "EVAL",
  "privacy_class": "PUBLIC_METADATA",
  "redaction_status": "PENDING",
  "properties": {
    "case_id": "case.demo.001",
    "graph": "resume_optimize",
    "node": "suggest_blocks",
    "duration_ms": 1234
  }
}
```

## What "PASSED" means

A sample PASSES the audit when:

- ``environment`` is ``local`` / ``ci`` / ``staging`` / ``production``
  (case-insensitive).
- ``properties`` and ``metadata`` contain no keys matching the
  forbidden set (case-insensitive).
- For ``production``: the audit returns ``payload=None`` and exits 3
  on *any* forbidden key. The audit MUST be re-run with a clean sample
  before production export can be enabled.

## What "FAILED" means

A sample FAILS when at least one forbidden key is present. The audit
exits 3 and the ``violations`` list enumerates the offending keys. The
operator MUST either:

1. Strip the forbidden content from the source payload and re-run the
   audit (preferred).
2. Record an override with **dual approval** (PM business owner +
   technical owner) per FR-024 and attach the override record to this
   evidence file.

## Retention

The audit report itself is retained according to the same FR-035a
30-day policy as production trace metadata; older audits are archived
by the retention CLI:

```bash
cd backend && uv run python -m app.modules.telemetry_contracts.retention_cli \
    --environment production \
    --json
```