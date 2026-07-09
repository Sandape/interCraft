# Contract: Resume Derive Agent (product/tech boundary)

**Graph id**: `resume_derive`  
**Location (planned)**: `backend/app/agents/graphs/resume_derive.py`

## Inputs

| Field | Required | Source |
|-------|----------|--------|
| `root_resume` | yes | `resumes_v2` kind=root `data` + `version` |
| `job` | yes | `jobs` row |
| `jd_text` | yes | `jobs.requirements_md` |
| `target_page_count` | yes | 1 / 2 / 3 |
| `template_id` | yes | user or system default |
| `user_supplements` | no | confirmed Q&A |
| `prior_suggestion_actions` | no | accept/dismiss history |
| `calibrate_hints` | no | from guidance continue |

## Node pipeline (logical)

```text
parse_jd
  → select_materials          # only root + supplements
  → draft_derived             # structured MD / ResumeDataV2
  → validate_sources          # drop unreferenced claims
  → render_measure            # HTML pagination estimate
  → calibrate_pages           # loop ≤ 5; compress | expand
  → seed_suggestions          # direct | needs_supplement | do_not_write
  → END | NEEDS_GUIDANCE | FAIL
```

Editor-time suggestion refresh may run a lighter subgraph: `analyze_fit → suggest` with same source validator.

## Outputs

| Artifact | Description |
|----------|-------------|
| `jd_parse` | Structured JD + priority tiers + keyword buckets |
| `selection_plan` | Included / compressed / hidden materials + reasons |
| `derived_data` | Resume body for new derived row |
| `unused_materials` | Parked content |
| `page_report` | target, measured, rounds, strategy steps |
| `suggestions[]` | Graded actionable items |
| `supplement_questions[]` | Concrete questions, not vague prompts |
| `takeaway_notes` | Human-readable「为什么这么写」 |
| `risk_flags[]` | stuffing, evidence gap, ATS format risks |

## Hard constraints (MUST)

1. No body text claim without `source_refs` pointing at root or confirmed supplement.
2. Never copy JD requirement text as user accomplishment without evidence.
3. Never invent metrics, employers, projects, or skill proficiency.
4. Expression rewrite allowed; fact mutation not allowed.
5. Unconfirmed supplements stay in `pendingClaims` — block export.
6. If measured pages ≠ target after max rounds → `needs_guidance`, not silent wrong-page success.
7. Applying suggestions in editor requires explicit user confirm (HITL); no silent overwrite of manual edits.

## HITL

- Derive run itself is async without mid-run interrupt (progress only).
- Suggestion **apply** uses confirm API (preview → apply), analogous to M16 interrupt semantics but via REST, not necessarily LangGraph interrupt for MVP editor path.

## Eval fixtures (Test-First)

Minimum fixture set under `backend/tests/agents/resume_derive/`:

1. JD emphasizes skill X; root has X → X appears; provenance present.
2. JD emphasizes skill Y; root lacks Y → body must not claim Y; question emitted.
3. Target 1 page with long root → success only if measured==1 or needs_guidance (never succeed with pages>1).
4. Keyword stuffing attempt in model output → validator/risk flag strips or blocks.
