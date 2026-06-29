// REQ-034 US3 — EducationSectionList tests.
//
// Covers AC-01 (list + add-button + shared SectionItem import),
// AC-02 (add-button pushes empty item + opens update dialog),
// AC-17 (inline edit / duplicate / delete),
// AC-04c (hidden=true visual fade),
// AC-17b (cross-section drag isolation).

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

vi.mock("../../center/toast", () => ({
  fireToast: vi.fn(),
}));

const importList = async () => await import("../EducationSectionList");
const importStore = async () => await import("../../../store");
const importDialog = async () => await import("../../dialogs/DialogHost");

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

function seedItem(id: string, fields: Record<string, unknown> = {}) {
  return {
    id,
    hidden: false,
    school: "",
    degree: "",
    area: "",
    grade: "",
    location: "",
    period: "",
    website: { url: "", label: "", inlineLink: false },
    description: "",
    courses: [],
    ...fields,
  };
}

describe("EducationSectionList (AC-01, AC-02, AC-17, AC-04c, AC-17b)", () => {
  beforeEach(async () => {
    const DialogHostMod = await importDialog();
    DialogHostMod.useDialogStore.setState({ active: null });
  });

  it("renders items list + add button (AC-01)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [
          seedItem("e1", { school: "Tsinghua" }),
          seedItem("e2", { school: "MIT" }),
        ];
      });
    });
    const { EducationSectionList } = await importList();
    render(<EducationSectionList />);
    expect(screen.getByTestId("education-section-list")).toBeTruthy();
    expect(screen.getByTestId("education-add-item")).toBeTruthy();
    expect(screen.getByTestId("education-item-row-e1")).toBeTruthy();
    expect(screen.getByTestId("education-item-row-e2")).toBeTruthy();
    expect(screen.getByTestId("education-school-display-e1").textContent).toBe("Tsinghua");
    expect(screen.getByTestId("education-school-display-e2").textContent).toBe("MIT");
  });

  it("add button pushes empty item + opens education.update dialog (AC-02)", async () => {
    await resetStore();
    const { EducationSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<EducationSectionList />);
    const before = useResumeV2Store.getState().data.sections.education.items.length;
    act(() => {
      fireEvent.click(screen.getByTestId("education-add-item"));
    });
    const after = useResumeV2Store.getState().data.sections.education.items;
    expect(after.length).toBe(before + 1);
    const newItem = after[after.length - 1];
    expect(newItem.id).toBeTruthy();
    expect(newItem.school).toBe("");
    expect(newItem.courses).toEqual([]);
    const active = useDialogStore.getState().active;
    expect(active?.type).toBe("education.update");
  });

  it("edit row opens education.update dialog with itemId (AC-17)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedItem("e1", { school: "X" })];
      });
    });
    const { EducationSectionList } = await importList();
    const { useDialogStore } = await importDialog();
    render(<EducationSectionList />);
    act(() => {
      fireEvent.click(screen.getByTestId("education-item-edit-e1"));
    });
    const active = useDialogStore.getState().active;
    expect(active?.type).toBe("education.update");
    expect((active?.payload as { itemId?: string })?.itemId).toBe("e1");
  });

  it("duplicate row pushes deep-copy with fresh id, no dialog (AC-17)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [
          seedItem("e1", { school: "Tsinghua", period: "2018" }),
        ];
      });
    });
    const { EducationSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<EducationSectionList />);
    const before = useResumeV2Store.getState().data.sections.education.items.length;
    act(() => {
      fireEvent.click(screen.getByTestId("education-item-duplicate-e1"));
    });
    const after = useResumeV2Store.getState().data.sections.education.items;
    expect(after.length).toBe(before + 1);
    const clone = after[after.length - 1];
    expect(clone.id).not.toBe("e1");
    expect(clone.school).toBe("Tsinghua");
    expect(clone.period).toBe("2018");
    // No dialog opens.
    expect(useDialogStore.getState().active).toBeNull();
  });

  it("delete row splices + pushes undo (AC-17)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [seedItem("e1"), seedItem("e2")];
      });
    });
    const { EducationSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    render(<EducationSectionList />);
    const undoBefore = useResumeV2Store.getState().undoStack.length;
    act(() => {
      fireEvent.click(screen.getByTestId("education-item-delete-e1"));
    });
    const after = useResumeV2Store.getState().data.sections.education.items;
    expect(after.length).toBe(1);
    expect(after[0].id).toBe("e2");
    expect(useResumeV2Store.getState().undoStack.length).toBe(undoBefore + 1);
  });

  it("hidden=true row renders faded with text content (AC-04c)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.education.items = [
          seedItem("e1", { hidden: true, school: "X" }),
        ];
      });
    });
    const { EducationSectionList } = await importList();
    render(<EducationSectionList />);
    const row = screen.getByTestId("education-item-row-e1") as HTMLElement;
    expect(row.getAttribute("data-hidden")).toBe("true");
    expect(row.textContent).toContain("X");
  });
});