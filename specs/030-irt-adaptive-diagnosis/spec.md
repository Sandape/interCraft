# Feature Specification: IRT-Based Adaptive Ability Diagnosis

**Feature Branch**: `[030-irt-adaptive-diagnosis]`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "2-PL/3-PL IRT 模型，基于历史 ability profile θ 自适应选题，重测信度从 ~0.5 提到 ~0.85。题库标定策略。"

## User Scenarios & Testing

### User Story 1 - Questions Carry Calibrated IRT Parameters (Priority: P1)

As a psychometrician-equivalent maintainer, each interview question in the item bank must carry calibrated Item Response Theory parameters — difficulty (b), discrimination (a), and for multiple-choice items guessing (c) — so that user ability can be modeled mathematically rather than via a simple weighted average of scores.

**Why this priority**: IRT parameters are the foundation — without them, θ estimation and adaptive selection are impossible. The current ability diagnosis aggregates dimension scores with weights, which conflates question difficulty with user ability and yields low retest reliability (~0.5). P1 because everything else in this feature depends on having calibrated items.

**Independent Test**: Can be fully tested by running a calibration batch over historical interview responses and confirming each calibrated item has b, a, and (for multiple-choice) c parameters with convergence status recorded.

**Acceptance Scenarios**:

1. **Given** historical interview responses exist for ≥30 users per item, **When** a calibration batch runs, **Then** each item receives b, a, and (for MC) c parameters with a convergence status.
2. **Given** an item has <30 responses, **When** calibration runs, **Then** the item is marked "uncalibrated" with a prior estimate and excluded from θ estimation.
3. **Given** calibration converges, **When** the maintainer views the item bank, **Then** each item shows its parameters, response count, standard error, and last-calibrated timestamp.
4. **Given** an item's discrimination parameter falls below threshold, **When** calibration completes, **Then** the item is flagged for review.

---

### User Story 2 - User Ability θ Estimated Per Dimension (Priority: P2)

As a user, my ability profile should reflect a mathematically sound θ estimate per dimension (with confidence interval), rather than a weighted average of raw scores, so that my profile is comparable across time and across different question sets.

**Why this priority**: θ estimation is the user-facing value of IRT. P2 because it requires US1 (calibrated items) to be in place; the system works without it (falls back to weighted average) but loses the psychometric rigor.

**Independent Test**: Can be fully tested by running 2 interviews for the same user within 7 days, then comparing the θ estimates per dimension and confirming they fall within the retest reliability tolerance band (≥0.85).

**Acceptance Scenarios**:

1. **Given** a user completes an interview with calibrated items, **When** the ability profile is computed, **Then** each dimension shows a θ value with standard error and confidence interval.
2. **Given** the same user takes 2 interviews within 7 days, **When** both θ estimates are computed, **Then** they correlate at ≥0.85 per dimension.
3. **Given** a user has <3 interviews, **When** their profile is displayed, **Then** the θ estimate is marked "low confidence" with a wide confidence interval.
4. **Given** the ability profile history is viewed, **When** the user scrolls over time, **Then** θ evolution per dimension is visible.

---

### User Story 3 - Adaptive Question Selection Based On θ (Priority: P2)

As a user in diagnostic mode, the next question's difficulty should target my current θ estimate's confidence interval, so that each question maximizes information gain about my ability rather than being a fixed-difficulty shot.

**Why this priority**: Adaptive selection is the interactive payoff of IRT — fewer questions, more ability information. P2 because it requires US1 and US2; the existing fixed-5-question mock interview mode is preserved as an alternative.

**Independent Test**: Can be fully tested by running a diagnostic-mode interview and confirming that ≥70% of question selections have difficulty within ±0.5 logits of the running θ estimate.

**Acceptance Scenarios**:

1. **Given** a user starts a diagnostic-mode interview, **When** question 2 is selected, **Then** its difficulty falls within the confidence interval of the θ estimate after question 1.
2. **Given** the user answers question 1 correctly, **When** question 2 is selected, **Then** its difficulty is higher than question 1's.
3. **Given** the user answers question 1 incorrectly, **When** question 2 is selected, **Then** its difficulty is lower than question 1's.
4. **Given** the calibrated item bank is exhausted for a dimension, **When** adaptive selection runs, **Then** the system falls back to uncalibrated items with prior estimates (no dead-end).

---

### User Story 4 - Item Bank Maintenance (Priority: P3)

As a maintainer, I want the item bank to be maintained over time — new items calibrated, stale or compromised items retired, bank health monitored — so that the diagnostic quality does not degrade as questions leak or age.

**Why this priority**: Bank maintenance is the long-term sustainability layer. P3 because it requires US1 to be in place; the system works without active maintenance but quality drifts.

**Independent Test**: Can be fully tested by adding a new question, running 50 simulated responses, and confirming the item reaches "calibrated" status, then marking it retired and confirming it's excluded from future selection.

**Acceptance Scenarios**:

1. **Given** a new question is added, **When** it accumulates 50 responses, **Then** it transitions from "uncalibrated" to "calibrated" with full IRT parameters.
2. **Given** an item is compromised (e.g., leaked publicly), **When** the maintainer marks it retired, **Then** it is excluded from future selection but retained in historical response data.
3. **Given** the bank health dashboard is viewed, **When** the maintainer checks a dimension, **Then** it shows count of calibrated items, uncalibrated items, retired items, and average response count.
4. **Given** an item's parameters drift significantly across calibration runs, **When** the drift exceeds threshold, **Then** the item is flagged for review.

---

### Edge Cases

- What happens when a user has <3 interviews? → θ estimate has wide confidence interval, displayed as low-confidence; no adaptive selection until enough data.
- What happens when an item has <30 responses? → Marked "uncalibrated", excluded from θ estimation, but eligible for selection with prior estimate.
- What happens when all items in a dimension are retired? → Dimension marked "under maintenance", θ not computed, profile shows placeholder.
- What happens when calibration fails to converge? → Run marked failed, previous parameters retained, alert raised for maintainer review.
- What happens when response data is corrupted? → Affected items flagged, excluded from this calibration run, previous parameters retained.
- What happens when adaptive mode exhausts calibrated items? → Falls back to uncalibrated items with prior estimates; selection continues, confidence interval widens.
- What happens when a user takes 2 interviews far apart (e.g., 6 months)? → θ estimates may legitimately differ; retest reliability window is configurable.

## Requirements

### Functional Requirements

**Item calibration**

- **FR-001**: Each interview question MUST be tagged with an IRT item record containing difficulty (b), discrimination (a), and for multiple-choice items guessing (c).
- **FR-002**: IRT parameters MUST be calibrated from historical response data using a standard estimation method (e.g., marginal MLE).
- **FR-003**: Calibration MUST be runnable as a batch job (offline, ARQ) without blocking agent execution.
- **FR-004**: Items with insufficient responses (below a configurable threshold) MUST be marked "uncalibrated" and excluded from θ estimation.
- **FR-005**: Items with extreme parameters (e.g., discrimination below threshold) MUST be flagged for review.
- **FR-006**: The IRT model MUST be configurable per dimension (2-PL for open-ended, 3-PL for multiple-choice).

**Ability estimation**

- **FR-007**: System MUST estimate user ability θ per dimension after each interview using IRT, replacing the simple weighted average.
- **FR-008**: The ability profile MUST display θ-based scores with standard errors and confidence intervals.
- **FR-009**: θ estimates MUST be persisted with timestamps so evolution over time is visible.
- **FR-010**: Retest reliability MUST be measurable — same user taking 2 interviews within a configurable window produces θ estimates that correlate at ≥0.85 per dimension.

**Adaptive selection**

- **FR-011**: The interview graph MUST support a "diagnostic mode" where question selection is adaptive (information-gain maximized), separate from the existing "mock interview mode" (fixed 5 questions).
- **FR-012**: Adaptive selection MUST target the current θ estimate's confidence interval, with ≥70% of selections within ±0.5 logits of the running θ.
- **FR-013**: When calibrated items are exhausted, the system MUST fall back to uncalibrated items with prior estimates.

**Item bank maintenance**

- **FR-014**: New items MUST enter the bank with a prior estimate (e.g., from a difficulty self-assessment) and refine as responses accumulate.
- **FR-015**: System MUST support item retirement (compromised or stale items) without deleting historical response data.
- **FR-016**: The bank health dashboard MUST show per-dimension counts of calibrated, uncalibrated, and retired items, plus average response count.
- **FR-017**: Items whose parameters drift significantly across calibration runs MUST be flagged for review.

**Testing infrastructure**

- **FR-018**: The deterministic mock LLM client MUST be able to produce responses with known difficulty so IRT logic is unit-testable with ground-truth parameters.
- **FR-019**: The eval suite (feature 026) MUST include cases verifying that θ estimation is stable under prompt changes (i.e., the same response produces the same θ).

### Key Entities

- **Item**: id, dimension, question text hash, difficulty (b), discrimination (a), guessing (c, for 3-PL), status (calibrated/uncalibrated/retired/flagged), response count, standard error, last calibrated at.
- **AbilityTheta**: user id, dimension, θ value, standard error, confidence interval, computed at, source interview ids.
- **ItemResponse**: user id, item id, response (correct/partial/incorrect), score, timestamp, source interview id.
- **CalibrationRun**: id, run at, items processed, model (2-PL/3-PL), convergence status, duration, metrics.
- **ItemBankHealth**: dimension, calibrated count, uncalibrated count, retired count, average response count, drift flags.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Each dimension has ≥10 calibrated items with response count ≥30.
- **SC-002**: Retest reliability (same user, 2 interviews within 7 days) ≥0.85 per dimension.
- **SC-003**: θ estimate standard error ≤0.5 (logit scale) for users with ≥3 interviews.
- **SC-004**: Adaptive mode selects questions with difficulty within ±0.5 logits of current θ for ≥70% of selections.
- **SC-005**: Calibration batch completes within 30 minutes for the current item bank.
- **SC-006**: New items reach "calibrated" status within 50 responses.
- **SC-007**: Items with extreme parameters are flagged within 1 calibration run.
- **SC-008**: Retest reliability improves from the pre-feature baseline (~0.5) to ≥0.85.

## Assumptions

- IRT implementation uses a standard library (e.g., py-irt) or a custom 2-PL/3-PL MLE; the specific choice is decided in planning.
- Historical interview response data is the calibration source; no external item bank is imported.
- The existing 5-question mock interview mode is preserved; adaptive mode is an opt-in alternative.
- Constitution Principle I (Library-First): IRT is a new self-contained module, callable independently.
- Constitution Principle II (CLI Interface): calibration is runnable via CLI and ARQ.
- Constitution Principle III (Test-First): IRT math is unit-tested with known ground-truth parameters.
- Constitution Principle V (Observability): calibration runs and item bank health are observable.
- 3-PL is only used for multiple-choice items; open-ended items use 2-PL.
- θ is per-dimension; cross-dimension correlation is out of scope for this feature.
- The LLM-generated questions are treated as candidate items; their difficulty parameters are calibrated, not assumed from LLM self-assessment.
- Retest reliability window defaults to 7 days; configurable per dimension.
- Frontend ability profile receives a minimal update to display θ and confidence interval; full visualization redesign is deferred.
