# Feature Specification: Interview Resume Guardrails

**Feature Branch**: `007-interview-resume-guardrails`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Improve the mock interview resume experience so an in-progress interview can be left and re-entered with visible continuity, and resume failures keep the user oriented instead of dropping them into a blank setup flow."

## Clarifications

### Session 2026-06-16

- Q: What should be restored after re-entering an in-progress interview? -> A: Restore visible session context, prior answers, question count, score count, elapsed time, and a stable resume notice without auto-submitting any answer.
- Q: What should happen when resume data cannot be loaded? -> A: Show a dedicated retryable error state with the session id context and a return-to-list action.
- Q: What is the validation baseline? -> A: Cover normal completion, leave-and-return resume, and resume failure with automated browser tests using the configured Chrome control path where available.

## User Scenarios & Testing

### User Story 1 - Resume an In-Progress Interview (Priority: P1)

As a candidate, I want to leave an interview and later continue it from the existing session so that I do not lose my progress or accidentally start over.

**Why this priority**: This protects the core interview workflow. A user who loses interview progress cannot trust the interview feature.

**Independent Test**: Start an interview, submit at least one answer, navigate away, re-open the session from the interview list, and verify the live page shows restored context and allows the next answer.

**Acceptance Scenarios**:

1. **Given** an authenticated user has an in-progress interview with prior answers, **When** they choose continue from the interview list, **Then** the live interview page shows a resumed notice and the previous answers/questions before accepting the next answer.
2. **Given** a resumed interview contains prior timing data, **When** the live page opens, **Then** the elapsed time starts from the stored duration instead of zero.
3. **Given** a resumed interview is still active, **When** the user submits the next answer, **Then** the answer uses the next sequence number and the page remains in the existing session.

---

### User Story 2 - Recover from Resume Load Failure (Priority: P1)

As a candidate, I want a clear recovery state when the app cannot restore an interview so that I can retry or return to the interview list without losing context.

**Why this priority**: Resume failures are expected in real networks. A blank setup form implies progress loss and risks duplicate sessions.

**Independent Test**: Force the resume endpoint to fail, open an in-progress session URL, and verify a dedicated error state appears with retry and return actions.

**Acceptance Scenarios**:

1. **Given** the resume request fails, **When** the live page opens, **Then** the user sees a resume error message rather than the new-interview setup form.
2. **Given** resume fails for a known session, **When** the error state appears, **Then** it includes a retry action and a return-to-list action.
3. **Given** the user retries after a transient failure, **When** the page reloads successfully, **Then** the standard resumed interview state appears.

---

### User Story 3 - Verify Full Interview Continuity (Priority: P2)

As a product engineer, I want automated end-to-end coverage for both uninterrupted and interrupted interview flows so that regressions in resume behavior are caught before release.

**Why this priority**: The feature is only trustworthy if normal and interrupted flows are both validated in a real browser.

**Independent Test**: Run the focused E2E suite and verify the normal 5-round flow, leave-and-return flow, and resume failure flow pass.

**Acceptance Scenarios**:

1. **Given** a healthy interview service, **When** the uninterrupted 5-round flow runs, **Then** the user reaches the report page.
2. **Given** a user leaves midway through an interview, **When** they return from the list, **Then** the test verifies the resumed state and completes the remaining rounds.
3. **Given** the resume request returns an error, **When** the session URL opens, **Then** the test verifies the error state and does not create a new interview.

### Edge Cases

- Resume payload includes messages but no questions: show restored answers and let the next backend event populate the next question.
- Resume payload includes duplicate questions or scores: the UI must avoid rendering duplicates.
- Resume payload includes completed status: send the user to completed/report state rather than live input.
- Resume payload is malformed: show the resume failure state with retry and return actions.
- Browser refresh occurs while live WebSocket is reconnecting: do not lose restored answers already rendered.

## Requirements

### Functional Requirements

- **FR-001**: System MUST show a stable resumed notice when an in-progress interview is restored from an existing session.
- **FR-002**: System MUST restore visible prior user answers from saved conversation data.
- **FR-003**: System MUST restore visible prior generated questions and score cards when present in saved state.
- **FR-004**: System MUST initialize the next answer sequence number from restored user answer count.
- **FR-005**: System MUST initialize elapsed time from stored session duration when available.
- **FR-006**: System MUST avoid rendering duplicate restored questions or duplicate restored scores.
- **FR-007**: System MUST show a dedicated resume error state if session lookup or resume data loading fails.
- **FR-008**: Resume error state MUST provide retry and return-to-list actions.
- **FR-009**: Resume error state MUST NOT show the new-interview setup form.
- **FR-010**: Interview list MUST expose stable selectors for in-progress session cards and continue actions so automated tests can verify recovery workflows.
- **FR-011**: Focused E2E coverage MUST include uninterrupted completion, interrupted resume completion, and resume failure.
- **FR-012**: The feature MUST reuse the existing interview session contracts and must not create a duplicate session during resume.

### Key Entities

- **Interview Session**: Existing session record containing status, position, company, duration, and report metadata.
- **Resume Snapshot**: Existing backend resume payload containing saved graph values such as messages, questions, and scores.
- **Restored Answer**: A user message reconstructed from saved conversation data and displayed on the live page.
- **Resume Error State**: A UI state tied to a specific session URL when restore cannot complete.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can leave and resume an in-progress interview in under 10 seconds after clicking continue.
- **SC-002**: 100% of restored interviews with prior user messages show at least one previous answer before the next submission.
- **SC-003**: 100% of resume failures show the dedicated error state instead of the new-interview setup form.
- **SC-004**: Focused E2E validation covers at least one normal completion path and two resume paths: success and failure.
- **SC-005**: No duplicate interview session is created during the resume flow.

## Assumptions

- The existing backend resume endpoint remains the source of truth for restored graph state.
- The existing live interview route is the only entry point for continuing an in-progress session.
- The initial implementation focuses on text-mode interviews.
- Browser validation can use Playwright and the configured Chrome control path available in this Codex session.
- WebSocket streaming may be mocked or intercepted in frontend E2E when the test focuses on UI continuity rather than backend graph correctness.
