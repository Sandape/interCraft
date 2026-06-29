// REQ-034 US3 — SkillsSectionList tests.
//
// Covers AC-01, AC-02, AC-17, AC-06c.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

vi.mock("../../center/toast", () => ({
  fireToast: vi.fn(),
}));

const importList = async () => await import("../SkillsSectionList");
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
    icon: "wrench",
    iconColor: "rgba(0,0,0,1)",
    name: "",
    proficiency: "",
    level: 1,
    keywords: [],
    ...fields,
  };
}

describe("SkillsSectionList (AC-01, AC-02, AC-17, AC-06c)", () => {
  beforeEach(async () => {
    const DialogHostMod = await importDialog();
    DialogHostMod.useDialogStore.setState({ active: null });
  });

  it("renders items list + add button (AC-01)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.skills.items = [
          seedItem("s1", { name: "React" }),
          seedItem("s2", { name: "Python" }),
        ];
      });
    });
    const { SkillsSectionList } = await importList();
    render(<SkillsSectionList />);
    expect(screen.getByTestId("skills-section-list")).toBeTruthy();
    expect(screen.getByTestId("skills-add-item")).toBeTruthy();
    expect(screen.getByTestId("skills-item-row-s1")).toBeTruthy();
    expect(screen.getByTestId("skills-item-row-s2")).toBeTruthy();
    expect(screen.getByTestId("skills-name-display-s1").textContent).toBe("React");
    expect(screen.getByTestId("skills-name-display-s2").textContent).toBe("Python");
  });

  it("add button pushes empty item + opens skills.update dialog (AC-02)", async () => {
    await resetStore();
    const { SkillsSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<SkillsSectionList />);
    act(() => {
      fireEvent.click(screen.getByTestId("skills-add-item"));
    });
    const after = useResumeV2Store.getState().data.sections.skills.items;
    expect(after.length).toBe(1);
    expect(after[0].name).toBe("");
    expect(after[0].keywords).toEqual([]);
    expect(useDialogStore.getState().active?.type).toBe("skills.update");
  });

  it("edit / duplicate / delete inline actions (AC-17)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.skills.items = [seedItem("s1", { name: "React" })];
      });
    });
    const { SkillsSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<SkillsSectionList />);
    act(() => {
      fireEvent.click(screen.getByTestId("skills-item-edit-s1"));
    });
    expect(useDialogStore.getState().active?.type).toBe("skills.update");
    act(() => {
      fireEvent.click(screen.getByTestId("skills-item-duplicate-s1"));
    });
    const afterDup = useResumeV2Store.getState().data.sections.skills.items;
    expect(afterDup.length).toBe(2);
    expect(afterDup[1].name).toBe("React");
    act(() => {
      fireEvent.click(screen.getByTestId("skills-item-delete-s1"));
    });
    expect(useResumeV2Store.getState().data.sections.skills.items.length).toBe(1);
  });

  it("hidden=true renders faded row (AC-06c)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.skills.items = [seedItem("s1", { hidden: true, name: "X" })];
      });
    });
    const { SkillsSectionList } = await importList();
    render(<SkillsSectionList />);
    const row = screen.getByTestId("skills-item-row-s1") as HTMLElement;
    expect(row.getAttribute("data-hidden")).toBe("true");
    expect(row.textContent).toContain("X");
  });
});