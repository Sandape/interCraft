---
name: req-044-us4-seed-pattern
description: REQ-044 US4 incidents/badcases seed pattern + EC-1/2/3/4 coverage strategy
metadata:
  type: project
---

REQ-044 US4 ships an operations-led workspace for incident triage + badcase review (FR-021~FR-023). 12 endpoints, 19 ACs, all under `backend/app/modules/admin_console/incidents/`.

**Why:** The seed must satisfy 4 Edge Cases simultaneously without silent empty fallback. Operations is the primary audience; reviewers get BADCASE_CHANGE because the badcase review workflow is owned by reviewers; viewers remain denied (FR-031 least-privilege).

**How to apply:** The 6-incident seed covers all 4 severities (P0-P3), all 4 statuses (open/investigating/resolved/postmortem), all 3 trends (rising/stable/declining), and the 4 Edge Cases:
- 1 P2 candidate with `candidate=True` (EC-1) — front-end MUST render "candidate" label and not merge with confirmed
- 2 incidents with `common_root_cause="db-timeout-cluster"` + cross-link `linked_incident_ids` (EC-2)
- 1 incident with `ingestion_delayed=True` + `freshness_at` (EC-3)
- 1 incident with 2 prior `audit_trail` entries (EC-4)

The 4-badcase seed covers all 4 statuses (open/reviewing/closed/escalated) and 3 privacy classes (public/internal/restricted). Evidence list returns exactly 8 links per incident (one per FR-022 type) with a `coverage` map so the front-end can render 8 sections with empty-state badges.

Sort key: incidents sorted by `(severity desc, last_seen_at desc)` per FR-021 AC-21.2. Badcases sorted by `first_seen_at desc`.

**Audit 2-stage pattern:** US4 added 4 new audit actions but migration 0022's CHECK constraint only accepts 4 US1 actions. Solution: Python-side `_DB_BLOCKED_ACTIONS` frozenset + `_write_audit_unsafe` helper that no-ops DB writes for the 4 new actions; in-memory `_AUDIT` dict in `incidents/service.py` remains the source of truth for EC-4 verification until Phase 2 batch 4 widens the migration.

Related: [[req_044_us1_seed_pattern]] (US1 decision_signals baseline)
