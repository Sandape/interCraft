import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RootResumeCard } from "../RootResumeCard";

const getRootResumeMock = vi.fn();
const createRootResumeMock = vi.fn();

vi.mock("../api", () => ({
  getRootResume: (...args: unknown[]) => getRootResumeMock(...args),
  createRootResume: (...args: unknown[]) => createRootResumeMock(...args),
  promoteToRoot: vi.fn(),
}));

function renderCard() {
  return render(
    <MemoryRouter>
      <RootResumeCard />
    </MemoryRouter>,
  );
}

describe("RootResumeCard", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows empty state when root resume returns 404", async () => {
    getRootResumeMock.mockRejectedValue({ status: 404 });

    renderCard();

    await waitFor(() => {
      expect(screen.getByTestId("root-resume-empty")).toBeInTheDocument();
    });
    expect(screen.getByTestId("create-root-btn")).toBeInTheDocument();
    expect(screen.queryByTestId("root-resume-card")).not.toBeInTheDocument();
  });

  it("shows root card when root resume exists", async () => {
    getRootResumeMock.mockResolvedValue({
      id: "root-1",
      name: "根简历（职业素材库）",
      version: 3,
      data: { metadata: {} },
    });

    renderCard();

    await waitFor(() => {
      expect(screen.getByTestId("root-resume-card")).toBeInTheDocument();
    });
    expect(screen.getByText("根简历（职业素材库）")).toBeInTheDocument();
    expect(screen.queryByTestId("root-resume-empty")).not.toBeInTheDocument();
    expect(screen.queryByTestId("create-root-btn")).not.toBeInTheDocument();
  });

  it("creates root resume from empty state CTA", async () => {
    getRootResumeMock.mockRejectedValue({ status: 404 });
    createRootResumeMock.mockResolvedValue({
      id: "root-new",
      name: "根简历（职业素材库）",
      version: 1,
      data: { metadata: {} },
    });

    renderCard();
    await waitFor(() => {
      expect(screen.getByTestId("create-root-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("create-root-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("root-resume-card")).toBeInTheDocument();
    });
    expect(createRootResumeMock).toHaveBeenCalled();
  });
});
