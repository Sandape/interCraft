import { describe, expect, it } from "vitest";
import { listV3Themes } from "../registry";

describe("Muji v3 themes", () => {
  it("exposes exactly the three scoped themes", () => {
    expect(listV3Themes().map((theme) => [theme.id, theme.name, theme.renderPattern])).toEqual([
      ["muji-default-autumn", "默认（秋风同款）", "dark-header-centered-section"],
      ["muji-minimal-color", "极简色", "minimal-line"],
      ["muji-flat-atmospheric", "平面大气主题", "accent-band"],
    ]);
  });
});
