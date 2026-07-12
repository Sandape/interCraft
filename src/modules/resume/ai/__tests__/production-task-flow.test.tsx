/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useAIWorkspaceController } from "../useAIWorkspaceController";
import type { ResumeAnalysis, ResumeSuggestion } from "../types";

const mocks = vi.hoisted(() => ({
  startAnalysis: vi.fn(),
  getAnalysisRun: vi.fn(),
  listAnalyses: vi.fn(),
  listSuggestions: vi.fn(),
  previewSuggestions: vi.fn(),
  applySuggestions: vi.fn(),
  undoChangeSet: vi.fn(),
  cancelRun: vi.fn(),
  regenerateSuggestions: vi.fn(),
  updateSuggestionStatus: vi.fn(),
  submitFeedback: vi.fn(),
  compareAnalyses: vi.fn(),
  confirmSupplementFact: vi.fn(),
  flushSave: vi.fn(),
  resetFromServer: vi.fn(),
  focusAIAnchor: vi.fn(),
}));

const storeState = vi.hoisted(() => ({
  id: "r1",
  version: 3,
  isDirty: false,
  saving: false,
  lastEditAt: 100,
  data: { metadata: { markdown: { sourceMarkdown: "local draft" } } },
}));

vi.mock("../api", () => ({
  startAnalysis: mocks.startAnalysis,
  getAnalysisRun: mocks.getAnalysisRun,
  listAnalyses: mocks.listAnalyses,
  listSuggestions: mocks.listSuggestions,
  previewSuggestions: mocks.previewSuggestions,
  applySuggestions: mocks.applySuggestions,
  undoChangeSet: mocks.undoChangeSet,
  cancelRun: mocks.cancelRun,
  regenerateSuggestions: mocks.regenerateSuggestions,
  updateSuggestionStatus: mocks.updateSuggestionStatus,
  submitFeedback: mocks.submitFeedback,
  compareAnalyses: mocks.compareAnalyses,
  confirmSupplementFact: mocks.confirmSupplementFact,
}));

vi.mock("@/modules/resume/v2/store", () => {
  const useResumeV2Store = (
    selector: (state: typeof storeState & {
      flushSave: typeof mocks.flushSave;
      resetFromServer: typeof mocks.resetFromServer;
      focusAIAnchor: typeof mocks.focusAIAnchor;
    }) => unknown,
  ) =>
    selector({
      ...storeState,
      flushSave: mocks.flushSave,
      resetFromServer: mocks.resetFromServer,
      focusAIAnchor: mocks.focusAIAnchor,
    });
  useResumeV2Store.getState = () => ({
    ...storeState,
    flushSave: mocks.flushSave,
    resetFromServer: mocks.resetFromServer,
    focusAIAnchor: mocks.focusAIAnchor,
  });
  return { useResumeV2Store };
});

function analysis(overrides: Partial<ResumeAnalysis> = {}): ResumeAnalysis {
  return {
    id: "a1",
    resume_id: "r1",
    resume_version: 3,
    mode: "job_fit",
    status: "complete",
    is_stale: false,
    stale_reasons: [],
    overall_score: 72,
    confidence_score: 0.8,
    confidence_band: "high",
    confidence_reasons: [],
    job_context: null,
    dimensions: [],
    gaps: [],
    hard_blockers: [],
    disclaimer: "不是 ATS 分数。",
    created_at: "2026-07-11T00:00:00Z",
    ...overrides,
  };
}

function suggestion(overrides: Partial<ResumeSuggestion> = {}): ResumeSuggestion {
  return {
    id: "s1",
    analysis_id: "a1",
    base_resume_version: 3,
    kind: "rewrite",
    action_mode: "direct",
    priority: "high",
    title: "Tighten summary",
    explanation: "Be specific",
    anchor: { node_id: "summary", start: 0, end: 4, context_checksum: "x" },
    source_refs: [
      {
        source_id: "src1",
        source_type: "current_resume",
        anchor: "summary",
        excerpt: "led team",
        content_hash: "hash1234",
      },
    ],
    page_impact: { status: "may_expand", estimated_delta_lines: 2, export_gate_stale: true },
    status: "open",
    ...overrides,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("production-task-flow (REQ-061 T061)", () => {
  beforeEach(() => {
    Object.values(mocks).forEach((fn) => fn.mockReset());
    storeState.version = 3;
    storeState.isDirty = false;
    storeState.saving = false;
    storeState.lastEditAt = 100;
    mocks.flushSave.mockResolvedValue(undefined);
    mocks.listAnalyses.mockResolvedValue([analysis()]);
    mocks.listSuggestions.mockResolvedValue([
      suggestion(),
      suggestion({
        id: "s2",
        action_mode: "needs_supplement",
        title: "Add metric",
        source_refs: [
          {
            source_id: "src2",
            source_type: "root_resume",
            anchor: "exp.0",
            excerpt: null,
            content_hash: "hash5678",
          },
        ],
        page_impact: { status: "needs_measurement", export_gate_stale: true },
      }),
    ]);
  });

  it("exposes canonical task state and runtime links from start/status", async () => {
    mocks.startAnalysis.mockResolvedValue({
      run_id: "run-1",
      analysis_id: "run-1",
      status: "queued",
      status_url: "/api/v1/v2/resume-intelligence/runs/run-1",
      task_id: "task-1",
      canonical_status: "queued",
      available_actions: ["cancel"],
      runtime: {
        task_id: "task-1",
        status_url: "/api/v1/ai-tasks/task-1",
        events_url: "/api/v1/ai-tasks/task-1/events",
      },
      milestones: [
        { code: "analysis", status: "pending" },
        { code: "suggestions", status: "pending" },
      ],
    });
    mocks.getAnalysisRun.mockResolvedValue({
      run_id: "run-1",
      analysis_id: "run-1",
      status: "running",
      phase: "analysis",
      progress_percent: 35,
      canonical_status: "running",
      available_actions: ["cancel"],
      milestones: [
        { code: "analysis", status: "running" },
        { code: "suggestions", status: "pending" },
      ],
      runtime: {
        task_id: "task-1",
        status_url: "/api/v1/ai-tasks/task-1",
        events_url: "/api/v1/ai-tasks/task-1/events",
      },
      error: null,
    });

    const { result } = renderHook(
      () => useAIWorkspaceController({ resumeId: "r1", resumeKind: "derived", jobId: "j1" }),
      { wrapper },
    );

    await act(async () => {
      result.current.start(false);
    });
    await waitFor(() => expect(result.current.taskId).toBe("task-1"));
    expect(result.current.canonicalStatus).toBe("running");
    expect(result.current.runtimeLinks?.status_url).toContain("/api/v1/ai-tasks/");
    expect(result.current.milestones?.map((m) => m.code)).toEqual([
      "analysis",
      "suggestions",
    ]);
    expect(result.current.availableActions).toContain("cancel");
  });

  it("surfaces suggestion source, risk mode, and page impact", async () => {
    const { result } = renderHook(
      () => useAIWorkspaceController({ resumeId: "r1", resumeKind: "derived", jobId: "j1" }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.suggestions.length).toBe(2));
    const direct = result.current.suggestions.find((s) => s.id === "s1")!;
    const risky = result.current.suggestions.find((s) => s.id === "s2")!;
    expect(direct.source_refs[0].source_type).toBe("current_resume");
    expect(direct.page_impact?.status).toBe("may_expand");
    expect(risky.action_mode).toBe("needs_supplement");
  });

  it("handles preview conflict / stale apply and undo evidence", async () => {
    mocks.previewSuggestions.mockResolvedValue({
      preview_token: "tok",
      base_resume_version: 3,
      compatible: ["s1"],
      conflicts: [],
      blocked: [
        {
          suggestion_ids: ["s2"],
          code: "FACTS_REQUIRED",
          message: "needs facts",
        },
      ],
      diff: { before_markdown: "a", after_markdown: "b", patches: [] },
      page_impact: { status: "needs_measurement", export_gate_stale: true },
      evidence: { operation: "preview", base_version: 3 },
    });
    mocks.applySuggestions.mockResolvedValue({
      resume: { id: "r1", version: 4, data: storeState.data },
      change_set_id: "cs1",
      applied_suggestion_ids: ["s1"],
      analysis_stale: true,
      export_gate_stale: true,
      evidence: { operation: "apply", result_version: 4 },
      result_resume_version: 4,
    });
    mocks.undoChangeSet.mockResolvedValue({
      resume: { id: "r1", version: 5, data: storeState.data },
      change_set_id: "cs2",
      applied_suggestion_ids: ["s1"],
      analysis_stale: true,
      export_gate_stale: true,
      evidence: { operation: "undo", result_version: 5 },
      result_resume_version: 5,
    });

    const { result } = renderHook(
      () => useAIWorkspaceController({ resumeId: "r1", resumeKind: "standard" }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.analysis?.id).toBe("a1"));

    act(() => result.current.setSelected(["s1", "s2"]));
    await act(async () => {
      result.current.previewSelected();
    });
    await waitFor(() => expect(result.current.preview?.preview_token).toBe("tok"));
    expect(result.current.preview?.blocked[0].code).toBe("FACTS_REQUIRED");

    await act(async () => {
      result.current.applyPreview();
    });
    await waitFor(() => expect(result.current.lastChangeSetId).toBe("cs1"));
    expect(mocks.resetFromServer).toHaveBeenCalled();

    await act(async () => {
      result.current.undoLastApply();
    });
    await waitFor(() => expect(mocks.undoChangeSet).toHaveBeenCalled());
  });

  it("maps partial milestones onto controller state", async () => {
    mocks.startAnalysis.mockResolvedValue({
      run_id: "run-p",
      status: "queued",
      status_url: "/x",
      task_id: "task-p",
      canonical_status: "queued",
      available_actions: ["cancel"],
      runtime: { task_id: "task-p", status_url: "/api/v1/ai-tasks/task-p", events_url: "/e" },
      milestones: [
        { code: "analysis", status: "pending" },
        { code: "suggestions", status: "pending" },
      ],
    });
    mocks.getAnalysisRun.mockResolvedValue({
      run_id: "run-p",
      analysis_id: "run-p",
      status: "partial",
      phase: "done",
      progress_percent: 50,
      canonical_status: "partially_succeeded",
      available_actions: ["retry_failed_component", "open_result"],
      milestones: [
        { code: "analysis", status: "delivered" },
        { code: "suggestions", status: "failed" },
      ],
      runtime: { task_id: "task-p", status_url: "/api/v1/ai-tasks/task-p", events_url: "/e" },
      error: null,
    });

    const { result } = renderHook(
      () => useAIWorkspaceController({ resumeId: "r1", resumeKind: "standard" }),
      { wrapper },
    );
    await act(async () => {
      result.current.start(false);
    });
    await waitFor(() =>
      expect(result.current.canonicalStatus).toBe("partially_succeeded"),
    );
    expect(result.current.milestones?.find((m) => m.code === "analysis")?.status).toBe(
      "delivered",
    );
    expect(result.current.availableActions).toContain("retry_failed_component");
  });
});
