# Resume Intelligence

REQ-059 owns version-bound general/job-fit analyses, deterministic scoring,
gaps, AI suggestions, reversible change sets and feedback. Job-targeted resume
creation remains exposed by `resume_derive`, which calls this module for
snapshots, validation, analysis and suggestion lifecycle behavior.

## Boundaries

- All model calls use the centralized LLM client.
- Resume/JD/supplement text is untrusted data and is never logged.
- Authoritative scores are calculated by versioned pure functions.
- Analysis is immutable; suggestions and change sets have explicit lifecycle.
- Every tenant table uses PostgreSQL RLS and every write uses resume version CAS.

## CLI

```powershell
cd backend
uv run python -m app.modules.resume_intelligence.cli score --classification fixture.json --json
uv run python -m app.modules.resume_intelligence.cli validate-output --contract evidence_map --input fixture.json --json
uv run python -m app.modules.resume_intelligence.cli replay --fixture tests/fixtures/resume_intelligence/core-job-fit --mode mock --repeat 5 --json
```

Exit codes are documented in
`specs/059-ai-resume-intelligence/contracts/cli.md`.
