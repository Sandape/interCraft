/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import {
  DeriveProgress,
  DERIVE_CLIENT_TIMEOUT_MS,
} from "../DeriveProgress";

vi.mock("../api", () => ({
  getDeriveRun: vi.fn(),
}));

import { getDeriveRun } from "../api";

const mockedGet = vi.mocked(getDeriveRun);

function renderProgress(runId = "run-1") {
  return render(
    <MemoryRouter initialEntries={[`/resume/derive/${runId}`]}>
      <Routes>
        <Route path="/resume/derive/:runId" element={<DeriveProgress />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DeriveProgress failure UX (REQ-056)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockedGet.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows failed state with back link", async () => {
    mockedGet.mockResolvedValue({
      run_id: "run-1",
      status: "failed",
      phase: "done",
      progress_pct: 0,
      error_code: "ENQUEUE_FAILED",
      error_message: "派生后台暂不可用",
    } as never);

    renderProgress();
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByTestId("derive-progress-failed")).toBeInTheDocument();
    expect(screen.getByText(/ENQUEUE_FAILED/)).toBeInTheDocument();
  });

  it("shows timeout banner when still running past client timeout", async () => {
    mockedGet.mockResolvedValue({
      run_id: "run-1",
      status: "running",
      phase: "parse_jd",
      progress_pct: 10,
    } as never);

    renderProgress();
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      vi.advanceTimersByTime(DERIVE_CLIENT_TIMEOUT_MS + 100);
    });

    expect(screen.getByTestId("derive-progress-timeout")).toBeInTheDocument();
  });

  it("shows needs_guidance testid", async () => {
    mockedGet.mockResolvedValue({
      run_id: "run-1",
      status: "needs_guidance",
      phase: "calibrate",
      progress_pct: 90,
    } as never);

    renderProgress();
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByTestId("derive-guidance")).toBeInTheDocument();
  });
});
