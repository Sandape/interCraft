# Contract: Resume Branches — Path Reconciliation (FIX-006)

This contract supersedes §3.1.1 of
`specs/019-cross-module-linking/quickstart.md` and any reference to
`/resumes/branches` in the 019 contract files.

## 1. Affected Defect

| Defect | Issue | Fix |
|---|---|---|
| D-005 (P1) | Contracts document `POST /resumes/branches` but the backend implements `POST /resume-branches` (no trailing `/resumes/` segment; hyphen, not slash). | Contracts are updated to match the implementation. The implementation stays. |

## 2. Decision

**Implementation wins.** The backend path is `/resume-branches` and that is
what the frontend already calls. The 019 contracts are corrected to drop the
`/resumes/` prefix.

The alternative (move the backend to `/resumes/branches`) was rejected because:

1. The frontend `ResumeRepository.ts` and `ResumeList.tsx` both call
   `/api/v1/resume-branches`. Migrating them to `/api/v1/resumes/branches`
   would also require renaming the URL helper in `src/api/resumes.ts`.
2. Several existing tests (e.g., `full-resume-binding.spec.ts B2`,
   `smoke.spec.ts S3`) already use the `/resume-branches` path. Flipping
   the implementation would invalidate them.
3. There is no semantic loss: `/resume-branches` is a single nested resource
   that does not need to be under a `/resumes` collection.

If a future resource emerges that requires `/resumes/...` (e.g., a resume
template library), the prefix can be re-introduced with a router-level alias
or a sub-router.

## 3. Canonical Paths (After FIX-006)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/resume-branches` | List user's resume branches |
| `POST` | `/api/v1/resume-branches` | Create a new resume branch |
| `GET` | `/api/v1/resume-branches/{id}` | Get one branch |
| `PATCH` | `/api/v1/resume-branches/{id}` | Update a branch |
| `DELETE` | `/api/v1/resume-branches/{id}` | Delete a branch |
| `POST` | `/api/v1/resume-branches/{id}/fork` | Fork a branch (existing) |

The `/resumes/branches` form is removed from the docs and will return `404`
from the backend (it never worked).

## 4. Doc Updates Required

The following 019 contract files reference `/resumes/branches` and must be
updated to `/resume-branches`:

| File | Section | Edit |
|---|---|---|
| `specs/019-cross-module-linking/quickstart.md` | §3.1.1 | Replace `/resumes/branches` → `/resume-branches` (2 occurrences). |
| `specs/019-cross-module-linking/contracts/jobs-fields.md` | §2.4 | Replace `/resumes/branches` → `/resume-branches` (1 occurrence, in the CTA section). |
| `specs/019-cross-module-linking/spec.md` | §5.7 (FR-005, FR-007) | Replace `/resumes/branches` → `/resume-branches` (text only; no code). |
| `specs/019-cross-module-linking/plan.md` | §3.1 | Replace `/resumes/branches` → `/resume-branches` (1 occurrence). |
| `specs/019-cross-module-linking/contracts/error-questions-source.md` | §5 (D-005 reference) | Update anchor text from `/resumes/branches` → `/resume-branches`. |

## 5. Test Cases (Round-2)

| ID | File | Description | Anchor |
|---|---|---|---|
| CONTRACT-06 | `tests/e2e/round-2/contract-parity.spec.ts` | `POST /resume-branches` with valid body → 201; the response payload is identical to what `POST /resumes/branches` (which 404s) would have returned. | FIX-006 |
| B1 (Round-1) | `tests/e2e/round-1/full-resume-binding.spec.ts` | UI flow: Job detail CTA → resume editor with prefill. Rerun for regression. | FIX-002 + FIX-006 |
| B2 (Round-1) | `tests/e2e/round-1/full-resume-binding.spec.ts` | Save branch → `jobs.branch_id` backfill. Rerun for regression. | FIX-002 |
| S3 (Round-1) | `tests/e2e/round-1/smoke.spec.ts` | End-to-end: create branch from job. Rerun for regression. | FIX-002 + FIX-006 |

## 6. Open Question (Resolved)

> Should the path be `/resumes/branches` (REST style) or `/resume-branches`
> (current)?

Resolved: `/resume-branches`. Documented in §2 of this contract. The
implementation does not change.
