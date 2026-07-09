import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SmartOnePageControl } from "../controls/SmartOnePageControl";

describe("SmartOnePageControl", () => {
  it("shows active status and toggles restore path", () => {
    const onEnable = vi.fn();
    const onDisable = vi.fn();
    render(
      <SmartOnePageControl
        enabled={true}
        status="already-fit"
        selectedLineHeight={20}
        onEnable={onEnable}
        onDisable={onDisable}
      />,
    );

    expect(screen.getByTestId("smart-one-page-status")).toHaveTextContent("已适配一页");
    fireEvent.click(screen.getByTestId("smart-one-page-toggle"));
    expect(onDisable).toHaveBeenCalled();
  });

  it("reports infeasible state without implying content deletion", () => {
    render(
      <SmartOnePageControl
        enabled={true}
        status="infeasible"
        selectedLineHeight={null}
        onEnable={vi.fn()}
        onDisable={vi.fn()}
      />,
    );

    expect(screen.getByTestId("smart-one-page-status")).toHaveTextContent("无法压缩到一页");
  });
});
