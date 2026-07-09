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

describe("resume v2 store markdown settings", () => {
  beforeEach(async () => {
    vi.useFakeTimers();
    mockUpdateResume.mockReset();
    mockUpdateResume.mockResolvedValue({ id: "r1", version: 1, data: freshData() });
    const { useResumeV2Store } = await import("../index");
    useResumeV2Store.getState().resetFromServer({ id: "r1", data: freshData(), version: 0 });
  });

  it("updates Markdown source and theme without mutating the source on theme change", async () => {
    const { useResumeV2Store } = await import("../index");
    const source = "# 林溪\n\n## 经历\n\n- 一条经历";
    useResumeV2Store.getState().setSourceMarkdown(source);
    useResumeV2Store.getState().setMarkdownTheme("muji-minimal-color");

    const markdown = useResumeV2Store.getState().data.metadata.markdown;
    expect(markdown.sourceMarkdown).toBe(source);
    expect(markdown.themeId).toBe("muji-minimal-color");
  });

  it("persists manual line-height only while smart one-page is off", async () => {
    const { useResumeV2Store } = await import("../index");
    useResumeV2Store.getState().setManualLineHeight(12);
    expect(useResumeV2Store.getState().data.metadata.markdown.manualLineHeight).toBe(12);

    useResumeV2Store.getState().enableSmartOnePage(20, "already-fit");
    useResumeV2Store.getState().setManualLineHeight(25);
    expect(useResumeV2Store.getState().data.metadata.markdown.manualLineHeight).toBe(12);
    expect(useResumeV2Store.getState().getEffectiveLineHeight()).toBe(20);

    useResumeV2Store.getState().disableSmartOnePage();
    expect(useResumeV2Store.getState().data.metadata.markdown.manualLineHeight).toBe(12);
    expect(useResumeV2Store.getState().getEffectiveLineHeight()).toBe(12);
  });
});
