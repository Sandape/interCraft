import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DeriveWizard } from "../DeriveWizard";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  jobs: [] as Array<{
    id: string;
    company: string;
    position: string;
    requirements_md?: string;
  }>,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("@/hooks/queries/useJobs", () => ({
  useJobs: () => ({
    data: { data: mocks.jobs, next_cursor: null, has_more: false },
    isLoading: false,
    isFetching: false,
  }),
}));

vi.mock("../api", () => ({
  startDerive: vi.fn(),
}));

function renderWizard(open = true) {
  const onClose = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <DeriveWizard open={open} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { ...utils, onClose };
}

describe("DeriveWizard", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.jobs = [
      {
        id: "job-no-jd",
        company: "NoJD Corp",
        position: "Engineer",
        requirements_md: "",
      },
    ];
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("blocks derive when selected job has no JD", async () => {
    renderWizard();

    expect(screen.getByTestId("derive-wizard")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("derive-job-select"), {
      target: { value: "job-no-jd" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("derive-no-jd")).toBeInTheDocument();
    });
    expect(screen.getByTestId("derive-start-btn")).toBeDisabled();
  });

  it("renders nothing when closed", () => {
    renderWizard(false);
    expect(screen.queryByTestId("derive-wizard")).not.toBeInTheDocument();
  });
});
