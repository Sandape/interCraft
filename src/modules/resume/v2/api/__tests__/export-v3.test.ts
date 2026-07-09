import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderExport } from "../index";

const requestMock = vi.fn();

vi.mock("@/api/client", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

describe("v3 export request", () => {
  beforeEach(() => {
    requestMock.mockReset();
    requestMock.mockResolvedValue({ blob: () => Promise.resolve(new Blob(["pdf"])) });
  });

  it("includes current render settings when exporting PDF", async () => {
    await renderExport("r1", "pdf", "<div>html</div>", {
      sourceMarkdown: "# 林溪",
      themeId: "muji-default-autumn",
      lineHeight: 19,
      smartOnePageEnabled: false,
      paginationState: "paginated",
      pageCount: 3,
    });

    expect(requestMock).toHaveBeenCalledWith({
      method: "POST",
      path: "/api/v1/v2/export/render",
      body: {
        resume_id: "r1",
        format: "pdf",
        html: "<div>html</div>",
        source_markdown: "# 林溪",
        theme_id: "muji-default-autumn",
        line_height: 19,
        smart_one_page_enabled: false,
        pagination_state: "paginated",
        preview_page_count: 3,
      },
      raw: true,
    });
  });
});
