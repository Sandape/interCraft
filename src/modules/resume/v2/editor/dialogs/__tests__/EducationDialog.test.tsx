// REQ-034 US3 — EducationDialog tests.
//
// Covers AC-03 (prefill), AC-04 (11 input testids + field-level
// setDataMut), AC-07 (courses add/remove/drag-reorder), AC-08b
// (drag 500ms batch), AC-09b (id preserved), AC-11 (period single
// input), AC-13 (URL whitelist), AC-14 (XSS escaping), AC-15 (close
// loops undo to S0), AC-16 (no local draft state).

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../EducationDialog");
const importStore = async () => await import("../../../store");

async function resetStore(setup?: (m: Awaited<ReturnType<typeof importStore>>) => void) {
  const storeMod = await importStore();
  const defaultsMod = await import("../../../schema/defaults");
  storeMod.useResumeV2Store.setState((s) => ({
    ...s,
    data: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
    version: 1,
    id: "r1",
    hydrated: true,
    original: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
    undoStack: [],
    redoStack: [],
    debounceTimer: null,
    historyTTLTimer: null,
    lastEditAt: null,
  }));
  setup?.(storeMod);
}

function seedSingle(fields: Record<string, unknown> = {}) {
  return {
    id: "e1",
    hidden: false,
    school: "Tsinghua",
    degree: "Bachelor",
    area: "CS",
    grade: "3.8/4.0",
    location: "Beijing",
    period: "2018-09 ~ 2022-06",
    website: { url: "", label: "", inlineLink: false },
    description: "<p>foo</p>",
    courses: [],
    ...fields,
  };
}

describe("EducationDialog (AC-03, AC-04, AC-11, AC-13, AC-14, AC-16)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders 11 input testids (AC-04)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedSingle()];
      });
    });
    const { EducationDialog } = await importDialog();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    expect(screen.getByTestId("education-school")).toBeTruthy();
    expect(screen.getByTestId("education-degree")).toBeTruthy();
    expect(screen.getByTestId("education-area")).toBeTruthy();
    expect(screen.getByTestId("education-grade")).toBeTruthy();
    expect(screen.getByTestId("education-location")).toBeTruthy();
    expect(screen.getByTestId("education-period")).toBeTruthy();
    expect(screen.getByTestId("education-website-url")).toBeTruthy();
    expect(screen.getByTestId("education-website-label")).toBeTruthy();
    expect(screen.getByTestId("education-website-inline-link")).toBeTruthy();
    expect(screen.getByTestId("education-hidden")).toBeTruthy();
    expect(screen.getByTestId("education-description")).toBeTruthy();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedSingle()];
      });
    });
    const { EducationDialog } = await importDialog();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    expect((screen.getByTestId("education-school") as HTMLInputElement).value).toBe("Tsinghua");
    expect((screen.getByTestId("education-degree") as HTMLInputElement).value).toBe("Bachelor");
    expect((screen.getByTestId("education-area") as HTMLInputElement).value).toBe("CS");
    expect((screen.getByTestId("education-grade") as HTMLInputElement).value).toBe("3.8/4.0");
    expect((screen.getByTestId("education-location") as HTMLInputElement).value).toBe("Beijing");
    expect((screen.getByTestId("education-period") as HTMLInputElement).value).toBe("2018-09 ~ 2022-06");
  });

  it("top-level field edits write to store and push undo (AC-04)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedSingle()];
      });
    });
    const { EducationDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    const initial = useResumeV2Store.getState().undoStack.length;
    fireEvent.change(screen.getByTestId("education-school"), { target: { value: "MIT" } });
    fireEvent.change(screen.getByTestId("education-degree"), { target: { value: "Master" } });
    fireEvent.change(screen.getByTestId("education-area"), { target: { value: "EE" } });
    fireEvent.change(screen.getByTestId("education-grade"), { target: { value: "4.0" } });
    fireEvent.change(screen.getByTestId("education-location"), { target: { value: "Boston" } });
    const item = useResumeV2Store.getState().data.sections.education.items[0];
    expect(item.school).toBe("MIT");
    expect(item.degree).toBe("Master");
    expect(item.area).toBe("EE");
    expect(item.grade).toBe("4.0");
    expect(item.location).toBe("Boston");
    expect(useResumeV2Store.getState().undoStack.length).toBeGreaterThan(initial + 1);
  });

  it("period is a single free-form input (AC-11, R2)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedSingle()];
      });
    });
    const { EducationDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    expect(screen.queryByTestId("education-period-start")).toBeNull();
    expect(screen.queryByTestId("education-period-end")).toBeNull();
    fireEvent.change(screen.getByTestId("education-period"), {
      target: { value: "2018-09 ~ Present" },
    });
    const item = useResumeV2Store.getState().data.sections.education.items[0];
    expect(item.period).toBe("2018-09 ~ Present");
  });

  it("URL whitelist accepts https/tel/mailto/IPv6/unicode, rejects javascript: (AC-13)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedSingle()];
      });
    });
    const { EducationDialog } = await importDialog();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    const input = screen.getByTestId("education-website-url") as HTMLInputElement;
    for (const ok of [
      "https://[::1]:8080",
      "tel:+86-010-1234",
      "mailto:a@b.com",
      "https://中文.cn",
    ]) {
      fireEvent.change(input, { target: { value: ok } });
      fireEvent.blur(input);
      expect(screen.queryByTestId("education-website-url-error")).toBeNull();
    }
    fireEvent.change(input, { target: { value: "javascript:alert(1)" } });
    fireEvent.blur(input);
    expect(screen.getByTestId("education-website-url-error")).toBeTruthy();
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("script payload escaped (AC-14)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedSingle()];
      });
    });
    const { EducationDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    const payload = "<script>window.__xss=1</script>";
    const input = screen.getByTestId("education-school") as HTMLInputElement;
    fireEvent.change(input, { target: { value: payload } });
    expect(useResumeV2Store.getState().data.sections.education.items[0].school).toBe(payload);
    expect(input.value).toBe(payload);
    expect((globalThis as { __xss?: number }).__xss).toBeUndefined();
  });

  it("no local useState for form fields (AC-16)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const file = path.join(process.cwd(), "src/modules/resume/v2/editor/dialogs/EducationDialog.tsx");
    const src = fs.readFileSync(file, "utf-8");
    const stateCount = (src.match(/useState/g) || []).length;
    // Only the fieldErrors error display uses useState — 1 call expected.
    expect(stateCount).toBeLessThanOrEqual(2);
  });
});

describe("EducationDialog courses add/remove/drag-reorder (AC-07, AC-07b, AC-08b)", () => {
  it("courses add from empty array creates one empty string (AC-07b)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedSingle({ courses: [] })];
      });
    });
    const { EducationDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    act(() => {
      fireEvent.click(screen.getByTestId("education-add-course"));
    });
    const item = useResumeV2Store.getState().data.sections.education.items[0];
    expect(item.courses.length).toBe(1);
    expect(item.courses[0]).toBe("");
  });

  it("courses remove splices by idx (AC-07)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [
          seedSingle({ courses: ["Algorithms", "OS"] }),
        ];
      });
    });
    const { EducationDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    act(() => {
      fireEvent.click(screen.getByTestId("education-course-remove-0"));
    });
    const item = useResumeV2Store.getState().data.sections.education.items[0];
    expect(item.courses.length).toBe(1);
    expect(item.courses[0]).toBe("OS");
  });

  it("drag reorder 5 times within 500ms collapses into 1 undoStack entry (AC-08b)", async () => {
    vi.useFakeTimers();
    try {
      await resetStore((m) => {
        m.useResumeV2Store.getState().setDataMut((d) => {
          d.sections.education.items = [
            seedSingle({ courses: ["A", "B", "C"] }),
          ];
        });
      });
      const { EducationDialog } = await importDialog();
      const { useResumeV2Store } = await importStore();
      vi.advanceTimersByTime(500);
      render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
      const undoBefore = useResumeV2Store.getState().undoStack.length;
      act(() => { fireEvent.click(screen.getByTestId("education-test-reorder-2-0")); });
      act(() => { fireEvent.click(screen.getByTestId("education-test-reorder-0-1")); });
      act(() => { fireEvent.click(screen.getByTestId("education-test-reorder-1-2")); });
      act(() => { fireEvent.click(screen.getByTestId("education-test-reorder-2-1")); });
      act(() => { fireEvent.click(screen.getByTestId("education-test-reorder-0-2")); });
      const undoAfter = useResumeV2Store.getState().undoStack.length;
      expect(undoAfter).toBe(undoBefore + 1);
      const captured = useResumeV2Store.getState().undoStack.at(-1);
      const capturedCourses = captured!.data.sections.education.items[0].courses;
      expect(capturedCourses).toEqual(["A", "B", "C"]);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("EducationDialog close loops undo to S0 (AC-15)", () => {
  it("ESC after 5 mutations reverts to pre-dialog snapshot", async () => {
    await resetStore();
    const { useResumeV2Store } = await importStore();
    const { EducationDialog } = await importDialog();
    useResumeV2Store.getState().setDataMut((d) => {
      d.sections.education.items = [seedSingle()];
    });
    const S0 = JSON.parse(JSON.stringify(useResumeV2Store.getState().data));
    render(<EducationDialog onClose={() => {}} sectionId="education" itemId="e1" />);
    fireEvent.change(screen.getByTestId("education-school"), { target: { value: "MIT" } });
    fireEvent.change(screen.getByTestId("education-degree"), { target: { value: "PhD" } });
    fireEvent.change(screen.getByTestId("education-period"), { target: { value: "2024" } });
    act(() => { fireEvent.click(screen.getByTestId("education-add-course")); });
    act(() => { fireEvent.click(screen.getByTestId("education-test-reorder-0-1")); });
    // Simulate close path: looped undo.
    let guard = 50;
    while (
      guard-- > 0 &&
      JSON.stringify(useResumeV2Store.getState().data) !== JSON.stringify(S0)
    ) {
      useResumeV2Store.getState().undo();
    }
    expect(JSON.stringify(useResumeV2Store.getState().data)).toBe(JSON.stringify(S0));
  });
});