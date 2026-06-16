# Research: Error Book Completion

## Decision: Add a dedicated recall endpoint

**Rationale**: Existing docs for M08 list `POST /api/v1/error-questions/{id}/recall`, but current code only supports direct PATCH status changes and reset. A dedicated action is safer for the primary learning loop because clients do not need to compute legal frequency/status pairs.

**Alternatives considered**:

- Continue using PATCH status transitions only: rejected because it duplicates state-machine logic in the UI and makes “答对一次” ambiguous.
- Put recall only in Error Coach: rejected because manual review belongs to M08 and must work without Agent execution.

## Decision: Derive status from frequency during recall

**Rationale**: The product model treats frequency as remaining weakness count. On recall, frequency decreases by one; status follows frequency: 3 fresh, 2/1 practicing, 0 mastered. This keeps one visible mental model for users.

**Alternatives considered**:

- Let users manually choose status: retained for existing PATCH compatibility, but not used for the primary recall workflow.
- Archive automatically at frequency 0: rejected for this feature because mastered questions should remain reviewable and resettable.

## Decision: Keep soft delete as delete behavior

**Rationale**: Current backend already soft-deletes through `deleted_at`, and specs require default list/detail reads to hide deleted records. This preserves recoverability for future lifecycle modules without exposing deleted questions in normal use.

**Alternatives considered**:

- Change DELETE to archived status: rejected because existing code and tests already use `deleted_at`, and archived status remains a separate state concept.
- Physical deletion: rejected because it reduces audit/recovery options.

## Decision: Repair ErrorBook page in place

**Rationale**: The page already owns the module workflow, but currently contains mojibake text and invalid hook usage. Replacing the page with a focused, design-system-aligned implementation is lower risk than layering fixes around broken strings and runtime hazards.

**Alternatives considered**:

- Patch only the visible strings: rejected because hook misuse and missing recall UX would remain.
- Create a parallel page: rejected because it would split routes and tests.

## Decision: E2E covers normal completion and interrupted return

**Rationale**: The acceptance criteria explicitly asks for a normal business flow and an abnormal leave/re-enter flow. For this module, the equivalent is a create -> recall-to-mastered flow and a create/recall -> navigate away -> return flow.

**Alternatives considered**:

- Only API tests: rejected because they cannot catch broken page text, invalid hooks, or visual workflow failures.
