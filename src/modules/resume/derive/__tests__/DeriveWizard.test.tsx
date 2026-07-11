import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DeriveWizard } from "../DeriveWizard";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  startDerive: vi.fn(),
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
  startDerive: mocks.startDerive,
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
    mocks.startDerive.mockReset();
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

  it("uses the editor's three themes and sends the selected theme", async () => {
    mocks.jobs = [
      {
        id: "job-with-jd",
        company: "Theme Corp",
        position: "Designer",
        requirements_md: "A complete JD",
      },
    ];
    mocks.startDerive.mockResolvedValue({ run_id: "run-1", status: "pending" });
    renderWizard();

    fireEvent.change(screen.getByTestId("derive-job-select"), {
      target: { value: "job-with-jd" },
    });
    const themeSelect = screen.getByTestId("derive-theme-select");
    expect(themeSelect).toHaveTextContent("默认（秋风同款）");
    expect(themeSelect).toHaveTextContent("极简色");
    expect(themeSelect).toHaveTextContent("平面大气主题");
    expect(themeSelect).not.toHaveTextContent("Pikachu");

    fireEvent.change(themeSelect, { target: { value: "muji-flat-atmospheric" } });
    fireEvent.click(screen.getByTestId("derive-start-btn"));

    await waitFor(() => {
      expect(mocks.startDerive).toHaveBeenCalledWith({
        job_id: "job-with-jd",
        target_page_count: 1,
        template_id: "muji-flat-atmospheric",
      });
    });
  });
});
