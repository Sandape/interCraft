import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ApiError } from "@/api/errors";
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
  const useResumeV2Store = (selector: (state: typeof storeState & {
    flushSave: typeof mocks.flushSave;
    resetFromServer: typeof mocks.resetFromServer;
    focusAIAnchor: typeof mocks.focusAIAnchor;
  }) => unknown) =>
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
    title: "重写项目描述",
    explanation: "强化表达。",
    anchor: { node_id: "exp-1", start: 0, end: 8, context_checksum: "abc" },
    status: "open",
    source_refs: [],
    ...overrides,
  };
}

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return function TestWrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useAIWorkspaceController", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storeState.version = 3;
    storeState.isDirty = false;
    storeState.saving = false;
    storeState.lastEditAt = 100;
    storeState.data = { metadata: { markdown: { sourceMarkdown: "local draft" } } };
    mocks.flushSave.mockResolvedValue(undefined);
    mocks.listAnalyses.mockResolvedValue([analysis()]);
    mocks.listSuggestions.mockResolvedValue([suggestion()]);
    mocks.startAnalysis.mockResolvedValue({ run_id: "run-1", status: "queued", status_url: "/runs/run-1" });
    mocks.getAnalysisRun.mockResolvedValue({ run_id: "run-1", status: "queued", phase: "queued" });
    mocks.previewSuggestions.mockResolvedValue({
      preview_token: "token-1",
      base_resume_version: 3,
      compatible: ["s1"],
      conflicts: [],
      blocked: [],
      diff: { before_markdown: "before", after_markdown: "after", patches: [] },
      page_impact: { status: "unchanged", export_gate_stale: false },
    });
  });

  it("flushes autosave before starting analysis", async () => {
    const { result } = renderHook(
      () => useAIWorkspaceController({ resumeId: "r1", resumeKind: "derived", jobId: "j1" }),
      { wrapper: wrapper() },
    );

    await act(async () => result.current.start(false));

    await waitFor(() => expect(mocks.startAnalysis).toHaveBeenCalled());
    expect(mocks.flushSave).toHaveBeenCalled();
    expect(mocks.flushSave.mock.invocationCallOrder[0]).toBeLessThan(mocks.startAnalysis.mock.invocationCallOrder[0]);
    expect(mocks.startAnalysis).toHaveBeenCalledWith("r1", expect.objectContaining({ client_version: 3, mode: "job_fit" }));
  });

  it("detects local analysis staleness from resume version", async () => {
    mocks.listAnalyses.mockResolvedValue([analysis({ resume_version: 2 })]);
    const { result } = renderHook(
      () => useAIWorkspaceController({ resumeId: "r1", resumeKind: "derived", jobId: "j1" }),
      { wrapper: wrapper() },
    );

    await waitFor(() => expect(result.current.analysis?.id).toBe("a1"));
    expect(result.current.analysisIsLocallyStale).toBe(true);
  });

  it("preserves local draft and resets from server on 409 apply conflict", async () => {
    mocks.applySuggestions.mockRejectedValue(
      new ApiError({
        status: 409,
        code: "VERSION_CONFLICT",
        message: "版本冲突",
        requestId: "req-1",
        details: { latest_data: { metadata: { markdown: { sourceMarkdown: "server" } } }, latest_version: 4 },
      }),
    );
    const { result } = renderHook(
      () => useAIWorkspaceController({ resumeId: "r1", resumeKind: "derived", jobId: "j1" }),
      { wrapper: wrapper() },
    );

    await waitFor(() => expect(result.current.suggestions.length).toBe(1));
    act(() => result.current.setSelected(["s1"]));
    await act(async () => result.current.previewSelected());
    await waitFor(() => expect(result.current.preview?.preview_token).toBe("token-1"));

    await act(async () => result.current.applyPreview());

    await waitFor(() => expect(mocks.resetFromServer).toHaveBeenCalledWith({
      id: "r1",
      version: 4,
      data: { metadata: { markdown: { sourceMarkdown: "server" } } },
    }));
    expect(result.current.conflictDraft).toEqual({ metadata: { markdown: { sourceMarkdown: "local draft" } } });
  });
});
