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
| Quoted/unparseable paths | **1,850** (preserved; see §7) |
| Snapshot time | 2026-07-12 at time of dispatch |

> **Verify:** These counts match the authoritative `git status --porcelain=v1 -uall` output from the primary root.

---

## 2. Status Breakdown

### 2.1 Modified Entries (5)

All 5 modified entries are working-tree changes. These are NOT part of the Phase 5c scope and remain unmodified by this work.

### 2.2 Untracked Entries (7,946)

Aggregated by top-level group (`top_group` in manifest):

| Top Group | Count | Proposed Ownership |
|---|---|---|
| `docs/` | 4,259 | Publish via Issue/dispatch/PR |
| `needs_manual_review` (quoted paths) | 1,850 | Manual review required |
| `backend/` | 422 | Archive outside repo; approved ignore |
| `.team-test-cc/` | 382 | Retained named user work |
| `.claude/` durable retained | 202 | Approved ignore (durable assets remain) |
| `.team-test/` | 167 | Retained named user work |
| `.test-acceptance/` | 131 | Retained named user work |
| `.claude/` runtime removed | 125 | Approved ignore (Phase 5c) |
| `test-reports/` | 106 | Publish via Issue/dispatch/PR |
| `specs/` | 100 | Publish via Issue/dispatch/PR |
| `tmp/` | 47 | Archive outside repo |
| `tests/` | 39 | Publish via Issue/dispatch/PR |
| `team-autonomous-loop-workspace/` | 20 | Retained named user work |
| `.claude/bug-tickets/` | 14 | Approved ignore (Phase 5c preemptive) |
| `.claude/` unclassified | 13 | Manual review |
| `.worktrees/` | 9 | Archive outside repo |
| Other | 13 | Manual review / per-item routing |

---

## 3. Ownership Categories

Per the dirty-worktree CSV classification, each entry is assigned one of the following ownership categories via the `rationale_code` field:

### 3.1 Publish via Issue/dispatch/PR

Entries in this category represent work product that should be routed through the normal delivery pipeline. These include:
- `docs/` — documentation changes
- `test-reports/` — test output
- `specs/` — specification documents
- `tests/` — test artifacts

**Phase 10 routing:** These should be submitted as PRs against the primary repository following the standard governance process.

### 3.2 Archive Outside Repository

Entries that are build artifacts, runtime data, or temporary files that should not be committed:
- `backend/` build artifacts (`.venv`, `.ruff_cache`, etc.)
- `tmp/` temporary files
- `.worktrees/` git worktree metadata

These should be cleaned from disk or added to appropriate `.gitignore` rules in future phases.

### 3.3 Approved Ignore (via .gitignore)

Entries that are now covered by `.gitignore` rules:
- `.claude/settings.local.json` — Phase 5c
- `.claude/state.json` — Phase 5c
- `.claude/agent-memory/` — Phase 5c
- `.claude/teams/` — Phase 5c
- `.claude/bug-tickets/` — Phase 5c (preemptive)
- `.claude/durable retained (agents/commands/skills/settings.json)` — explicitly NOT ignored

### 3.4 Retained Named User Work

Entries that represent user-specific or team-specific working state:
- `.team-test-cc/` — test CC configuration
- `.team-test/` — test configuration
- `.test-acceptance/` — acceptance test working data
- `team-autonomous-loop-workspace/` — autonomous loop workspace

These are intentionally left untracked and unignored; they belong to individual users or teams and should not be committed.

### 3.5 Manual Review Required

Entries where the classification could not be automatically determined:
- Quoted/unparseable paths (1,850) — paths with special characters that `git status` quoted
- `.claude/` unclassified entries (13) — unusual files in `.claude/` that don't match known patterns
- Other top-level entries that don't fit known categories

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
| **SHA-256** | `A56548B350E3DD455B8F22B1CB4D8EB27F2EB5115CAFC94365537D9C02A9C369` |
| **Headers** | `status`, `path`, `top_group`, `proposed_category`, `rationale_code` |
| **Format** | UTF-8 CSV with RFC 4180 quoting |

---

## 6. Phase 10 Routing & Acceptance

The dirty worktree is NOT clean after this phase. Phase 5c only addresses tracked Claude runtime files and their gitignore rules. Future phases (Phase 6+) will address additional categories.

| Phase | Scope | Status |
|---|---|---|
| Phase 5c | Claude runtime tracked files + gitignore ✅ | **Done** |
| Phase 6+ | Build artifacts, temp files | **Not started** |
| Phase 7+ | Documentation/report publishing | **Not started** |
| Phase 8+ | Named user workspace handling | **Not started** |
| Phase 9+ | Manual review of unclassified/quoted paths | **Not started** |
| Phase 10 | Final routing of publishable work | **Not started** |

**Acceptance criteria for this phase:**
1. ✅ All 21 tracked runtime files removed from Git tracking
2. ✅ .gitignore rules added for runtime directories (narrow, not blanket)
3. ✅ External backup verified before removal
4. ✅ External CSV manifest generated and verified (7,951 rows)
5. ✅ Runtime & secret audit document created
6. ✅ Dirty worktree reconciliation document created
7. ❌ Primary root is NOT clean — and should not be claimed as such
