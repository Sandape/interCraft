# Feature Specification: LLM Structured Output Hardening

**Feature Branch**: `[038-llm-structured-output-hardening]`

**Created**: 2026-07-02

**Status**: done (US1~US4 all merged 2026-07-03 via cdb9aef; FR-001~FR-014 all 14/14 covered)
**Last-verified (2026-07-03)**: 7 feat/refactor/test commits on master (09dc2c5, 161c7c0, a7bff01, 551a862, c51fbf7, 25697a1, 6d99f23) + merge commit cdb9aef. spec frontmatter Status: Draft was stale; rewritten to Done. (test-acceptance v2.0 verifier audit, confidence 0.95)

**Input**: User description: "LLM强制结构化输出是Agent容灾设计中的重要一环，分析一下当前的系统是否针对LLM结构化输出做了严格健壮的设计，LangGraph的最佳实践应该是借助LangGraph自身的with_structured_output+pydantic校验，你可以调研一下。如果当前的实现并不是最佳实践，整理一份改造需求"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Block Invalid Agent State From LLM Output (Priority: P1)

As an AI platform owner, I need every machine-consumed LLM response to be accepted only after it satisfies a declared output contract, so malformed text, missing fields, invalid enum values, and out-of-range scores cannot silently corrupt Agent state.

**Why this priority**: Agent recovery depends first on knowing whether a model response is usable. Silent best-effort parsing makes failures look successful and hides root causes from users, evaluators, and operators.

**Independent Test**: Can be tested by replaying valid, malformed, incomplete, and semantically invalid model outputs through each structured-output Agent task and verifying that only validated objects update downstream state.

**Acceptance Scenarios**:

1. **Given** an Agent task that produces data used by downstream logic, **When** the LLM response omits a required field or returns a field with the wrong type, **Then** the invalid response is rejected, the downstream state is not updated with invalid data, and a deterministic fallback or typed failure is returned.
2. **Given** an Agent task that produces a numeric score or routing decision, **When** the LLM returns a value outside the allowed range or enum set, **Then** the validation failure is captured before business logic consumes the value.
3. **Given** an Agent task returns a valid response matching its declared contract, **When** the task completes, **Then** downstream logic receives a normalized structured object without relying on free-text extraction.

---

### User Story 2 - Add Structured Agent Tasks Safely (Priority: P2)

As a feature engineer, I need a repeatable way to declare, test, and register structured LLM outputs for new Agent tasks, so new nodes do not reintroduce prompt-only JSON parsing or inconsistent fallbacks.

**Why this priority**: The system has multiple Agent graphs and more are planned. A one-off fix would decay unless new structured tasks are easy to add and hard to bypass.

**Independent Test**: Can be tested by adding a small sample Agent task with a declared output contract and verifying that local tests, coverage reports, and registration checks fail when the contract is missing or violated.

**Acceptance Scenarios**:

1. **Given** a new Agent task that returns machine-consumed data, **When** it is registered without an output contract, **Then** a local verification check reports the task as non-compliant.
2. **Given** a new Agent task with a declared output contract, **When** the mock LLM returns valid data, **Then** the task passes validation and exposes the same normalized shape to downstream consumers.
3. **Given** a new Agent task with a declared output contract, **When** the mock LLM returns invalid data, **Then** the task emits a schema validation failure that can be asserted in tests.

---

### User Story 3 - Diagnose Structured Output Failures (Priority: P2)

As an operator or evaluator, I need structured-output failures to be visible in traces, logs, metrics, and eval reports, so production incidents and regression cases can be diagnosed without replaying raw prompts manually.

**Why this priority**: Agent failures are often intermittent and provider-dependent. Observability must identify whether a failure came from transport, model refusal, schema validation, fallback use, or downstream business rules.

**Independent Test**: Can be tested by forcing a schema validation failure in a mocked run and verifying that the failure category, output contract identity, node name, validation errors, and fallback status appear in the recorded evidence.

**Acceptance Scenarios**:

1. **Given** a structured Agent task fails validation, **When** the run is inspected, **Then** the evidence includes the node, output contract name and version, validation status, failure category, and fallback decision.
2. **Given** an eval run includes malformed-output cases, **When** the eval report is generated, **Then** malformed-output detection appears as a first-class result rather than as a generic LLM error.
3. **Given** sensitive model inputs or outputs are captured for debugging, **When** evidence is persisted, **Then** existing redaction and raw-payload access policies still apply.

---

### User Story 4 - Preserve Existing User-Facing Agent Behavior (Priority: P3)

As a product stakeholder, I need the structured-output migration to preserve existing interview, coaching, resume optimization, and diagnosis behavior, so hardening improves reliability without changing the user's expected flow.

**Why this priority**: The current product already has shipped Agent workflows and regression coverage. Hardening must not degrade completed user journeys.

**Independent Test**: Can be tested by running existing Agent unit, integration, E2E, and golden eval suites before and after migration and comparing externally visible behavior.

**Acceptance Scenarios**:

1. **Given** an existing happy-path Agent workflow, **When** the structured-output migration is enabled, **Then** the workflow completes with the same user-visible state transitions and final outputs.
2. **Given** an existing language-fidelity eval case, **When** the structured-output migration is enabled, **Then** the case still verifies Chinese output quality for user-visible text fields.

### Edge Cases

- Provider returns syntactically valid JSON that violates required fields, enum values, score ranges, or list item constraints.
- Provider returns extra prose, markdown fences, nested JSON fragments, or multiple JSON objects around the expected payload.
- Provider returns truncated, empty, refused, or tool-call-shaped output for a structured task.
- Structured output is requested for a task that should remain free-form user-facing text.
- A fallback result is produced repeatedly for the same node and should not be mistaken for successful model behavior.
- Mock and eval clients return raw strings while production expects structured objects.
- Delegated Agent outputs claim success but violate the parent graph's expected output contract.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain an inventory of all LLM-producing Agent tasks and classify each task as structured machine-consumed output or free-form user-facing text.
- **FR-002**: System MUST define a canonical output contract for every structured LLM task, including required fields, data types, numeric ranges, enum values, list item constraints, extra-field policy, and contract version.
- **FR-003**: System MUST request contract-constrained structured output for structured LLM tasks whenever the active provider path supports it.
- **FR-004**: System MUST validate every structured LLM response against the task's canonical output contract before downstream Agent state, routing, scoring, persistence, or patch application consumes it.
- **FR-005**: System MUST prevent ad hoc free-text extraction from being the authoritative parser for structured LLM tasks.
- **FR-006**: System MUST return either a validated structured object or a typed structured-output failure for each structured LLM task.
- **FR-007**: System MUST provide deterministic fallback behavior for structured-output failures where the product flow can safely continue.
- **FR-008**: System MUST distinguish schema validation failures from transport failures, provider failures, quota failures, model refusals, timeout failures, and downstream business-rule failures.
- **FR-009**: System MUST make structured-output validation status observable through logs, traces, metrics, and eval reports.
- **FR-010**: System MUST support structured-output scenarios in mock LLM clients and golden eval fixtures, including valid responses, malformed responses, contract violations, and fallback cases.
- **FR-011**: System MUST enforce delegated Agent output contracts when one Agent passes machine-consumed data to another Agent.
- **FR-012**: System MUST include a local verification check that fails when a structured LLM task lacks an output contract or bypasses contract validation.
- **FR-013**: System MUST preserve existing user-facing Agent workflows and language-fidelity expectations during the migration.
- **FR-014**: System MUST document which LLM tasks remain free-form and why they are excluded from structured-output enforcement.

### Key Entities *(include if feature involves data)*

- **Structured Output Contract**: The declared shape and validation rules for one machine-consumed LLM task, including contract name, version, required fields, constraints, and extra-field policy.
- **Structured Invocation**: One LLM call made for a structured task, including node identity, provider path, output contract, validation status, retry count, and fallback decision.
- **Validation Failure**: A typed record that explains why an LLM response failed validation, including failure category, field-level errors, response availability, and safe diagnostic references.
- **Fallback Result**: A deterministic result used when a structured task fails but the product flow can safely continue.
- **Coverage Registry**: The inventory of structured and free-form Agent tasks used by local verification and readiness reporting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of machine-consumed LLM tasks are listed in the coverage registry and mapped to either an output contract or a documented free-form exclusion.
- **SC-002**: 100% of structured LLM tasks reject malformed, missing-field, invalid-enum, and out-of-range mock responses before downstream state is updated.
- **SC-003**: Existing Agent unit, integration, E2E, and golden eval suites continue to pass after structured-output enforcement is enabled.
- **SC-004**: At least one malformed-output regression case per structured Agent domain is included in automated tests or eval fixtures.
- **SC-005**: Structured-output validation failures are visible in operator evidence within one run, including node, contract, validation status, failure category, and fallback status.
- **SC-006**: No structured Agent task relies on free-text JSON extraction as its authoritative success path after migration.

## Assumptions

- Existing free-form coaching or explanation responses remain outside forced structured-output enforcement unless their output is consumed by business logic.
- Some provider paths may not support native schema enforcement; local contract validation remains mandatory in all cases.
- Existing prompt, eval, observability, and redaction systems will be reused rather than replaced.
- Current user-facing behavior is the baseline unless a later clarification explicitly changes product semantics.
