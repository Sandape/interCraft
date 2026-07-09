# Feature Specification: Prompt Caching & Token Cost Engineering

**Feature Branch**: `[027-prompt-caching-cost]`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "DeepSeek V4 context caching 接入 LLMClient，prompt 分层（system/tools/snapshot 稳定前缀 + 动态尾），cache hit 单独计价，quota 预扣-调整模型对齐。"

## User Scenarios & Testing

### User Story 1 - Stable Prompt Prefix Gets Cached (Priority: P1)

As the LLM client, when a user progresses through a multi-turn agent flow (e.g., the 5-question interview), I want the stable parts of the prompt — system prompt, tool definitions, resume snapshot — to be cached by the provider so that repeated calls within the session reuse the cached prefix instead of paying full input-token cost each time.

**Why this priority**: This is where the cost saving comes from. The interview graph alone makes ~7 LLM calls per session (intake + planner + 5×question+score + report), and ~70% of each call's input is the same stable prefix. Without caching, every call pays full price. P1 because it is the only story that directly delivers the cost reduction; the others measure and account for it.

**Independent Test**: Can be fully tested by running one full interview session against the real provider and confirming that calls 2..N report a cache hit on the stable prefix, with cached input tokens charged at the provider's cached rate.

**Acceptance Scenarios**:

1. **Given** the interview graph runs its first LLM call (intake), **When** the call completes, **Then** the response records a cache write for the stable prefix (or a miss on the very first call).
2. **Given** the second LLM call (planner) uses the same system prompt and tool definitions, **When** it completes, **Then** the response records a cache hit and the cached token count is non-zero.
3. **Given** the resume snapshot is part of the prompt, **When** the snapshot is unchanged between two calls, **Then** both calls share the cache entry for the snapshot segment.
4. **Given** the resume snapshot changes between calls (user edited resume mid-session), **When** the next call runs, **Then** the snapshot segment is a cache miss but the system prompt segment still hits.

---

### User Story 2 - Cache Hit Rate Is Observable (Priority: P2)

As a maintainer, I want cache hit rate to be a first-class metric per node and per graph, with the cached vs uncached token counts visible in logs and metrics, so that I can verify caching is actually working and diagnose when it silently breaks.

**Why this priority**: Without observability, caching is invisible — a prompt reorder could silently drop cache hit rate to zero and nobody would notice until the quota bill arrives. P2 because it is the verification layer that makes US1 trustworthy and links to the eval gate (feature 026) for regression detection.

**Independent Test**: Can be fully tested by running one interview session, then querying the metrics endpoint for cache hit rate per node, and confirming the values are non-zero for calls 2..N.

**Acceptance Scenarios**:

1. **Given** an LLM call completes with a cache hit, **When** the maintainer queries the metrics endpoint, **Then** the cache hit counter increments for that node and graph.
2. **Given** an LLM call completes with a cache miss, **When** the maintainer inspects the structured log, **Then** the log entry includes the prefix hash and a "miss reason" field (e.g., first-call, prefix-changed, ttl-expired, provider-cache-unavailable).
3. **Given** the cache hit rate drops below a configured threshold for a node over a rolling window, **When** the maintainer views the dashboard, **Then** an alert is visible.
4. **Given** the metrics are scraped, **When** the maintainer groups by graph, **Then** per-graph cache hit rate is available alongside the existing token consumption metrics.

---

### User Story 3 - Prompts Are Layered For Cacheability (Priority: P2)

As a developer, when I write or modify a prompt for any of the 5 graphs, I want a clear structural discipline that places stable content (system prompt, tool definitions, resume snapshot, requirements block) at the prefix and dynamic content (user message, current question, score-so-far) at the tail, so that the cacheable prefix is maximized.

**Why this priority**: Caching only works if the prefix is actually stable. Without a layering discipline, a developer who innocently prepends a timestamp or interleaves user data into the system prompt will silently break caching. P2 because it is the engineering discipline that makes US1 sustainable.

**Independent Test**: Can be fully tested by auditing each of the 5 graphs' prompt assembly, confirming that no dynamic content appears before the stable prefix, and that a regression in layering is detectable via cache hit rate drop in the eval suite.

**Acceptance Scenarios**:

1. **Given** a developer writes a prompt for the interview score node, **When** the prompt is assembled at runtime, **Then** the order is: system prompt → tool definitions → resume snapshot → requirements → (dynamic) user answer + current question.
2. **Given** tool definitions are present, **When** they are serialized, **Then** they are ordered deterministically (e.g., alphabetical by tool name) so adding a new tool doesn't reorder the existing ones.
3. **Given** a prompt change accidentally places dynamic content before stable content, **When** the eval suite runs (feature 026), **Then** the cache hit rate metric flags the regression.
4. **Given** a new graph is added, **When** its prompt is reviewed, **Then** the layering discipline is checked as part of code review.

---

### User Story 4 - Quota Model Reflects Cached Discount (Priority: P3)

As a user, my monthly token quota should reflect the actual cost I incur — cached input tokens should be charged at the provider's cached rate, not the full rate, so that my 500K monthly quota effectively buys more agent work.

**Why this priority**: User-facing fairness. Without this, the pre-deduct/actual-adjust model would charge full price for cached tokens, and the cost savings from US1 would be invisible to the user. P3 because it depends on US1 (caching must work first) and US2 (cache hit must be observable to compute the discount).

**Independent Test**: Can be fully tested by running one interview session, then querying the user's quota ledger, and confirming that cached input tokens are charged at the cached rate and the total effective charge is less than the raw token sum.

**Acceptance Scenarios**:

1. **Given** an LLM call returns 1000 cached input tokens and 500 uncached input tokens, **When** the quota actual-adjust runs, **Then** the ledger charges (1000 × cached_rate + 500 × full_rate + output_tokens × output_rate).
2. **Given** the pre-deduct estimate uses a conservative upper bound, **When** the actual-adjust runs, **Then** the difference is refunded to the user's quota.
3. **Given** the user views their monthly quota usage, **When** they open the settings page, **Then** they see both raw tokens consumed and effective tokens charged (with the cache discount line).
4. **Given** the provider's cached rate changes, **When** the config is updated, **Then** subsequent calls use the new rate without code changes.

---

### Edge Cases

- What happens when the provider's cache API is unavailable? → Fall back to uncached invocation, log a warning with the prefix hash, no user-facing error.
- What happens when the prefix changes between calls (e.g., resume snapshot updated mid-session)? → Cache miss on the changed segment; stable segments (system prompt, tools) still hit.
- What happens when two concurrent calls share the same prefix? → Provider handles dedup; both calls report a hit.
- What happens when the cache TTL expires mid-session? → Next call is a miss (expected); subsequent calls hit again.
- What happens when PII is accidentally placed in the prefix? → The cache entry is invalidated; FR-012 enforces PII stays in the dynamic tail.
- What happens when the pre-deduct estimate is wildly off (e.g., cache hit rate surprise)? → Actual-adjust corrects; user is never over-charged beyond the conservative upper bound.

## Requirements

### Functional Requirements

**Prompt layering**

- **FR-001**: LLM client MUST assemble each request so the cacheable prefix (system prompt, tool definitions, stable context like resume snapshot and requirements block) precedes the dynamic tail (user message, current question, score-so-far).
- **FR-002**: Tool definitions MUST be serialized in a deterministic order (alphabetical by tool name) so adding a tool does not reorder existing entries and invalidate the cache.
- **FR-003**: Resume snapshot content MUST be placed in the cacheable prefix when it is unchanged within a session.
- **FR-004**: Per-call dynamic content (user's free-text answer, current question text, accumulated scores) MUST be placed in the dynamic tail, never in the prefix.
- **FR-005**: Personally identifiable information from user input MUST NOT appear in the cacheable prefix.

**Cache invocation**

- **FR-006**: LLM client MUST emit cache-control signals per the provider's protocol for segments marked as stable.
- **FR-007**: LLM client MUST record cache hit/miss status, cached input token count, and uncached input token count per invocation.
- **FR-008**: LLM client MUST gracefully fall back to uncached invocation when the provider's cache API is unavailable, with a structured warning logged.
- **FR-009**: LLM client MUST compute a prefix hash for each stable segment so cache misses are diagnosable.

**Quota accounting**

- **FR-010**: Quota pre-deduct MUST estimate using a conservative upper bound (assume cache miss) so users are never under-charged mid-call.
- **FR-011**: Quota actual-adjust MUST charge cached input tokens at the provider's cached rate and uncached input tokens at the full rate.
- **FR-012**: The cached rate and full rate MUST be configurable per model without code changes.
- **FR-013**: Monthly quota report MUST show raw tokens consumed, effective tokens charged, and the cache discount applied.

**Observability**

- **FR-014**: System MUST expose cache hit rate as a metric per node and per graph.
- **FR-015**: System MUST log cache misses with the prefix hash and a miss-reason field (first-call, prefix-changed, ttl-expired, provider-cache-unavailable).
- **FR-016**: System MUST expose a counter for cache discount applied (tokens saved) per user and per graph.

**Testing infrastructure**

- **FR-017**: The deterministic mock LLM client MUST simulate cache hits and misses so cache-aware logic is testable without the real provider.
- **FR-018**: The eval suite (feature 026) MUST include a regression case that detects cache hit rate drop when the prompt layering is broken.

### Key Entities

- **CachePrefix**: The stable prefix assembly for one call; attributes include prefix hash, component hashes (system prompt, tool defs, snapshot, requirements), node, version.
- **CacheHitRecord**: Per-invocation cache outcome; attributes include trace id, node, prefix hash, hit/miss, cached tokens, uncached tokens, miss reason, cost saved.
- **QuotaLedger**: Per-user monthly quota; attributes include raw tokens consumed, effective tokens charged, cache discount applied, remaining quota.
- **PricingConfig**: Per-model pricing; attributes include model, full input rate, cached input rate, output rate, effective timestamp.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Cache hit rate ≥60% for input tokens across the interview graph end-to-end (5 questions + report).
- **SC-002**: Effective input token cost reduced by ≥40% on the interview graph versus the pre-feature baseline.
- **SC-003**: Monthly quota report shows raw vs effective token consumption per user, with the cache discount line visible.
- **SC-004**: A prompt change that breaks the cacheable prefix (e.g., reorders system prompt or injects dynamic content before stable content) is detectable via cache hit rate drop in the eval suite (feature 026).
- **SC-005**: Quota pre-deduct estimate is within ±15% of actual post-cache charge for ≥95% of calls.
- **SC-006**: Cache miss with a diagnostic log (including miss reason) is emitted for 100% of misses.
- **SC-007**: No user is over-charged beyond the conservative pre-deduct upper bound at any point during a call.

## Assumptions

- DeepSeek V4 Pro's context caching API is the target; specific protocol details (cache-control headers, segment markers) are validated in planning.
- Cache TTL follows the provider default (typically minutes); explicit TTL tuning is out of scope for this feature.
- No new infrastructure is introduced; caching is provider-side.
- The deterministic mock LLM client is extended to simulate cache behavior; no new test framework is added.
- Frontend quota display receives a minimal update to show effective vs raw tokens; full UX redesign is deferred.
- Constitution Principle V (Observability) is extended: cache hit rate and cache discount metrics join the existing token consumption metric set.
- Constitution Principle III (Test-First): cache-aware logic is testable via the mock client before hitting the real provider.
- The pre-deduct/actual-adjust model in `LLMClient` is the integration point; no new quota subsystem is built.
- Per-node token estimates in `TokenEstimator` may need refinement to reflect post-cache effective cost; done in planning.
- Pricing configuration is externalized (env var or config file) so rate changes don't require code deploys.
