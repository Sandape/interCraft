import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LineSpacingControl } from "../controls/LineSpacingControl";

describe("LineSpacingControl", () => {
  it("offers integer presets 12 through 25 and emits selected value", () => {
    const onChange = vi.fn();
    render(<LineSpacingControl value={19} disabled={false} onChange={onChange} />);

    const select = screen.getByTestId("line-spacing-control");
    expect(Array.from(select.querySelectorAll("option")).map((o) => o.value)).toEqual([
      "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25",
    ]);

    fireEvent.change(select, { target: { value: "12" } });
    expect(onChange).toHaveBeenCalledWith(12);
  });
});
