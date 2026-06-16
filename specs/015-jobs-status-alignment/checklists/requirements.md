# Specification Quality Checklist: Jobs Status Alignment

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-16
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Clarifications resolved in this session:
  - Tabs = all real backend statuses (applied/test/oa/hr/offer/rejected/withdrawn) + an "all" tab.
  - 409 handling = inline error row with an explicit `重试` button (`data-testid="job-row-retry"`), no silent rollback.
  - Advance action = popover status menu driven by `JOB_TRANSITIONS`; terminal moves (rejected/withdrawn) prompt a confirm modal.
  - Source of truth = new `GET /api/v1/jobs/transitions` endpoint, fetched once per session, used to derive tab set, row menu, and "Active" composition.
  - Stats = 5 tiles in lifecycle order: 总申请 / 进行中 (Active = applied+test+oa+hr) / Offer / 已拒绝 / 已撤回.
  - Row-leaves-tab: on a successful status change, the row is removed from the current filter tab; on 409, the row stays in the current tab with its previous status.
- Scope is narrow: one backend endpoint addition + Jobs page UI changes; other pages untouched.
