import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../index";

describe("Muji Markdown safety and fallback", () => {
  it("strips unsafe scripts and reports warnings", () => {
    const result = renderMarkdown(`# X

<script>alert(1)</script>

[bad](javascript:alert(1))

![local](file:///tmp/a.png)
`, { themeId: "muji-default-autumn", lineHeight: 19 });

    expect(result.html.toLowerCase()).not.toContain("<script");
    expect(result.html.toLowerCase()).not.toContain("javascript:");
    expect(result.html.toLowerCase()).not.toContain("file:///tmp/a.png");
    expect(result.warnings.map((w) => w.code)).toContain("unsafe_url");
  });
});
