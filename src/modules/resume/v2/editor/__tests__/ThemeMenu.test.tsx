import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ThemeMenu } from "../controls/ThemeMenu";

describe("ThemeMenu", () => {
  it("renders exactly three scoped Muji themes", () => {
    const onChange = vi.fn();
    render(<ThemeMenu value="muji-default-autumn" onChange={onChange} />);

    const options = Array.from(screen.getByTestId("theme-menu").querySelectorAll("option"));
    expect(options.map((option) => option.textContent)).toEqual(["默认（秋风同款）", "极简色", "平面大气主题"]);

    fireEvent.change(screen.getByTestId("theme-menu"), { target: { value: "muji-flat-atmospheric" } });
    expect(onChange).toHaveBeenCalledWith("muji-flat-atmospheric");
  });
});
