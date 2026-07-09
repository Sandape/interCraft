# Feature Specification: Long-Term Memory Layer for Agents

**Feature Branch**: `[028-long-term-memory]`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "跨 session 三层记忆（semantic/episodic/procedural），LangMem/Mem0 风格，每个 graph 加 retrieve(user_id, query) 增强 prompt。pgvector 复用。"

## User Scenarios & Testing

### User Story 1 - Agent Recalls User Facts Across Sessions (Priority: P1)

As a returning user, when I start my 4th interview session, the interview agent remembers my target position, my identified weaknesses from prior interviews, and my stated preferences — so I don't have to re-explain my context every time and the agent can ask sharper, more personalized questions.

**Why this priority**: This is the core value of long-term memory. Today, `AsyncPostgresSaver` only persists thread-level state; everything cross-session is lost. The ability profile is hand-curated dimensions, not learned from interactions. P1 because cross-session recall is the single highest-leverage capability — every graph benefits, and without it the other memory types have nothing to anchor to.

**Independent Test**: Can be fully tested by running 3 interview sessions for one user, then starting a 4th and confirming the planner node retrieves ≥3 relevant memories (target position, prior weakness, stated preference) and injects them into the LLM context.

**Acceptance Scenarios**:

1. **Given** a user has completed 3 interviews mentioning "backend engineer" as target position, **When** they start a 4th interview, **Then** the planner node retrieves the target-position fact and injects it without the user re-stating it.
2. **Given** a user's prior interviews flagged "system design" as a weakness, **When** the question_gen node runs, **Then** the retrieved weakness memory shapes the question difficulty and topic.
3. **Given** the user changes their target position in session 4, **When** memory extraction runs post-session, **Then** the new fact supersedes the old (old marked superseded, not deleted).
4. **Given** the memory store is empty for a new user, **When** their first interview runs, **Then** the agent proceeds with no injected memories and no error.

---

### User Story 2 - Agent Retrieves Relevant Past Interactions (Priority: P2)

As a user struggling with a specific error-book question, when the error-coach agent runs, it retrieves my past attempts at similar questions — including what hints worked and what didn't — so the coach doesn't repeat hints I already saw and builds on prior progress.

**Why this priority**: Episodic memory makes the agent feel continuous rather than stateless. P2 because it requires US1 (semantic facts anchor the retrieval) and is enrichment rather than foundation — the agent works without it but feels repetitive.

**Independent Test**: Can be fully tested by attempting the same error-book question twice (with different answers), then a third time, and confirming the error-coach retrieves the prior two episodes and avoids repeating the same hint ladder step.

**Acceptance Scenarios**:

1. **Given** a user attempted error-book question Q1 yesterday and received hint steps H1-H3, **When** they revisit Q1 today, **Then** the error-coach retrieves the prior episode and skips already-shown hints.
2. **Given** a user attempts a new question Q2 similar to Q1, **When** the error-coach runs, **Then** the retrieval surfaces the Q1 episode as relevant context.
3. **Given** an episode is older than the retention window, **When** the agent retrieves, **Then** the episode is excluded (not silently injected stale).
4. **Given** an episode's outcome was "user abandoned", **When** retrieved, **Then** it is marked low-confidence and the agent can choose to re-approach rather than skip.

---

### User Story 3 - Agent Learns User-Specific Interaction Patterns (Priority: P3)

As a user who consistently prefers concise hints over verbose explanations, the agent learns this procedural preference over multiple interactions and applies it to future hint generation and resume rewrites.

**Why this priority**: Procedural memory is the optimization layer — it makes the agent feel personalized at the interaction-style level. P3 because it requires US1 and US2 to be in place (patterns are extracted from episodes anchored by facts) and is not blocking.

**Independent Test**: Can be fully tested by running 5 error-coach sessions where the user consistently rejects verbose hints, then a 6th session, and confirming the agent defaults to concise hints.

**Acceptance Scenarios**:

1. **Given** a user has rejected verbose hints 3 times across sessions, **When** the error-coach generates a hint, **Then** the procedural memory "prefers concise hints" is retrieved and applied.
2. **Given** a user consistently accepts resume rewrites that preserve technical detail, **When** resume_optimize runs, **Then** the procedural memory shapes the rewrite suggestions.
3. **Given** a procedural pattern has only 1 supporting sample, **When** it is retrieved, **Then** it is marked low-confidence and the agent does not over-apply it.
4. **Given** a user's pattern changes (e.g., now prefers verbose), **When** the new pattern is extracted, **Then** the old pattern is superseded.

---

### User Story 4 - User Can View And Control Their Memories (Priority: P2)

As a user, I can list, search, and delete the memories the system has stored about me, so that I retain control over my data — especially any memories that feel inaccurate or that I want purged for privacy.

**Why this priority**: Privacy/control is a Constitution Principle (Security & Privacy) and a user trust requirement. P2 (not P1) because the system works without it, but shipping without user control would be a compliance and trust gap.

**Independent Test**: Can be fully tested by listing a user's memories via API, deleting one, and confirming the next agent invocation no longer retrieves it.

**Acceptance Scenarios**:

1. **Given** a user has stored memories, **When** they call the list API, **Then** all memories for that user are returned with type, content, source, confidence, and timestamps.
2. **Given** a user identifies an inaccurate memory, **When** they call the delete API with the memory id, **Then** the memory is purged and the next agent invocation does not retrieve it.
3. **Given** a user wants to purge all memories, **When** they call the "forget me" API, **Then** all semantic, episodic, and procedural memories for that user are purged within 30 seconds.
4. **Given** a memory contains content the user considers sensitive, **When** they review it, **Then** they can see the source (which interaction produced it) for context.

---

### Edge Cases

- What happens when memory extraction runs while the user requests deletion? → Deletion is queued and applied after the current invocation completes; the extracted memory is then purged.
- What happens when the vector store is unavailable during retrieval? → Agent degrades gracefully to no-memory mode; logs a warning; no user-facing error.
- What happens when an extracted memory contains PII beyond the fact? → Redaction layer blocks storage; the fact is stored without the PII; a warning is logged.
- What happens when two memories conflict (e.g., user stated two different target positions)? → Latest-wins; the old memory is marked superseded with a timestamp.
- What happens when the memory token budget is exceeded? → Lowest-relevance memories are dropped first; the budget cap is enforced.
- What happens when a graph runs for a brand-new user with no memories? → Agent proceeds with no injected memories; no error, no empty-memory log spam.
- What happens when a cross-user memory leak is attempted (bug)? → Row-level security blocks it; the breach is logged.

## Requirements

### Functional Requirements

**Memory storage**

- **FR-001**: System MUST store semantic memories (user facts) extracted from agent interactions, keyed by user id, with a fact key, fact value, confidence, source, and version.
- **FR-002**: System MUST store episodic memories (past interactions) with timestamp, graph, node, outcome, summary, and embedding.
- **FR-003**: System MUST store procedural memories (interaction patterns) with pattern type, pattern value, confidence, and supporting sample count.
- **FR-004**: Memory schema MUST be versioned so extraction logic can evolve without invalidating stored data.

**Memory extraction**

- **FR-005**: System MUST extract new memories from completed agent interactions via a post-node hook.
- **FR-006**: Memory extraction MUST run asynchronously and MUST NOT block the agent response.
- **FR-007**: Memory extraction MUST deduplicate and resolve conflicting memories (latest-wins with superseded marker on the old).
- **FR-008**: Each memory MUST carry a source field (extracted-from-LLM-output, user-asserted, system-inferred) and a confidence score.
- **FR-009**: Memory extraction MUST redact PII before storage; facts containing PII beyond the necessary are blocked.

**Memory retrieval**

- **FR-010**: Each of the 5 graphs MUST be able to retrieve relevant memories (by user id + query) before invoking the LLM, and inject them into the prompt context.
- **FR-011**: Memory retrieval MUST be relevance-ranked (semantic similarity) and capped at a configurable token budget per call.
- **FR-012**: Memory retrieval MUST be observable — which memories were injected into which call is logged.
- **FR-013**: Memory retrieval failure (e.g., vector store down) MUST degrade gracefully — the agent proceeds without memory and no user-facing error is raised.

**User control**

- **FR-014**: System MUST expose a user-facing API to list, search, and delete stored memories.
- **FR-015**: System MUST support a "forget me" workflow that purges all memories for a user within 30 seconds.
- **FR-016**: Memories MUST be encrypted at rest (Constitution: Security & Privacy).
- **FR-017**: Per-user memory isolation MUST be enforced via row-level security.

**Testing infrastructure**

- **FR-018**: The deterministic mock LLM client MUST be able to assert on injected memories so memory-aware logic is testable without the real provider.
- **FR-019**: The eval suite (feature 026) MUST include cases verifying that memory injection improves response relevance.

### Key Entities

- **SemanticMemory**: user id, fact key, fact value, confidence, source, version, status (active/superseded), created_at, updated_at.
- **EpisodicMemory**: user id, episode id, graph, node, summary, embedding, timestamp, outcome, retention expiry.
- **ProceduralMemory**: user id, pattern type (hint_style, rewrite_preference, etc.), pattern value, confidence, supporting sample count, status.
- **MemoryRetrievalLog**: trace id, user id, graph, node, query, retrieved memory ids, token budget used, retrieval latency.
- **MemorySchemaVersion**: schema version, extraction prompt version, migration path.

## Success Criteria

### Measurable Outcomes

- **SC-001**: After a user completes 3 interviews, the 4th interview's planner node retrieves ≥3 relevant memories and injects them into context.
- **SC-002**: Memory injection stays within a 500-token budget per call in ≥95% of calls.
- **SC-003**: Memory retrieval latency p95 ≤100ms.
- **SC-004**: A user can list, search, and delete their stored memories via API; deletion takes effect on the next agent invocation.
- **SC-005**: Memory extraction adds ≤200ms p95 to agent response time (async, non-blocking).
- **SC-006**: Conflicting memories are resolved with latest-wins; the old memory is marked superseded (not deleted) in 100% of cases.
- **SC-007**: "Forget me" workflow purges all memories for a user within 30 seconds.
- **SC-008**: Cross-user memory leakage is prevented by row-level security, verified by an integration test that attempts cross-user access and is denied.

## Assumptions

- pgvector is used for embeddings (already present in the project's PostgreSQL); no new vector store is introduced.
- The embedding model is configurable; the specific model is decided in planning.
- The memory module is a new self-contained library (Constitution Principle I — Library-First).
- Frontend memory management UI is out of scope; only the backend API is exposed in this feature.
- Row-level security enforces per-user isolation, consistent with existing modules.
- Memory extraction prompt is versioned alongside the memory schema.
- LangMem and Mem0 are candidate frameworks to evaluate in planning, not committed in this spec.
- Constitution Principle V (Observability): memory retrieval is logged alongside the existing structured logs and traces.
- Constitution Principle III (Test-First): memory-aware logic is testable via the mock LLM client.
- Memory retention follows a default policy (e.g., episodic memories expire after 90 days); specific policy decided in planning.
- The pre-existing `AsyncPostgresSaver` continues to handle thread-level short-term state; this feature adds cross-session long-term memory as a separate layer.
