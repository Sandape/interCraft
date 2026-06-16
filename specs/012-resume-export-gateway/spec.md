# Feature Specification: Resume Export Gateway

**Feature Branch**: `[012-resume-export-gateway]`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Connect the already visible resume editor export entry to a working main backend API gateway. The editor already exposes an export button and menu, and a rendering module exists, but the main API does not serve the frontend path. Implement a narrow, testable export gateway for PDF/PNG/JPEG with clear error feedback."

## Clarifications

### Session 2026-06-16

- Q: Should the export action proxy a separate renderer service or expose a main backend route for the already used frontend path? -> A: Main backend route. This is the smallest reliable default because the frontend already calls `/api/v1/export/render`, the renderer code already exists locally, and curl/E2E validation can exercise one API surface.
- Q: Should this slice include Markdown import/export and all Feature 002 work? -> A: No. Scope is binary PDF/PNG/JPEG export gateway and feedback only; Markdown export remains client-side existing behavior.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Download Rendered Resume (Priority: P1)

An authenticated resume editor user opens the existing export menu, chooses PDF, PNG, or JPEG, and receives a downloaded file rendered from the current resume markdown and selected style.

**Why this priority**: The UI already advertises server-rendered export formats, but the main backend path is missing. This blocks a visible action from completing.

**Independent Test**: Can be tested by opening a seeded resume, selecting PDF export, and verifying the browser receives a binary download with the expected content type and filename.

**Acceptance Scenarios**:

1. **Given** a resume with at least one block, **When** the user chooses PDF export, **Then** the export action downloads a `.pdf` file without leaving the editor.
2. **Given** a resume with at least one block and a selected visual style, **When** the user chooses PNG or JPEG export, **Then** the downloaded file uses the matching image content type and extension.

---

### User Story 2 - See Export Failure Feedback (Priority: P2)

When rendering fails or input is invalid, the user sees a clear inline error in the export menu and can retry or choose Markdown without losing editor state.

**Why this priority**: Rendering depends on a headless browser and can fail locally or in deployment. The user needs recoverable feedback instead of a silent broken button.

**Independent Test**: Can be tested by forcing the render endpoint to return a server error and verifying the export menu remains open with an error message.

**Acceptance Scenarios**:

1. **Given** the render endpoint returns a server error, **When** the user chooses PDF export, **Then** the export menu remains visible and displays a user-facing failure message.
2. **Given** the resume has no exportable content, **When** the user opens the export menu, **Then** binary export options are not offered and the empty-content message is shown.

### Edge Cases

- Empty or whitespace-only markdown is rejected before rendering.
- Unsupported style identifiers are rejected with a validation error.
- Unsupported export formats are rejected with a validation error.
- Content larger than the accepted limit is rejected without invoking the renderer.
- Renderer crashes or missing browser dependencies return a structured server error instead of an unhandled exception.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose a main API export route at the same path used by the editor export client.
- **FR-002**: System MUST accept markdown, style identifier, export format, and optional locale for PDF, PNG, and JPEG export.
- **FR-003**: System MUST return binary content with the correct content type and a downloadable filename on successful export.
- **FR-004**: System MUST reject empty content, unsupported styles, unsupported formats, and oversized content with structured error details.
- **FR-005**: System MUST preserve editor state and keep the export menu open when a binary export fails.
- **FR-006**: System MUST keep existing client-side Markdown export working independently from binary export failures.

### Key Entities

- **ExportRequest**: User-provided render request containing markdown, style identifier, target format, and locale.
- **ExportResult**: Rendered binary file plus response metadata such as content type, filename, and request identifier.
- **ExportError**: Structured failure with code, message, and request identifier.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A seeded resume can be exported to PDF through the visible editor menu in under 10 seconds in the local development environment.
- **SC-002**: Invalid export requests return a structured error response in 100% of tested validation cases.
- **SC-003**: The export menu displays a recoverable failure message within one interaction after a forced server failure.
- **SC-004**: Existing Markdown export remains functional when the binary renderer is unavailable.

## Assumptions

- The existing resume editor, export menu, markdown serializer, and renderer module are retained.
- Binary export does not mutate user data and does not create persistent records in this slice.
- The renderer may run in-process for local development and testing; deployment can later split it behind a service boundary without changing the frontend contract.
- Existing app proxying sends `/api/v1/*` frontend calls to the FastAPI backend.
