# 012 Requirement Status

Status reconciled against code on 2026-06-22. Both user stories and 6
FR are implemented; E2E covers the export + failure-feedback flow.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Download Rendered Resume | done | `backend/app/api/v1/export.py` `POST /export/render`; `src/api/export.ts:exportResume()`; `tests/e2e/resume-export-gateway.spec.ts` | — |
| US2 | See Export Failure Feedback | done | `src/lib/apiErrorToMessage.ts` `ExportError` + `exportErrorToMessage`; `src/components/resume/ExportMenu.tsx` toast | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | main API export route at the path the editor client uses | done | `backend/app/api/v1/export.py` prefix `/export`; mounted in `api/v1/__init__.py` | — |
| FR-002 | accept markdown + style + format + locale for PDF/PNG/JPEG | done | `backend/app/api/v1/export.py:25-29` `ExportRequest` (markdown/style_id/format/locale); `VALID_FORMATS = {"pdf","png","jpeg"}` | — |
| FR-003 | return binary content with correct content-type + downloadable filename | done | `backend/app/api/v1/export.py` `CONTENT_TYPES` map + `Response` body | — |
| FR-004 | reject empty/unsupported style/format/oversized with structured error | done | `backend/app/api/v1/export.py:64-68` (EMPTY_CONTENT / INVALID_STYLE / INVALID_FORMAT / CONTENT_TOO_LARGE) | — |
| FR-005 | preserve editor state + keep menu open on binary export failure | done | `src/components/resume/ExportMenu.tsx` error toast without closing menu | — |
| FR-006 | keep client-side Markdown export independent of binary export | done | `src/components/resume/ExportMenu.tsx` separate Markdown export path | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | seeded resume → PDF via editor menu in < 10s locally | done | `tests/e2e/resume-export-gateway.spec.ts` | — |
| SC-002 | invalid requests return structured error in 100% of validation cases | done | `backend/app/api/v1/export.py:64-68`; `tests/e2e/resume-export-gateway.spec.ts` | — |
| SC-003 | export menu shows recoverable failure within one interaction after forced server failure | done | `src/lib/apiErrorToMessage.ts` + `src/components/resume/ExportMenu.tsx` toast; `tests/e2e/resume-export-gateway.spec.ts` | — |
| SC-004 | Markdown export still works when binary renderer unavailable | done | `src/components/resume/ExportMenu.tsx` separate Markdown path | — |

## Status Roll-up

- Total: 2 US + 6 FR + 4 SC = 12 rows.
- `done`: 12 rows.
