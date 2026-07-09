# Contract: Legacy Content Migration and Recovery

## Purpose

Guarantee older resumes remain accessible after the legacy structured editor is retired.

## Input Shapes

The migration path must handle representative older resumes with:

- Basics/profile fields.
- Summary.
- Experience.
- Education.
- Projects.
- Skills.
- Custom sections.
- Partially filled sections.
- Empty or missing optional fields.

## Conversion Contract

When an older resume has no Markdown source:

1. Detect that Markdown source is missing.
2. Extract every non-empty user-visible text field in stable resume order.
3. Convert recognized sections into Markdown headings and list/table-friendly content.
4. Preserve unknown/custom sections under Markdown headings.
5. Persist or stage the converted Markdown as the authoritative editor source.
6. Store or show conversion warnings for fields that cannot be represented perfectly.

Conversion must be idempotent. A resume already converted to Markdown must not be converted again or duplicated on reopen.

## Warning Contract

If conversion is lossy or uncertain:

- Show clear user-visible feedback inside the Markdown editor route.
- Keep the original structured content recoverable.
- Include enough debug context for tests and support to identify the affected fields.

## Rejected Behavior

The implementation must not:

- Redirect users to the old editor for editing.
- Show an unrecoverable `LEGACY_FORMAT` dead end for non-empty resumes.
- Drop custom or unknown sections silently.
- Delete original structured content during first conversion.

## Test Contract

Automated coverage must include:

- Unit tests for structured-to-Markdown conversion fixtures.
- Idempotency tests for already converted resumes.
- Route/component tests for older resume open behavior.
- E2E test that opens a structured-only resume and verifies visible content in the Markdown editor.

## Acceptance Gates

- 100 percent of representative older resumes in the migration fixture set open without losing non-empty visible text.
- Conversion warnings are visible when fields cannot be represented perfectly.
- Reopening a converted resume does not duplicate content.

