import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StaleRootBanner } from "../StaleRootBanner";

describe("StaleRootBanner", () => {
  it("shows banner when root snapshot is stale", () => {
    render(<StaleRootBanner stale onRegenerate={vi.fn()} />);
    expect(screen.getByTestId("stale-root-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/根简历已更新。当前派生仍是旧快照/),
    ).toBeInTheDocument();
  });

  it("renders null when not stale", () => {
    const { container } = render(<StaleRootBanner stale={false} />);
    expect(screen.queryByTestId("stale-root-banner")).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });
});
