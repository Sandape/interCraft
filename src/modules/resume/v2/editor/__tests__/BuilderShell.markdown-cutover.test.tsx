import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

describe("BuilderShell regression guard for retired controls", () => {
  it("keeps legacy structured controls absent from the cutover editor", () => {
    render(
      <BuilderShell
        data={JSON.parse(JSON.stringify(defaultResumeDataV2))}
        onChange={() => {}}
        resumeId="r-cutover"
      />,
    );

    expect(screen.getByTestId("markdown-source-editor")).toBeVisible();
    expect(screen.queryByTestId("left-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("preview-stage")).not.toBeInTheDocument();
    expect(screen.queryByTestId("open-template-gallery")).not.toBeInTheDocument();
  });
});
