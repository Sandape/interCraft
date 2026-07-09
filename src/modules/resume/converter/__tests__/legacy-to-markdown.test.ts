import { describe, expect, it } from "vitest";
import { convertLegacyResumeToMarkdown } from "../legacy-to-markdown";

describe("legacy structured resume to Markdown conversion", () => {
  it("preserves visible basics, summary, sections, skills, and custom sections", () => {
    const result = convertLegacyResumeToMarkdown({
      basics: {
        name: "Legacy Lin",
        headline: "AI Product Engineer",
        email: "legacy@example.com",
        phone: "13800000000",
        location: "Shanghai",
        website: { label: "Portfolio", url: "https://example.com" },
        customFields: [{ name: "GitHub", value: "https://github.com/legacy" }],
      },
      summary: {
        title: "Summary",
        hidden: false,
        content: "<p>Structured summary.</p>",
      },
      sections: {
        experience: {
          title: "Experience",
          hidden: false,
          items: [
            {
              company: "Old Resume Co",
              position: "Engineer",
              date: "2021 - 2024",
              summary: "Built old editor workflows.",
            },
          ],
        },
        skills: {
          title: "Skills",
          hidden: false,
          items: [{ name: "Markdown", keywords: ["Rendering", "Pagination"] }],
        },
      },
      customSections: [
        {
          title: "Impact",
          hidden: false,
          items: [{ name: "Migration", description: "Preserved legacy content." }],
        },
      ],
    });

    expect(result.convertedMarkdown).toContain("# Legacy Lin");
    expect(result.convertedMarkdown).toContain("icon:email legacy@example.com");
    expect(result.convertedMarkdown).toContain("Structured summary.");
    expect(result.convertedMarkdown).toContain("Old Resume Co");
    expect(result.convertedMarkdown).toContain("Markdown");
    expect(result.convertedMarkdown).toContain("Impact");
    expect(result.status).toBe("converted");
  });

  it("does not duplicate content when Markdown already exists", () => {
    const result = convertLegacyResumeToMarkdown({
      metadata: {
        markdown: {
          sourceMarkdown: "# Existing Markdown",
        },
      },
      basics: { name: "Legacy Lin" },
    });

    expect(result.convertedMarkdown).toBe("# Existing Markdown");
    expect(result.status).toBe("not_needed");
  });
});
