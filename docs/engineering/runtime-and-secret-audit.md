# Runtime & Secret Audit — REQ-064 Phase 5c

> **Dispatch:** req-064-phase5c-20260712-01
> **Date:** 2026-07-12
> **Base:** `b15130155b8dc75bc68d4294949c176f1387751e`
> **Branch:** `codex/064-phase5c-runtime-reconciliation`
> **AC Hash:** `0fdc18c53b4af3b2d1f9791d6441e17d1d3853e9e930f3618e4e20de97c90c6c`
> **Operator:** Claude Code (deepseek-v4-flash)

---

## 1. Scope

This audit covers two parallel concerns mandated by REQ-064 Phase 5c:

1. **Runtime reconciliation** — removal from Git tracking of 21 Claude runtime/local files that are machine-local or ephemeral by nature.
2. **Secret scan** — classification of historical credential-like patterns found in the reachable object graph, with explicit no-claim of live-secret validation.

Tracked-file removal, hashing, and history scanning run only in the clean
external worktree `D:\Project\eGGG-phase5c-clone`. The primary root
`D:\Project\eGGG` is queried only for NUL-delimited Git status metadata used by
the external manifest; Phase 5c does not read or mutate its file contents.

---

## 2. External Backup

A repository-external backup of the 21 tracked runtime/local files was created before any removal.

| Field | Value |
|---|---|
| **Path** | `D:\Project\eGGG-governance-audit\phase5c-tracked-claude-runtime-b151301.zip` |
| **Size (bytes)** | 68,653 |
| **SHA-256** | `D48B64A7534922057F3003B16A17F64820E92748888D73D6989E7E3114E8D0F3` |

**Verification status:** ✅ Hash matches expected. Backup confirmed intact before any `git rm` operation.

---

## 3. Removed Inventory — 21 Tracked Runtime/Local Files

All files below were removed from the branch with `git rm`. After merge, future
clones will not contain them and an unchanged local tracked copy may be removed
when that checkout updates. The repository-external backup and Git history are
therefore the recovery sources; this audit does not claim the files remain on
disk.

### 3.1 `.claude/agent-memory/` (9 files)

| # | Path | Git Blob | Blob Size | SHA-256 |
|---|---|---|---|---|
| 1 | `.claude/agent-memory/analyzer/MEMORY.md` | `30d2de32` | 321 | `4E9BD21962B4...` |
| 2 | `.claude/agent-memory/analyzer/admin_console_baseline.md` | `e4f94388` | 2,048 | `E9451E6A7C0F...` |
| 3 | `.claude/agent-memory/analyzer/req044_worktree_spec_gap.md` | `9b6b663b` | 1,030 | `9A2533B50B65...` |
| 4 | `.claude/agent-memory/dev/MEMORY.md` | `b72d50f8` | 4,574 | `6E9CA56023C9...` |
| 5 | `.claude/agent-memory/dev/req_044_us3_seed_pattern.md` | `860bc4a9` | 2,468 | `B5945DF2F741...` |
| 6 | `.claude/agent-memory/dev/req_044_us7_metric_trust.md` | `358552af` | 4,238 | `4E42B3C1EBC5...` |
| 7 | `.claude/agent-memory/dev/req_044_cross_saved_views.md` | `7f66d822` | 2,408 | `D19A6A39D73C...` |
| 8 | `.claude/agent-memory/req_044_us1_seed_pattern.md` | `7c67d3c8` | 1,783 | `CFB5D757C139...` |
| 9 | `.claude/agent-memory/req_044_us4_seed_pattern.md` | `83ad613d` | 2,016 | `2A5F7DB0B982...` |

### 3.2 `.claude/teams/` (10 files)

| # | Path | Git Blob | Blob Size | SHA-256 |
|---|---|---|---|---|
| 10 | `.claude/teams/req044/ac-matrix/REQ-044-US3.md` | `15351a20` | 10,918 | `3BDF1B27C561...` |
| 11 | `.claude/teams/req038/test-reports/REQ-038-review.md` | `1b8a6150` | 5,213 | `A08ACCCAC9E8...` |
| 12 | `.claude/teams/req044/ac-matrix/REQ-044-CROSS.md` | `2c712c44` | 9,046 | `569B1414AF8B...` |
| 13 | `.claude/teams/req044/ac-matrix/REQ-044-US5.md` | `54249c86` | 10,661 | `BCB4914B2854...` |
| 14 | `.claude/teams/req038/ac-matrix/REQ-038.md` | `8ee28310` | 26,052 | `9856D494E865...` |
| 15 | `.claude/teams/req044/ac-matrix/REQ-044-US7.md` | `a8d3064e` | 17,570 | `372BE5C6E375...` |
| 16 | `.claude/teams/req044/ac-matrix/REQ-044-US6.md` | `cd11c710` | 17,646 | `1E38474B3C60...` |
| 17 | `.claude/teams/req044/ac-matrix/REQ-044-US2.md` | `ceba6630` | 11,712 | `F425812FD3E4...` |
| 18 | `.claude/teams/req044/ac-matrix/REQ-044-US4.md` | `db2cb365` | 10,366 | `6AE8C67D86C2...` |
| 19 | `.claude/teams/req044/ac-matrix/REQ-044-US1.md` | `dd3cf2a7` | 13,356 | `C95C89CEDBF7...` |

### 3.3 State & Local Settings (2 files)

| # | Path | Git Blob | Blob Size | SHA-256 |
|---|---|---|---|---|
| 20 | `.claude/state.json` | `2ae01a1d` | 1,155 | `D269FC481EB5...` |
| 21 | `.claude/settings.local.json` | `41ea43f2` | 5,756 | `57E92693C763...` |

**Total removed from tracking:** 21 files
**Total backup size:** 68,653 bytes (compressed archive)

---

## 4. Retained Durable Classes

The following project assets were explicitly **not** removed and remain Git-tracked:

| Category | Count | Examples |
|---|---|---|
| `.claude/settings.json` | 1 | Canonical project settings |
| `.claude/agents/` | 6 | `main-agent.md`, `dev.md`, `tester.md`, `playwright-test-*` |
| `.claude/commands/` | 8 | `build.md`, `plan.md`, `ship.md`, `spec.md`, `test.md`, etc. |
| `.claude/skills/` | 50 | All skill definitions |
| `.cursor/rules/` | 1 | `agent-delivery.mdc` |

These are durable, version-controlled project definitions — not machine-local or ephemeral state.

**Total retained durable assets:** 66 (1 project settings file + 6 agents + 8
commands + 50 skills + 1 Cursor rule).

---

## 5. Gitignore Rules Added

The following narrow rules were appended to `.gitignore` (see file at repository root):

```gitignore
# Claude runtime/local artifacts — tracked removals per REQ-064 Phase 5c
.claude/settings.local.json
.claude/state.json
.claude/agent-memory/
.claude/teams/
.claude/bug-tickets/
```

**Design principles:**
- **Narrow scope only:** Does NOT ignore all `.claude/` or `.cursor/` — the durable classes above remain tracked.
- **Future-proofing:** `.claude/bug-tickets/` is included preemptively (no files exist yet) to prevent accidental tracking of auto-generated ticket caches.
- **No agent/command/skill/settings.json/rules exclusion:** All project-definition files remain visible to Git.

---

## 6. Rollback Implications

Rollback is another governed PR: create a rollback Issue/dispatch/branch from
authoritative `master`, then run `git revert <phase-5c-squash-sha>` without
`-m`. That inverse commit restores the tracked versions and removes the ignore
rules together. Use the external backup only when local runtime content must be
recovered independently of the tracked historical versions; never extract it
over unclassified user work.

**Risk:** Updating a checkout after this merge can remove unchanged tracked
runtime copies. The verified external backup is required before merge and must
be retained until Phase 10 reconciliation is accepted.

---

## 7. Secret Scan

### 7.1 Codex Scan Evidence

- **Reachable commits:** 258
- **Reachable objects:** 7,397
- **High-confidence regex targets:** structured provider API-key prefixes and
  private-key headers. Generic `secret`/`token`/`password` assignments were not
  included in this pass because they require a separate entropy-aware scanner.
- **Historical match entries:** 441 (aggregate across all commits for the three identified paths)

### 7.2 Path Classifications

#### Path A: `backend/tests/integration/fixtures/033_redaction_samples.py`

| Field | Value |
|---|---|
| **Type** | Redaction test fixture |
| **Classification** | ✅ **Redaction fixture** — intentional test samples for exercising the redaction pipeline |
| **Live secret?** | **Not validated.** File/function context identifies an intentional redaction fixture (value-hash prefix `CBC69B4F8705`); no provider call was made and no live-status claim is made. |
| **Action** | No change required; redaction fixture serves its purpose. |

#### Path B: `specs/003-phase4-interview-agent/contracts/llm-client.md`

| Field | Value |
|---|---|
| **Type** | Documentation / specification |
| **Classification** | ⚠️ **Credential-like documentation example** — contains a documented `DEEPSEEK_API_KEY` value used as a usage illustration in a spec document |
| **Live secret?** | **Not proven live.** The value-hash prefix `048055C74692` appears in documentation context at line 132 and traces to initial commit `0282157`. No runtime validation was performed to determine whether it is active, revoked, or dummy. |
| **Action** | Require continued redaction: treat as potentially sensitive documentation; do not reuse or expose. Future engineering should replace with a placeholder (e.g., `sk-...replace-me...`) in the spec. |

#### Path C: `src/components/ai/AITaskActions.tsx`

| Field | Value |
|---|---|
| **Type** | React component |
| **Classification** | ✅ **Regex false positive** — the broad `sk-` branch matched characters inside a React `data-testid` value, not a credential field. |
| **Live secret?** | No. All matches are UI test identifiers, not credentials. |
| **Action** | None required. No credential values present. |

### 7.3 GitHub Secret Scanning API

```
GET https://api.github.com/repos/Sandape/interCraft/secret-scanning/alerts
Responses observed in separate attempts: HTTP 404 and HTTP 403
```

The GitHub secret-scanning API was **unavailable** (not authorized/not found).
No upstream alerts were incorporated. This audit relies on a redacted local
pattern scan across reachable commit snapshots; matching values were not
written to the report.

### 7.4 Limitations & Honest Disclosure

1. **No live-secret validation performed.** No runtime connectivity test was executed against any detected credential-like value. A string resembling a provider key in documentation or fixtures has **not** been tested against the provider's API.
2. **No secret values are recorded in this report.** All metadata (blob hashes, SHA-256 of content, path names) is safe for version control. Value-hash prefixes are truncated to 12 hex characters where shown.
3. **GitHub API unavailable.** The upstream GitHub secret-scanning alert feed could not be queried. Any alerts that may exist on the server side were not consulted.
4. **Scanner limitations.** Pattern-based regex scanning produces both false positives (like `data-testid`) and may miss obfuscated or encoded credentials. This audit is a point-in-time sample, not a comprehensive cryptographic proof.
5. **No credential rotation was triggered.** Because no live secret was
   confirmed, no key rotation, revocation, or incident response was initiated.
   If the Owner cannot prove from provider-side inventory/rotation records that
   the documentation example was never live or is already revoked, rotate it;
   do not validate it by sending the historical value to a provider API.
