import { beforeEach, describe, expect, it, vi } from "vitest";
import { defaultResumeDataV2 } from "../../schema/defaults";

const mockUpdateResume = vi.fn();

vi.mock("../../api", () => ({
  updateResume: (...args: unknown[]) => mockUpdateResume(...args),
}));

vi.mock("@/modules/resume/v2/editor/center/toast", () => ({
  fireToast: vi.fn(),
}));

const freshData = () => JSON.parse(JSON.stringify(defaultResumeDataV2));

describe("resume v2 store markdown cutover status", () => {
  beforeEach(async () => {
    vi.useFakeTimers();
    mockUpdateResume.mockReset();
    mockUpdateResume.mockResolvedValue({ id: "r1", version: 1, data: freshData() });
    const { useResumeV2Store } = await import("../index");
    useResumeV2Store.getState().resetFromServer({ id: "r1", data: freshData(), version: 0 });
  });

  it("defaults pagination and legacy conversion metadata", async () => {
    const { useResumeV2Store } = await import("../index");
    const markdown = useResumeV2Store.getState().data.metadata.markdown;

    expect(markdown.paginationState).toBe("idle");
    expect(markdown.pageCount).toBe(1);
    expect(markdown.legacyConversionStatus).toBe("not_needed");
    expect(markdown.legacyConversionWarnings).toEqual([]);
  });

  it("updates pagination state without adding undo history", async () => {
    const { useResumeV2Store } = await import("../index");

    useResumeV2Store.getState().setMarkdownPagination("paginated", 3);

    const state = useResumeV2Store.getState();
    expect(state.data.metadata.markdown.paginationState).toBe("paginated");
    expect(state.data.metadata.markdown.pageCount).toBe(3);
    expect(state.undoStack).toHaveLength(0);
  });

  it("records legacy conversion status and warnings", async () => {
    const { useResumeV2Store } = await import("../index");

    useResumeV2Store
      .getState()
      .setLegacyConversionStatus("warning", ["Custom section was preserved as Markdown."]);

    const markdown = useResumeV2Store.getState().data.metadata.markdown;
    expect(markdown.legacyConversionStatus).toBe("warning");
    expect(markdown.legacyConversionWarnings).toEqual([
      "Custom section was preserved as Markdown.",
    ]);
  });
});
