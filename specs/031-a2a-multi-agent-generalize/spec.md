# Feature Specification: A2A Multi-Agent Generalization

**Feature Branch**: `[031-a2a-multi-agent-generalize]`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "把 025 的 A2A Planner+Supervisor 模式泛化到 error_coach（类似题推荐 agent）和 resume_optimize（JD 分析 + 重写双 agent）。"

## User Scenarios & Testing

### User Story 1 - Reusable A2A Orchestration Framework (Priority: P1)

As a developer, I want the Supervisor + subgraph orchestration pattern from feature 025 (interview planner + interviewer) extracted into a reusable library, so that new multi-agent flows can be added by declaring agents and routing rules — without rewriting orchestration core or copy-pasting the 025 boilerplate.

**Why this priority**: This is the foundation — without a reusable framework, US2 and US3 would each copy-paste the 025 pattern, creating maintenance drift. P1 because every other story depends on the framework existing.

**Independent Test**: Can be fully tested by refactoring the 025 interview graph to use the new framework and confirming all existing E2E tests (interview-a2a-planner.spec.ts) still pass without regression.

**Acceptance Scenarios**:

1. **Given** the framework library exists, **When** a developer declares a new agent (name, role, input/output schema, routing rule), **Then** the Supervisor picks it up without core changes.
2. **Given** the 025 interview graph is refactored to use the framework, **When** the existing interview E2E suite runs, **Then** all tests pass with no behavioral regression.
3. **Given** a new agent is added to a graph, **When** the codebase is reviewed, **Then** the diff is ≤50 lines (declaration only, no Supervisor changes).
4. **Given** the framework supports both synchronous and asynchronous delegation, **When** an agent delegates a subtask, **Then** the delegation completes with a result, a timeout, or a fallback.

---

### User Story 2 - Error Coach Splits Into Hint-Ladder + Recommendation Agents (Priority: P2)

As a user stuck on an error-book question, the error-coach flow should involve two specialized agents — a hint-ladder agent that provides progressive hints and a similar-question-recommendation agent that proposes related questions — so that when I'm stuck, I get both help on the current question and a path to practice the underlying skill.

**Why this priority**: This is the first application of the framework beyond 025, validating that the pattern generalizes. P2 because it requires US1 (the framework) to be in place.

**Independent Test**: Can be fully tested by triggering an error-coach session, getting stuck on a question, and confirming the recommendation agent proposes ≥1 similar question alongside the hint-ladder output.

**Acceptance Scenarios**:

1. **Given** a user is stuck on error-book question Q1 (3 failed attempts), **When** the error-coach runs, **Then** the recommendation agent proposes ≥1 similar question.
2. **Given** the recommendation agent runs, **When** it returns, **Then** the hint-ladder agent's output is unchanged (no regression in hint quality).
3. **Given** the recommendation agent times out, **When** the Supervisor handles it, **Then** the user still receives the hint-ladder output (graceful degradation).
4. **Given** the recommendation agent proposes a question the user has already solved, **When** the user views it, **Then** it is filtered out (no duplicate practice).

---

### User Story 3 - Resume Optimize Splits Into JD-Analysis + Rewrite Agents (Priority: P2)

As a user optimizing my resume for a specific job, the resume_optimize flow should involve two specialized agents — a JD-analysis agent that extracts requirements and themes from the job description, and a rewrite agent that produces block suggestions based on the analysis — so that rewrite suggestions are grounded in what the JD actually asks for.

**Why this priority**: This is the second application, further validating the framework. P2 because it requires US1 and shows the pattern works for a different graph shape.

**Independent Test**: Can be fully tested by triggering a resume_optimize session with a JD, and confirming the JD-analysis output (extracted requirements/themes) is visible in the trace and the rewrite suggestions reference the analysis.

**Acceptance Scenarios**:

1. **Given** a user submits a JD for resume optimization, **When** the JD-analysis agent runs, **Then** it extracts requirements, themes, and keywords into a structured output.
2. **Given** the JD-analysis output is available, **When** the rewrite agent runs, **Then** its block suggestions reference the extracted requirements (visible in trace).
3. **Given** the JD is empty or unparseable, **When** the JD-analysis agent runs, **Then** it returns a structured "missing fields" result and the rewrite agent falls back to general suggestions.
4. **Given** the rewrite agent times out, **When** the Supervisor handles it, **Then** the user sees the JD-analysis output with a "rewrite unavailable" notice.

---

### User Story 4 - Standardized A2A Message Protocol (Priority: P3)

As a developer, agent-to-agent communication should use a standardized message format — task, context, expected output, status — so that agents from different graphs can interoperate and the messages are persistable for debugging.

**Why this priority**: Protocol standardization is the long-term enabler — it makes agents composable across graphs. P3 because the framework works without it (ad-hoc messages), but standardization compounds value over time.

**Independent Test**: Can be fully tested by inspecting the persisted A2A messages for one interview session and confirming each carries task, context, expected output, and status fields.

**Acceptance Scenarios**:

1. **Given** agent A delegates a subtask to agent B, **When** the message is persisted, **Then** it carries from, to, task, context, expected output, and status.
2. **Given** agent B completes the subtask, **When** the result returns, **Then** the message status transitions to "success" with the result payload.
3. **Given** agent B fails, **When** the error propagates, **Then** the message status is "failed" with the error reason.
4. **Given** a maintainer queries A2A messages for a trace (feature 029), **When** they filter by trace id, **Then** all inter-agent messages for that invocation are returned in order.

---

### Edge Cases

- What happens when a delegated agent times out? → Supervisor falls back to default behavior, logs a warning, user sees a degraded response (not an error).
- What happens when a delegated agent fails? → Supervisor retries once; if still failing, falls back; if no fallback, surfaces a user-facing error.
- What happens with circular delegation (A → B → A)? → Cycle detection blocks it; an error is logged; the delegation is rejected.
- What happens when an agent produces malformed output? → Schema validation catches it; Supervisor retries or falls back.
- What happens when two agents produce conflicting results? → Supervisor resolves by configured priority or surfaces both to the user with labels.
- What happens when delegation depth exceeds the limit? → Hard cap (e.g., 3 levels) is enforced; an error is raised and the Supervisor falls back.
- What happens when the framework is used for a graph that doesn't need multi-agent? → Single-agent mode is supported; the Supervisor routes to one agent and ends.

## Requirements

### Functional Requirements

**Framework**

- **FR-001**: System MUST extract the Supervisor + subgraph orchestration pattern from the 025 interview graph into a reusable library.
- **FR-002**: The library MUST support adding new agents (name, role, input/output schema, routing rule) without modifying the Supervisor core.
- **FR-003**: The Supervisor MUST route between agents based on a configurable routing function.
- **FR-004**: The Supervisor MUST support Command-based state handoff per the LangGraph Command API.
- **FR-005**: The framework MUST support both synchronous (blocking) and asynchronous (fire-and-forget) delegation.
- **FR-006**: The framework MUST enforce a configurable timeout on delegated subtasks.
- **FR-007**: The framework MUST enforce a delegation depth cap (e.g., 3 levels) with cycle detection.

**Error handling**

- **FR-008**: Agent failure MUST be handled by the Supervisor (retry, fallback, or user-facing error).
- **FR-009**: Agent output MUST be schema-validated; malformed output triggers retry or fallback.
- **FR-010**: Conflicting agent results MUST be resolved by configured priority or surfaced to the user.

**Applications**

- **FR-011**: The error_coach graph MUST be refactored to use the framework, with a hint-ladder agent and a similar-question-recommendation agent.
- **FR-012**: The similar-question-recommendation agent MUST propose ≥1 similar question when the user is stuck, filtered against already-solved questions.
- **FR-013**: The resume_optimize graph MUST be refactored to use the framework, with a JD-analysis agent and a rewrite agent.
- **FR-014**: The JD-analysis agent MUST extract requirements, themes, and keywords from the JD into a structured output.
- **FR-015**: The rewrite agent MUST produce block suggestions referencing the JD-analysis output.

**Protocol and observability**

- **FR-016**: Agent-to-agent communication MUST use a standardized message format (from, to, task, context, expected output, status).
- **FR-017**: A2A messages MUST be persisted for debugging, linked to the trace (feature 029).
- **FR-018**: Multi-agent handoffs MUST be visible as nested spans in the trace (feature 029).

**Testing**

- **FR-019**: Each multi-agent graph MUST be individually testable via the deterministic mock LLM client.
- **FR-020**: The eval suite (feature 026) MUST include cases for multi-agent handoff (delegation, result return, error propagation, timeout fallback).

### Key Entities

- **AgentDefinition**: name, role, input schema, output schema, routing rules, timeout, fallback behavior.
- **A2AMessage**: from agent, to agent, task, context, expected output, status (pending/success/failed/timeout), timestamp, trace id.
- **SupervisorConfig**: agents, routing function, default timeout, fallback behavior, max delegation depth.
- **DelegationRecord**: parent agent, child agent, task, result, duration, status, retry count.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The reusable A2A framework is extracted from 025; the interview graph's existing E2E tests pass with no regression.
- **SC-002**: error_coach with hint-ladder + recommendation agents delivers ≥1 similar-question recommendation when the user is stuck.
- **SC-003**: resume_optimize with JD-analysis + rewrite agents produces block suggestions that reference the JD analysis (visible in trace).
- **SC-004**: Adding a new agent to a graph requires ≤50 lines of new code (declaration only, no Supervisor core changes).
- **SC-005**: Agent-to-agent delegation timeout fires within the configured window with a user-facing fallback (no infinite waits).
- **SC-006**: Multi-agent handoffs are visible as nested spans in the trace (feature 029).
- **SC-007**: The 3 multi-agent graphs (interview, error_coach, resume_optimize) each have eval cases (feature 026) covering delegation, result return, error propagation, and timeout fallback.

## Assumptions

- LangGraph Command API is the routing mechanism; no new orchestration framework is introduced.
- The 025 interview graph is the reference implementation; refactoring it to use the new framework is in scope (validates reusability).
- Constitution Principle I (Library-First): the A2A framework is a self-contained library, callable independently.
- Constitution Principle III (Test-First): each agent is testable in isolation via the mock LLM client.
- Constitution Principle IV (Integration Testing): multi-agent handoff is tested end-to-end, not only in unit tests.
- The specific agent splits (error_coach recommendation, resume_optimize JD split) are the user-named examples; other splits may emerge during planning.
- "A2A" here refers to the internal inter-agent message protocol, not the Google A2A network protocol (which targets cross-vendor agent interop and is out of scope).
- The existing single-agent graphs (ability_diagnose, general_coach) are not forced into multi-agent; they can adopt the framework if beneficial, but it's not required.
- Frontend changes are minimal — multi-agent outputs are surfaced through existing UI surfaces (interview plan, error-coach panel, resume-optimize suggestions).
- The framework coexists with feature 028 (long-term memory) — agents can retrieve memories via the shared memory layer.
