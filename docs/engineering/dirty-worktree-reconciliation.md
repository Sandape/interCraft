# Dirty Worktree Reconciliation — REQ-064 Phase 5c

> **Dispatch:** req-064-phase5c-20260712-01
> **Date:** 2026-07-12
> **Base:** `b15130155b8dc75bc68d4294949c176f1387751e`
> **Branch:** `codex/064-phase5c-runtime-reconciliation`
> **Primary root:** `D:\Project\eGGG`
> **Manifest:** `D:\Project\eGGG-governance-audit\dirty-worktree-manifest-20260712.csv`
> **Operator:** Claude Code (deepseek-v4-flash)

---

## 1. Baseline

| Metric | Value |
|---|---|
| **Total dirty entries** | **7,951** |
| Modified (` M`) | **5** |
| Untracked (`??`) | **7,946** |
| Quoted/unparseable paths | **0** — manifest regenerated from NUL-delimited (`-z`) status output |
| Snapshot time | 2026-07-12 at time of dispatch |

> **Verify:** These counts match the authoritative `git status --porcelain=v1 -uall` output from the primary root.

---

## 2. Status Breakdown

### 2.1 Modified Entries (5)

All five are preserved and require an owner before routing:

- `.specify/feature.json`
- `AGENTS.md`
- `CLAUDE.md`
- `backend/tests/conftest.py`
- `specs/README.md`

### 2.2 Untracked Entries (7,946)

The NUL-safe manifest deliberately uses conservative categories; filenames are
decoded exactly and no path content was read:

| Proposed category | Count | Meaning |
|---|---:|---|
| `needs_owner_assignment` | 7,067 | Includes 6,104 evidence candidates, 756 runtime/test workspaces, 202 durable-tooling candidates, and the 5 tracked modifications; none is treated as named user work until a person accepts ownership |
| `publish_via_dispatch_pr` | 318 | Source/spec/test/document candidates that still require an Issue, exact allowlist, and review before publication |
| `approved_ignore` | 139 | Claude runtime paths covered by the narrow Phase-5c ignore policy |
| `needs_manual_review` | 427 | Paths not safely classified by path-only rules |

Largest exact top-level groups are `docs/` (6,109), `backend/` (422),
`.team-test-cc/` (382), `.claude/` (354), `.team-test/` (167),
`.test-acceptance/` (131), `test-reports/` (106), `specs/` (100), `tmp/`
(47), and `tests/` (39).

---

## 3. Ownership Categories

Per the dirty-worktree CSV classification, each entry is assigned one of the following ownership categories via the `rationale_code` field:

### 3.1 Publish via Issue/dispatch/PR

These 318 path-only candidates may be work product, but the category is not
publication approval. Phase 10 must group them by owner and requirement, create
bounded Issues/dispatches, inspect content safely, and publish only the groups
that pass review.

### 3.2 Archive Outside Repository

No current row is pre-approved for archival. A path may move into this category
only after an owner confirms it is reproducible/non-durable and the archive
destination/hash is recorded. `backend/`, `tmp/`, and workspace names alone are
not sufficient evidence for deletion or ignore rules.

### 3.3 Approved Ignore (via .gitignore)

The 139 manifest rows under these paths are covered by the reviewed Phase-5c
ignore policy:
- `.claude/settings.local.json` — Phase 5c
- `.claude/state.json` — Phase 5c
- `.claude/agent-memory/` — Phase 5c
- `.claude/teams/` — Phase 5c
- `.claude/bug-tickets/` — Phase 5c (preemptive)

Durable `.claude/agents`, `.claude/commands`, `.claude/skills`,
`.claude/settings.json`, and `.cursor/rules` are explicitly not ignored.

### 3.4 Retained Named User Work

No row is considered “named user work” merely because it lives in a team or
test directory. The 7,067 `needs_owner_assignment` rows must receive an owner,
retention decision, and next action. Until then they remain untracked,
unignored, and untouched.

### 3.5 Manual Review Required

The 427 path-only unknowns require manual ownership review. This count no longer
includes Git-quoted filenames: NUL-delimited parsing decoded those names safely.

---

## 4. Non-Destructive Prohibitions

The following operations are **prohibited** as part of this Phase 5c work:

1. **No `git clean`** — will not be executed. Removing untracked files is outside scope.
2. **No `git reset --hard`** — will not be executed. Modified working tree files are preserved.
3. **No deletion of primary-root files** — file contents are NOT read or mutated.
4. **No `.gitignore` blanket patterns** — only narrow, path-specific rules were added.
5. **No Phase 6 work** — Phase 5c ends at commit + PR. No further reconciliation phases are started.

---

## 5. External Manifest

| Field | Value |
|---|---|
| **Path** | `D:\Project\eGGG-governance-audit\dirty-worktree-manifest-20260712.csv` |
| **Rows** | 7,951 (7,946 untracked + 5 modified) |
| **SHA-256** | `21113B401D714D4DC0C49DE996D5D5253D978E54708A224A0027CDB044871FB2` |
| **Headers** | `status`, `path`, `top_group`, `proposed_category`, `rationale_code` |
| **Format** | UTF-8 CSV generated from `git status --porcelain=v1 -z -uall`; raw paths are NUL-delimited before RFC 4180 CSV quoting |

---

## 6. Phase 10 Routing & Acceptance

The dirty worktree is NOT clean after this phase. Phase 5c only addresses the
reviewed Claude runtime class and produces a trustworthy handoff manifest.
Phases 6–9 retain their existing governance/CI/automation scopes; they must not
silently absorb dirty-root cleanup. Phase 10 owns final routing.

| Phase | Scope | Status |
|---|---|---|
| Phase 5c | Claude runtime tracked files + narrow ignore + manifest | **In review until PR merge/verification** |
| Phase 6–9 | Existing REQ-064 intake/gate, CI, automation, and drill scopes | **No dirty-root routing added** |
| Phase 10 | Assign owners; route publish/archive/ignore/retain decisions; prove zero unexplained entries | **Not started** |

**Acceptance criteria for this phase:**
1. All 21 tracked runtime files are removed by this PR and recoverable from the verified backup/history.
2. Ignore rules are narrow and durable project assets remain visible.
3. The external manifest has 7,951 NUL-safely parsed rows and the recorded hash.
4. Phase 10 starts with 7,067 owner assignments, 318 publication candidates,
   139 approved-ignore rows, and 427 manual reviews; every later decision must
   update the manifest/evidence rather than bulk-delete.
5. Primary root is NOT clean and this document must never be used to claim it is.
