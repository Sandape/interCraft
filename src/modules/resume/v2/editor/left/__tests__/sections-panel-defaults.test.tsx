// REQ-RESUME-FIX-7a — SectionsPanel default-title fallback.
//
// L012 lesson (cycle 4 new): i18n REQ 验收必须 E2E 走真实渲染，不能只验
// bundle 形状。FIX-7 仅靠 zhCN namespace shape + dialog 文件 grep 通过了
// "ship-ready" 判定，但 E2E 截图发现 SectionsPanel 12/14 rows 仍显英文。
// 根因：defaults.ts 把 English literal 写进了 section.title，shadow 了
// SectionsPanel.tsx:140 的 `SECTION_LABELS[id]` 兜底链。本测试覆盖：
//
//   1. defaults.ts: `defaultResumeDataV2.sections.{id}.title === ""`（数据形状）
//   2. SectionsPanel 渲染 SectionRow 时，使用 zhCN.resume.sectionsPanel[id]
//      中文兜底（DOM 真实渲染）
//   3. summary.title 默认 ""（SectionRenderer.tsx:23 兜底链生效）
//
// 不要修改本测试用例本身而不更新 defaults.ts 或 SectionsPanel.tsx ——
// 本测试是 REQ-RESUME-FIX-7a 验收红线。

import { describe, it, expect, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";
import React from "react";
import { zhCN } from "@/lib/i18n/zh-CN";

afterEach(() => cleanup());

const SECTION_KEYS = [
  "profiles",
  "experience",
  "education",
  "projects",
  "skills",
  "languages",
  "interests",
  "awards",
  "certifications",
  "publications",
  "volunteer",
  "references",
] as const;

describe("REQ-RESUME-FIX-7a — defaults.ts title fallback contract", () => {
  it("every section default title is empty string ('')", async () => {
    const { defaultResumeDataV2 } = await import("../../../schema/defaults");
    for (const key of SECTION_KEYS) {
      expect(
        defaultResumeDataV2.sections[key].title,
        `sections.${key}.title must be '' so SECTION_LABELS[id] fallback fires`,
      ).toBe("");
    }
  });

  it("summary default title is empty string ('')", async () => {
    const { defaultResumeDataV2 } = await import("../../../schema/defaults");
    expect(defaultResumeDataV2.summary.title).toBe("");
  });

  it("sections.profiles carries the expected icon (non-regression on icon defaults)", async () => {
    // Icon is a separate field — sanity-check we didn't accidentally
    // clobber it while fixing the title.
    const { defaultResumeDataV2 } = await import("../../../schema/defaults");
    expect(defaultResumeDataV2.sections.profiles.icon).toBe("user");
    expect(defaultResumeDataV2.sections.experience.icon).toBe("briefcase");
    expect(defaultResumeDataV2.sections.education.icon).toBe("graduation-cap");
  });
});

describe("REQ-RESUME-FIX-7a — SectionsPanel renders zh-CN fallback label", () => {
  beforeEach(async () => {
    const DialogHostMod = await import("../../dialogs/DialogHost");
    const storeMod = await import("../../../store");
    const defaultsMod = await import("../../../schema/defaults");
    DialogHostMod.useDialogStore.setState({ active: null });
    storeMod.useResumeV2Store.setState((s) => ({
      ...s,
      data: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
      version: 1,
      id: "r1",
      hydrated: true,
      original: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
      undoStack: [],
      redoStack: [],
      historyTTLTimer: null,
      debounceTimer: null,
      lastEditAt: null,
    }));
  });

  it("renders zh-CN 'Profiles' label for default profiles section row", async () => {
    const SectionsPanelMod = await import("../SectionsPanel");
    render(<SectionsPanelMod.default />);
    const row = screen.getByTestId("section-row-profiles") as HTMLElement;
    // The title span (font-medium) holds `value.title || SECTION_LABELS[id] || id`.
    const labelSpan = row.querySelector("button > span.font-medium") as HTMLElement;
    expect(labelSpan).toBeTruthy();
    expect(labelSpan.textContent).toBe(zhCN.resume.sectionsPanel.profiles);
    // Negative assertion: must NOT be the English fallback key.
    expect(labelSpan.textContent).not.toBe("Profiles");
  });

  it("renders zh-CN labels for all 12 section rows (L012 E2E rendering, not bundle shape)", async () => {
    const SectionsPanelMod = await import("../SectionsPanel");
    render(<SectionsPanelMod.default />);
    for (const key of SECTION_KEYS) {
      const row = screen.getByTestId(`section-row-${key}`) as HTMLElement;
      const labelSpan = row.querySelector("button > span.font-medium") as HTMLElement;
      const expected = (zhCN.resume.sectionsPanel as Record<string, string>)[key];
      expect(
        labelSpan.textContent,
        `${key} row must render zhCN.resume.sectionsPanel.${key}`,
      ).toBe(expected);
    }
  });

  it("user-typed custom title still overrides SECTION_LABELS fallback (regression guard)", async () => {
    // Editing the title field should make `value.title` non-empty, so
    // the fallback chain returns the user value rather than the
    // zh-CN label. Confirms Plan A (empty default) didn't break the
    // "user can override" path.
    const SectionsPanelMod = await import("../SectionsPanel");
    const storeMod = await import("../../../store");
    storeMod.useResumeV2Store.getState().setDataMut((d) => {
      d.sections.profiles.title = "我的资料";
    });
    render(<SectionsPanelMod.default />);
    const row = screen.getByTestId("section-row-profiles") as HTMLElement;
    const labelSpan = row.querySelector("button > span.font-medium") as HTMLElement;
    expect(labelSpan.textContent).toBe("我的资料");
  });

  it("title input reflects the empty default until user types (form-state mirror)", async () => {
    const SectionsPanelMod = await import("../SectionsPanel");
    render(<SectionsPanelMod.default />);
    // Expand the experience row to expose the title input.
    const row = screen.getByTestId("section-row-experience") as HTMLElement;
    const toggle = row.querySelector("button") as HTMLElement;
    act(() => {
      fireEvent.click(toggle);
    });
    const input = screen.getByTestId("section-title-experience") as HTMLInputElement;
    expect(input.value).toBe("");
  });
});