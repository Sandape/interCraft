# Research: Resume Export Gateway

## Decision 1: Main API route for the existing frontend path

**Decision**: Add a FastAPI v1 route for `/api/v1/export/render`.

**Rationale**: The frontend already sends binary export requests to `/api/v1/export/render`. The renderer module exists, but only a standalone service exposes `/api/export/render`. A main route is the smallest change that makes the visible UI work and keeps curl/browser validation simple.

**Alternatives considered**:

- Change frontend to call standalone `/api/export/render`: rejected because Vite proxy and production API conventions already route `/api/v1/*` to the main backend.
- Add only a dev proxy rewrite: rejected because curl and production API validation would still lack the route.

## Decision 2: Stateless render request

**Decision**: The endpoint accepts markdown, style, and format directly and returns binary content without database writes.

**Rationale**: The editor already has the current markdown and selected style. Persisting export jobs would enlarge scope and duplicate account export behavior.

**Alternatives considered**:

- Create asynchronous export jobs: rejected for this slice because the existing UI expects an immediate download and the local renderer can return a binary response.

## Decision 3: Structured error envelope

**Decision**: Return `{ "error": "...", "message": "...", "request_id": "..." }` for validation and render failures.

**Rationale**: The frontend can display a useful message and tests can assert stable error codes. Request IDs support observability without exposing internals.

**Alternatives considered**:

- Plain text errors: rejected because they are harder to map to user-facing feedback and less useful for curl/API tests.

## Decision 4: Mock renderer in contract/E2E tests where appropriate

**Decision**: Backend contract tests monkeypatch the renderer to verify API behavior. Browser E2E routes success and failure responses to cover UI states quickly.

**Rationale**: Full headless-browser rendering is covered by the renderer module and can be validated manually/curl. API and UI tests should be deterministic and fast.

**Alternatives considered**:

- Always render real PDFs in automated tests: rejected because Playwright browser dependency availability can make the suite flaky and slow.
