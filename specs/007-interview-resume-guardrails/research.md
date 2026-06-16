# Research: Interview Resume Guardrails

## Decision 1: Preserve Existing Resume Contract

**Decision**: Use the existing `interviewSessionRepo.getById()` and `interviewSessionRepo.resume()` calls as the only restore inputs.

**Rationale**: The feature is a continuity guardrail, not a backend redesign. The current live page already consumes the resume payload; improving its projection and testability is the smallest useful change.

**Alternatives considered**:
- Add a new summarized resume endpoint: rejected because it expands backend scope and contract testing.
- Store resume state in client storage: rejected because backend graph state is the source of truth.

## Decision 2: Derive Sequence Number from Restored User Messages

**Decision**: Initialize the next answer sequence from reconstructed user message count.

**Rationale**: The current answer submission protocol already accepts `sequence_no`; using restored user messages aligns the next submission with visible restored answers.

**Alternatives considered**:
- Trust a separate `current_question` field when present: rejected as less consistently available across payload shapes.
- Reset sequence number on resume: rejected because it risks duplicate answer sequence numbers.

## Decision 3: Add Stable Test Selectors

**Decision**: Add `data-testid` attributes to the interview session card, live restore summary, input, submit, retry, and return actions.

**Rationale**: Existing E2E selectors depend partly on localized text and one missing session-card selector. Stable selectors reduce false failures without affecting UX.

**Alternatives considered**:
- Use visible Chinese text only: rejected because the repository contains mojibake in several files and text selectors are brittle.
- Use CSS class selectors: rejected because classes are presentational.

## Decision 4: Browser E2E with Network Routing

**Decision**: Test the resume UI using Playwright/browser routing to provide deterministic session and resume payloads.

**Rationale**: The feature validates UI behavior around success and failure states. Deterministic network routing avoids depending on LLM/WebSocket timing for this focused slice.

**Alternatives considered**:
- Run full backend graph for every resume test: useful for broader acceptance, but too slow and fragile for this guardrail.
- Unit-test only: rejected because the requirement explicitly includes real browser E2E.

## Decision 5: Dedicated Resume Error State

**Decision**: Keep a dedicated `resume_error` phase when `getById` or `resume` fails.

**Rationale**: Falling back to setup creates duplicate-session risk and misleads the user. A retryable error preserves context and lets the user return to the list.

**Alternatives considered**:
- Redirect automatically to the list: rejected because it hides the failing session URL and makes retry harder.
- Show a toast over setup: rejected because setup still implies starting over.
