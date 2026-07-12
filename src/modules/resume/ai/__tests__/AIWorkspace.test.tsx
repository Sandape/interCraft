import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AIWorkspace } from "../AIWorkspace";
import { useAIWorkspaceController } from "../useAIWorkspaceController";

vi.mock("../useAIWorkspaceController", () => ({
  useAIWorkspaceController: vi.fn(),
}));

const mockedController = vi.mocked(useAIWorkspaceController);

function withClient(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function baseController() {
  return {
    mode: "general" as const,
    version: 3,
    isDirty: false,
    saving: false,
    analysis: null,
    analyses: [],
    analysisLoading: false,
    run: null,
    suggestions: [],
    suggestionsLoading: false,
    selected: [],
    setSelected: vi.fn(),
    preview: null,
    previewIsLocallyStale: false,
    lastChangeSetId: null,
    conflictDraft: null,
    comparison: null,
    start: vi.fn(),
    starting: false,
    startError: null,
    retry: vi.fn(),
    cancelRun: vi.fn(),
    cancelling: false,
    cancelError: null,
    regenerateSuggestions: vi.fn(),
    regeneratingSuggestions: false,
    updateSuggestionStatus: vi.fn(),
    updatingSuggestionStatus: false,
    focusSuggestion: vi.fn(),
    confirmSupplement: vi.fn(),
    confirmingSupplement: false,
    supplementError: null,
    submitFeedback: vi.fn(),
    submittingFeedback: false,
    feedbackError: null,
    compareAnalyses: vi.fn(),
    comparingAnalyses: false,
    comparisonError: null,
    previewSelected: vi.fn(),
    previewing: false,
    previewError: null,
    applyPreview: vi.fn(),
    applying: false,
    applyError: null,
    analysisIsLocallyStale: false,
    undoLastApply: vi.fn(),
    undoing: false,
    undoError: null,
    taskId: null,
    canonicalStatus: null,
    availableActions: [],
    milestones: null,
    runtimeLinks: null,
    acceptedTask: null,
  };
}

describe("AIWorkspace", () => {
  beforeEach(() => mockedController.mockReturnValue(baseController()));

  it("keeps general health honest and never shows a job score", () => {
    const controller = baseController();
    mockedController.mockReturnValue(controller);
    render(<AIWorkspace resumeId="r1" resumeKind="standard" onClose={vi.fn()} />);
    expect(screen.getByText("通用体检 · 不展示岗位匹配分")).toBeInTheDocument();
    expect(screen.queryByText("当前证据覆盖 / 100")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "开始真实 AI 分析" }));
    expect(controller.start).toHaveBeenCalledWith(false);
  });

  it("shows job identity, disclaimer and hard blockers", () => {
    const controller = {
      ...baseController(),
      mode: "job_fit" as const,
      analysis: {
        id: "a1",
        resume_id: "r1",
        resume_version: 3,
        mode: "job_fit" as const,
        status: "complete" as const,
        is_stale: false,
        stale_reasons: [],
        overall_score: 68,
        confidence_score: 0.78,
        confidence_band: "medium" as const,
        confidence_reasons: [],
        job_context: {
          job_id: "j1",
          company: "示例公司",
          position: "产品经理",
          jd_hash: "a".repeat(64),
          refreshable: true,
        },
        dimensions: [],
        gaps: [],
        hard_blockers: ["r-hard"],
        disclaimer: "不是 ATS 官方分数，也不预测面试或录用结果。",
        created_at: "2026-07-11T00:00:00Z",
      },
    };
    mockedController.mockReturnValue(controller);
    render(<AIWorkspace resumeId="r1" resumeKind="derived" jobId="j1" onClose={vi.fn()} />);
    expect(screen.getByText("68")).toBeInTheDocument();
    expect(screen.getByText(/示例公司 · 产品经理/)).toBeInTheDocument();
    expect(screen.getByText(/不是 ATS 官方分数/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("硬性要求存在证据缺口");
  });

  it("has an accessible close control", () => {
    const close = vi.fn();
    render(<AIWorkspace resumeId="r1" resumeKind="standard" onClose={close} />);
    fireEvent.click(screen.getByRole("button", { name: "关闭 AI 指导" }));
    expect(close).toHaveBeenCalledOnce();
  });

  it("renders accessible tabs and live recovery state", () => {
    mockedController.mockReturnValue({
      ...baseController(),
      run: {
        run_id: "run-1",
        analysis_id: null,
        status: "running",
        phase: "解析岗位要求",
        progress_percent: 40,
        error: null,
      },
    });
    render(<AIWorkspace resumeId="r1" resumeKind="standard" onClose={vi.fn()} />);

    expect(screen.getByRole("tablist", { name: "AI 指导内容" })).toBeInTheDocument();
    expect(screen.getByTestId("run-recovery")).toHaveTextContent("正在运行");
    expect(screen.getByRole("button", { name: "取消运行" })).toBeInTheDocument();
  });
});
