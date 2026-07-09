# REQ-037 Requirement Status

Post-login first-screen performance and dashboard critical-path optimization.

Status date: 2026-06-30

## User Stories

| ID | Requirement | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Login Lands Without Reblocking | planned | - | Fix the confirmed-login to unresolved-session regression while preserving stale-token protection. |
| US2 | Dashboard Renders Progressively | planned | - | Critical shell and primary actions should render before secondary data settles. |
| US3 | First-Screen Data Budget Is Controlled | planned | - | Reduce duplicate or secondary first-screen reads. |
| US4 | Performance Regression Evidence Exists | planned | - | Add before/after timing and automated coverage. |

## Functional Requirements

| ID | Requirement | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | Valid login response makes session ready for first-screen rendering | planned | - | Directly addresses post-login full-screen loading. |
| FR-002 | Background identity refresh does not demote confirmed session to unresolved | planned | - | Must avoid `unknown` state after confirmed login unless invalid. |
| FR-003 | Stale or invalid cold-load tokens remain protected | planned | - | Security behavior must remain intact. |
| FR-004 | Critical first-screen content set is defined | planned | - | Shell, navigation, greeting, primary actions, stable dashboard structure. |
| FR-005 | Secondary dashboard panels load independently | planned | - | Recommendations/history should not block first screen. |
| FR-006 | Secondary panel failure does not block primary use | planned | - | Panel-level fallback required. |
| FR-007 | Duplicate blocking reads are avoided on initial dashboard render | planned | - | Especially repeated domain data for suggestions and dashboard widgets. |
| FR-008 | Broad recommendation lists are deferred, summarized, or reused | planned | - | Keeps suggestion computation off the critical path. |
| FR-009 | Avatar/media loading does not block first-screen actions | planned | - | Avatar should be opportunistic. |
| FR-010 | Login-to-dashboard timings are measurable | planned | - | Shell visible, first content, all panels settled. |
| FR-011 | Automated coverage includes slow identity and slow optional data | planned | - | Prevents regression. |
| FR-012 | Loading states distinguish session, critical content, and secondary panels | planned | - | Avoids misleading full-screen waits. |

## Success Criteria

| ID | Criterion | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | Authenticated shell visible within 1.0s in valid-login validation | planned | - | Synthetic local/staging measurement. |
| SC-002 | No post-login full-screen auth loader beyond 250ms unless invalid | planned | - | Core symptom guard. |
| SC-003 | Dashboard greeting/nav/actions visible within 1.5s | planned | - | Normal local/staging validation. |
| SC-004 | Slow secondary data does not block shell/actions | planned | - | 3s delay scenario. |
| SC-005 | Secondary data failure keeps page usable | planned | - | Panel fallback scenario. |
| SC-006 | Blocking first-screen data reads reduced by 40% or within budget | planned | - | Requires baseline measurement. |
| SC-007 | Stale-token cold-load protection remains secure | planned | - | No protected mount before validation. |
| SC-008 | Before/after browser evidence exists | planned | - | Timing, request count, screenshot/trace. |

