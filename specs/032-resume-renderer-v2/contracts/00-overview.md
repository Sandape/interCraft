# Contracts — Overview

**Feature**: 032-resume-renderer-v2

The v2 feature exposes four categories of contract:

| File | Audience | Format |
|---|---|---|
| `01-rest-api.md` | Frontend, mobile, third parties | OpenAPI 3.1 |
| `02-resume-data-schema.md` | Frontend, backend, integrations | JSON Schema |
| `03-sse-events.md` | Frontend (real-time) | Server-Sent Events |
| `04-template-gallery.md` | Frontend, marketplace authors | JSON manifest |
| `05-frontend-store.md` | Frontend dev | TypeScript types |

These contracts are **normative**: any drift must trigger a `FR` amendment
and a `requirements-status.md` update.

---

## Design principles

1. **Single source of truth**: the same `ResumeDataV2` shape is enforced on the
   backend (Pydantic) and the frontend (Zod). The JSON Schema in `02-…` is
   auto-generated from a canonical Python dict at build time.
2. **HTTP semantics**: REST verbs reflect state changes; non-idempotent actions
   (analyze, duplicate) are POST. 409 carries the latest state for conflict
   resolution.
3. **SSE-only for live updates**: WebSocket is intentionally not used; LISTEN/
   NOTIFY + SSE is sufficient and matches 027.
4. **No versioning in URL**: v2 is mounted under `/api/v1/v2/resumes/*` because
   `/api/v1` is the major version; `/v2/` disambiguates the resume schema
   family. URL parameters (`?version=2`) are not used.

---

## Cross-references

| Contract | Spec FR | Research section |
|---|---|---|
| REST API endpoints | FR-001..003, FR-095..103 | §4.3, §7 |
| ResumeDataV2 JSON Schema | FR-004..010, FR-013..027 | §3 (data-model) |
| SSE event format | FR-085..086 | §4.4 |
| Template gallery manifest | FR-028..033, FR-040, FR-057..059 | §5 |
| Frontend Zustand store shape | FR-081..084, FR-101..103 | §4.6 (research) |

---

## Stability promise

`ResumeDataV2` follows semantic versioning inside the schema: **additive** fields
are non-breaking; **removing** or **renaming** fields requires a migration path
documented in `specs/032-resume-renderer-v2/data-model.md`. Template IDs that
are dropped from the enum MUST be retained as deprecated renderers for at
least 2 minor versions.