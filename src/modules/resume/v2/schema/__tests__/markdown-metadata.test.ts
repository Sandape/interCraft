import { describe, expect, it } from "vitest";
import { defaultResumeDataV2 } from "../defaults";
import { resumeDataV2Schema } from "../data";

describe("ResumeDataV2 markdown metadata", () => {
  it("defaults to a Muji-compatible Markdown render state", () => {
    const markdown = defaultResumeDataV2.metadata.markdown;
    expect(markdown.sourceMarkdown).toContain("#");
    expect(markdown.themeId).toBe("muji-default-autumn");
    expect(markdown.manualLineHeight).toBe(19);
    expect(markdown.smartOnePageEnabled).toBe(false);
    expect(markdown.smartLineHeight).toBeNull();
  });

  it("accepts the three scoped themes and line-height presets 12 through 25", () => {
    const themes = ["muji-default-autumn", "muji-minimal-color", "muji-flat-atmospheric"] as const;
    for (const themeId of themes) {
      for (let manualLineHeight = 12; manualLineHeight <= 25; manualLineHeight += 1) {
        const parsed = resumeDataV2Schema.parse({
          ...defaultResumeDataV2,
          metadata: {
            ...defaultResumeDataV2.metadata,
            markdown: {
              ...defaultResumeDataV2.metadata.markdown,
              themeId,
              manualLineHeight,
            },
          },
        });
        expect(parsed.metadata.markdown.themeId).toBe(themeId);
        expect(parsed.metadata.markdown.manualLineHeight).toBe(manualLineHeight);
      }
    }
  });

  it("rejects out-of-scope themes and line-height values", () => {
    expect(() =>
      resumeDataV2Schema.parse({
        ...defaultResumeDataV2,
        metadata: {
          ...defaultResumeDataV2.metadata,
          markdown: {
            ...defaultResumeDataV2.metadata.markdown,
            themeId: "blue",
          },
        },
      }),
    ).toThrow();

    expect(() =>
      resumeDataV2Schema.parse({
        ...defaultResumeDataV2,
        metadata: {
          ...defaultResumeDataV2.metadata,
          markdown: {
            ...defaultResumeDataV2.metadata.markdown,
            manualLineHeight: 26,
          },
        },
      }),
    ).toThrow();
  });
});
