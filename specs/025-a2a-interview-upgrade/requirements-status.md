# 025 — A2A Interview Upgrade: Requirement Status

Status tracking for feature 025. Implementation complete as of 2026-06-23.

## User Stories

| Requirement | Summary | Priority | Status | Evidence | Notes |
|---|---|---|---|---|---|
| US1 | Tavily Search Tool — LangGraph `@tool` with graceful degradation | P1 | done | `backend/app/agents/tools/tavily_search.py`, `backend/app/agents/tools/tavily_client_mock.py` | — |
| US2 | Interview Plan Data Model — JSONB columns + Pydantic models | P1 | done | Migration `0016_025_interview_plan.py`, `backend/app/agents/interview/schemas.py` | — |
| US3 | Planner Context Reading — resume + JD from existing modules | P1 | done | `backend/app/agents/interview/nodes/planner_context.py` | — |
| US4 | Tavily Search for Interview Info — 3-dimension search | P1 | done | `backend/app/agents/interview/nodes/planner_search.py` | — |
| US5 | Generate Interview Plan — LLM call + structured output | P1 | done | `backend/app/agents/interview/nodes/planner_generate.py`, `backend/app/agents/interview/prompts/planner.md` | — |
| US6 | Supervisor Graph Routing — A2A via Command(goto=...) | P1 | done | `backend/app/agents/interview/graph.py` (Supervisor upgrade) | — |
| US7 | Plan Persistence & API — DB save + GET endpoints | P2 | done | `backend/app/modules/interviews/service.py` (T022, T023) | — |
| US8 | Frontend Interview Plan Display — Collapsible plan panel in InterviewLive | P2 | done | `src/pages/InterviewLive.tsx` (plan toggle + focus areas) | — |
| US9 | Frontend Report Plan Display — Plan section in InterviewReport | P2 | done | `src/pages/InterviewReport.tsx` (plan + web research display) | — |
| US10 | MockTavilyClient — Deterministic mock gated on TAVILY_MOCK_MODE | P1 | done | `backend/app/agents/tools/tavily_client_mock.py`, `tests/e2e/round-2/fixtures/tavily-mock.ts` | — |
| US11 | Unit + Integration Tests — Backend test coverage | P1 | done | Unit: `tests/unit/test_tavily_tool.py`, `tests/unit/test_tavily_mock.py`. Integration: `test_planner.py`, `test_interview_supervisor.py` | — |
| US12 | E2E Tests — Full flow + backward compatibility | P2 | done | `tests/e2e/interview-a2a-planner.spec.ts` (HAPPY-02, BC-01) | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | tavily-python dependency in pyproject.toml | done | `backend/pyproject.toml` | — |
| FR-002 | TAVILY_API_KEY + TAVILY_MOCK_MODE config settings | done | `backend/app/core/config.py` | — |
| FR-003 | InterviewPlan Pydantic model | done | `backend/app/agents/interview/schemas.py` | — |
| FR-004 | FocusArea Pydantic model | done | `backend/app/agents/interview/schemas.py` | — |
| FR-005 | WebResearch Pydantic model | done | `backend/app/agents/interview/schemas.py` | — |
| FR-006 | SearchResult Pydantic model | done | `backend/app/agents/interview/schemas.py` | — |
| FR-007 | Alembic migration adding interview_plan JSONB + web_research JSONB | done | `backend/migrations/versions/0016_025_interview_plan.py` | — |
| FR-008 | TavilySearchTool with graceful degradation (timeout/4xx/5xx → empty) | done | `backend/app/agents/tools/tavily_search.py` | — |
| FR-009 | InterviewGraphState extended with interview_plan + web_research | done | `backend/app/agents/interview/state.py` | — |
| FR-010 | ORM columns added to InterviewSession model | done | `backend/app/modules/interviews/models.py` | — |
| FR-011 | interview_plan + web_research in InterviewSessionOut schema | done | `backend/app/modules/interviews/schemas.py` | — |
| FR-012 | planner_context node (resume + JD reading) | done | `backend/app/agents/interview/nodes/planner_context.py` | — |
| FR-013 | planner_search node (3-dimension Tavily search) | done | `backend/app/agents/interview/nodes/planner_search.py` | — |
| FR-014 | planner_generate node (LLM call → InterviewPlan) | done | `backend/app/agents/interview/nodes/planner_generate.py` | — |
| FR-015 | Planner system prompt (planner.md) | done | `backend/app/agents/interview/prompts/planner.md` | — |
| FR-016 | planner_subgraph assembly (context → search → generate) | done | `backend/app/agents/interview/planner_graph.py` | — |
| FR-017 | Supervisor graph — planner_subgraph + Command(goto=interviewer) | done | `backend/app/agents/interview/graph.py` | — |
| FR-018 | Interviewer prompt updated with plan context injection | done | `backend/app/agents/interview/prompts/interviewer.md` | — |
| FR-019 | intake_node forwards interview_plan to interviewer state | done | `backend/app/agents/interview/nodes/intake.py` | — |
| FR-020 | Cached plan skip — skip Tavily when plan already exists | done | `backend/app/agents/interview/nodes/planner_search.py` | — |
| FR-021 | Persist interview_plan + web_research after planner completes | done | `backend/app/modules/interviews/service.py` (T022) | — |
| FR-022 | Expose interview_plan in GET session + GET report API responses | done | `backend/app/modules/interviews/service.py` (T023) | — |
| FR-023 | WS interview handler propagates plan fields on reconnect | done | `backend/app/api/v1/ws/interview.py` (T024) | — |
| FR-024 | Frontend: interview_plan + web_research type definitions | done | `src/repositories/interviewSessionRepo.ts` | — |
| FR-025 | Frontend: collapsible plan panel in InterviewLive | done | `src/pages/InterviewLive.tsx` | — |
| FR-026 | Frontend: plan display section in InterviewReport | done | `src/pages/InterviewReport.tsx` | — |
| FR-027 | Frontend: handle empty/null plan gracefully | done | Both `InterviewLive.tsx` + `InterviewReport.tsx` guard on null | — |
| FR-028 | Unit tests for TavilySearchTool (mock SDK, timeout, 4xx/5xx) | done | `backend/tests/unit/test_tavily_tool.py` | — |
| FR-029 | Unit tests for MockTavilyClient (scenario loading, empty fallback, env toggle) | done | `backend/tests/unit/test_tavily_mock.py` | — |
| FR-030 | Integration tests for Planner (resume+JD → plan, missing resume fallback) | done | `backend/tests/integration/test_planner.py` | — |
| FR-031 | Integration tests for Supervisor routing (plan→interviewer, skip cached) | done | `backend/tests/integration/test_interview_supervisor.py` | — |
| FR-032 | E2E fixture: Tavily scenario file | done | `tests/e2e/round-2/fixtures/tavily-scenarios/active.json`, `tests/e2e/round-2/fixtures/tavily-mock.ts` | — |
| FR-033 | E2E full flow test (HAPPY-02) | done | `tests/e2e/interview-a2a-planner.spec.ts` | — |
| FR-034 | E2E backward compatibility test (BC-01) | done | `tests/e2e/interview-a2a-planner.spec.ts` | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-01 | Tavily search tool callable and returns structured results | done | Unit test `test_tavily_tool.py`; mock test `test_tavily_mock.py` | — |
| SC-02 | Planner completes search+generation within 15s | done | Integration test `test_planner.py` (mock Tavily, no network) | — |
| SC-03 | A2A routing Planner→Interviewer passes state correctly | done | Integration test `test_interview_supervisor.py` | — |
| SC-04 | Interview plan visible on interview page and report page | done | `tests/e2e/interview-a2a-planner.spec.ts` HAPPY-02 | Includes frontend E2E check for plan toggle + report plan field |
| SC-05 | No Tavily results → system still completes interview | done | `_empty_plan` fallback in `planner_generate.py`; `EMPTY_SEARCH_SCENARIO` in mock | — |
| SC-06 | Old records without plan are backward compatible | done | `tests/e2e/interview-a2a-planner.spec.ts` BC-01 | Both session GET and report GET return null plan, no crash |
