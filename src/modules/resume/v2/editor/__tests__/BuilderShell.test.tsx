import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defaultResumeDataV2 } from "../../schema/defaults";
import { BuilderShell } from "../BuilderShell";

vi.mock("../../api", () => ({
  duplicateResume: vi.fn(),
  renderExport: vi.fn(),
  updateResume: vi.fn(),
}));

vi.mock("../center/toast", () => ({
  fireToast: vi.fn(),
}));

const data = () => JSON.parse(JSON.stringify(defaultResumeDataV2));

describe("BuilderShell Markdown-only contract", () => {
  beforeEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the Markdown editor as the active editing surface", () => {
    render(<BuilderShell data={data()} onChange={() => {}} resumeId="r-1" />);

    expect(screen.getByTestId("v2-editor")).toHaveAttribute("data-markdown-cutover", "true");
    expect(screen.getByTestId("markdown-source-editor")).toBeInTheDocument();
    expect(screen.getByTestId("markdown-preview-page")).toBeInTheDocument();
    expect(screen.getByTestId("export-pdf-option")).toBeInTheDocument();
  });

  it("does not expose legacy panels, template gallery, or dock controls", () => {
    render(<BuilderShell data={data()} onChange={() => {}} resumeId="r-1" />);

    expect(screen.queryByTestId("panel-left")).not.toBeInTheDocument();
    expect(screen.queryByTestId("panel-right")).not.toBeInTheDocument();
    expect(screen.queryByTestId("right-tab-host")).not.toBeInTheDocument();
    expect(screen.queryByTestId("template-gallery-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("dock")).not.toBeInTheDocument();
  });
});
