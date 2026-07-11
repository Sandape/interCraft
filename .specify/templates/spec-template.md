# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`

**Created**: [DATE]

**Status**: Draft

**Input**: User description: "$ARGUMENTS"

## Scope, Applicability & Risk *(mandatory)*

### In Scope

- [User-visible and system behavior included in this feature]

### Non-Goals

- [Explicitly excluded behavior; do not leave this section empty]

### Governance Profile

**Highest Risk Class**: [R0/R1/R2/R3 with rationale]

| Governed operation / effect | Risk class | Actor / target / trust boundary | Required authorization and evidence |
|---|---|---|---|
| [operation] | [R0/R1/R2/R3; highest applicable condition wins] | [boundary] | [direct / standing authorization / per-execution / step-up or dual approval] |

| Dimension | Applicability, boundary, owner, or explicit N/A rationale |
|---|---|
| API / contract surface | [decision] |
| Data and privacy | [stores/data classes/tenant boundary] |
| Background / scheduled execution | [decision] |
| External side effects | [decision] |
| AI / Agent behavior | [decision] |
| Schema / checkpoint migration | [decision] |
| Operational release unit | [inherited and capability-specific controls] |

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently - e.g., "Can be fully tested by [specific action] and delivers [specific value]"]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right edge cases.
-->

- What happens when [boundary condition]?
- How does system handle [error scenario]?
- How are timeout, cancellation, retry, duplicate delivery, partial success, and unknown side effects represented?
- What happens when authentication expires or authorization/resource ownership changes during execution?
- For AI/Agent behavior, how are malformed model/tool outputs, prompt injection, and human rejection handled?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: System MUST [specific capability, e.g., "allow users to create accounts"]
- **FR-002**: System MUST [specific capability, e.g., "validate email addresses"]
- **FR-003**: Users MUST be able to [key interaction, e.g., "reset their password"]
- **FR-004**: System MUST [data requirement, e.g., "persist user preferences"]
- **FR-005**: System MUST [behavior, e.g., "log all security events"]

*Example of marking unclear requirements:*

- **FR-006**: System MUST authenticate users via [NEEDS CLARIFICATION: auth method not specified - email/password, SSO, OAuth?]
- **FR-007**: System MUST retain user data for [NEEDS CLARIFICATION: retention period not specified]

### Governed Boundaries & Failure Semantics *(mandatory)*

- **Contract**: Define typed request/response/event/error semantics, or explain why no interface exists.
- **Authorization**: Identify actor, tenant/resource scope, execution-time revalidation, and forbidden outcomes.
- **Execution**: Define synchronous/background execution, durable acceptance, timeout, cancellation, retry,
  duplicate delivery, concurrency ownership and unknown-result semantics.
- **External Effects**: Identify reversible/irreversible effects, durable fenced effect intent,
  provider idempotency/reconciliation, immutable authorization receipt, execution-time CAS, and result adoption.
- **Data Lifecycle**: Inventory every applicable store/provider and derived copy; per store define allowed
  fields, isolation, encryption, access, retention, deletion/tombstoning, provenance propagation,
  backup/export/provider cleanup evidence, and owner.
- **Compatibility**: Define API/schema/job/checkpoint live-version and retention matrix, decoder/upcasters,
  migration exclusion/ledger, separate expand/contract releases, and backout/roll-forward.

### AI & Agent Safety Requirements *(mandatory when AI or Agent behavior is in scope)*

- **State**: Define thread/execution identity, typed state/reducers, checkpointer vs. long-term store,
  authoritative-write/effect fencing, resume behavior, supported live versions, and N-1 rolling compatibility.
- **Tools**: List read/write tools, schemas, least privilege, risk class, authorization/confirmation,
  version binding, and unknown-result reconciliation.
- **Trust Boundary**: Define how prompts distinguish system authority from user/retrieved/tool content.
- **Quality**: Define deterministic tests, risk-sized offline evaluation, online signals, rollout and rollback.

### Key Entities *(include if feature involves data)*

- **[Entity 1]**: [What it represents, key attributes without implementation]
- **[Entity 2]**: [What it represents, relationships to other entities]

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: [Measurable metric, e.g., "Users can complete account creation in under 2 minutes"]
- **SC-002**: [Measurable metric, e.g., "System handles 1000 concurrent users without degradation"]
- **SC-003**: [User satisfaction metric, e.g., "90% of users successfully complete primary task on first attempt"]
- **SC-004**: [Business metric, e.g., "Reduce support tickets related to [X] by 50%"]
- **SC-005**: [Reliability/quality metric with percentile or error-rate target and measurement window]
- **SC-006**: [For AI/Agent: evaluation threshold, unsafe action rate, recovery success, or N/A]

## Assumptions

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right assumptions based on reasonable defaults
  chosen when the feature description did not specify certain details.
-->

- [Assumption about target users, e.g., "Users have stable internet connectivity"]
- [Assumption about scope boundaries, e.g., "Mobile support is out of scope for v1"]
- [Assumption about data/environment, e.g., "Existing authentication system will be reused"]
- [Dependency on existing system/service, e.g., "Requires access to the existing user profile API"]
