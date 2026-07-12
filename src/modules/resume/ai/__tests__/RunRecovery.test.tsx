import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunRecovery } from "../RunRecovery";
import type { AnalysisRunStatus } from "../api";

function run(overrides: Partial<AnalysisRunStatus> = {}): AnalysisRunStatus {
  return {
    run_id: "run-1",
    analysis_id: null,
    status: "running",
    phase: "生成建议",
    progress_percent: 42,
    components: { parse: "succeeded", suggest: "running" },
    error: null,
    ...overrides,
  };
}

describe("RunRecovery", () => {
  it("shows running state and supports cancel", () => {
    const onCancel = vi.fn();
    render(<RunRecovery run={run()} onRetry={vi.fn()} onCancel={onCancel} />);

    expect(screen.getByTestId("run-recovery")).toHaveTextContent("正在运行");
    expect(screen.getByLabelText("运行进度 42%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "取消运行" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("shows failed state without fake success and supports retry", () => {
    const onRetry = vi.fn();
    render(
      <RunRecovery
        run={run({ status: "failed", error: { code: "MODEL_UNAVAILABLE", message: "模型不可用", retryable: true } })}
        onRetry={onRetry}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("没有生成假成功结果");
    expect(screen.getByText("模型不可用")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试真实 AI" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
