// REQ-034 US3 — ProjectsSectionList tests.
//
// Covers AC-01, AC-02, AC-17, AC-05c.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

vi.mock("../../center/toast", () => ({
  fireToast: vi.fn(),
}));

const importList = async () => await import("../ProjectsSectionList");
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
    name: "",
    period: "",
    website: { url: "", label: "", inlineLink: false },
    description: "",
    highlights: [],
    ...fields,
  };
}

describe("ProjectsSectionList (AC-01, AC-02, AC-17, AC-05c)", () => {
  beforeEach(async () => {
    const DialogHostMod = await importDialog();
    DialogHostMod.useDialogStore.setState({ active: null });
  });

  it("renders items list + add button (AC-01)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [
          seedItem("p1", { name: "Alpha" }),
          seedItem("p2", { name: "Beta" }),
        ];
      });
    });
    const { ProjectsSectionList } = await importList();
    render(<ProjectsSectionList />);
    expect(screen.getByTestId("projects-section-list")).toBeTruthy();
    expect(screen.getByTestId("projects-add-item")).toBeTruthy();
    expect(screen.getByTestId("projects-item-row-p1")).toBeTruthy();
    expect(screen.getByTestId("projects-item-row-p2")).toBeTruthy();
    expect(screen.getByTestId("projects-name-display-p1").textContent).toBe("Alpha");
    expect(screen.getByTestId("projects-name-display-p2").textContent).toBe("Beta");
  });

  it("add button pushes empty item + opens projects.update dialog (AC-02)", async () => {
    await resetStore();
    const { ProjectsSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<ProjectsSectionList />);
    act(() => {
      fireEvent.click(screen.getByTestId("projects-add-item"));
    });
    const after = useResumeV2Store.getState().data.sections.projects.items;
    expect(after.length).toBe(1);
    expect(after[0].highlights).toEqual([]);
    expect(useDialogStore.getState().active?.type).toBe("projects.update");
  });

  it("edit / duplicate / delete inline actions (AC-17)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedItem("p1", { name: "P1" })];
      });
    });
    const { ProjectsSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<ProjectsSectionList />);
    act(() => {
      fireEvent.click(screen.getByTestId("projects-item-edit-p1"));
    });
    expect(useDialogStore.getState().active?.type).toBe("projects.update");
    act(() => {
      fireEvent.click(screen.getByTestId("projects-item-duplicate-p1"));
    });
    const afterDup = useResumeV2Store.getState().data.sections.projects.items;
    expect(afterDup.length).toBe(2);
    expect(afterDup[1].name).toBe("P1");
    expect(useDialogStore.getState().active?.type).toBe("projects.update");
    act(() => {
      fireEvent.click(screen.getByTestId("projects-item-delete-p1"));
    });
    expect(useResumeV2Store.getState().data.sections.projects.items.length).toBe(1);
  });

  it("hidden=true renders faded row (AC-05c)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedItem("p1", { hidden: true, name: "X" })];
      });
    });
    const { ProjectsSectionList } = await importList();
    render(<ProjectsSectionList />);
    const row = screen.getByTestId("projects-item-row-p1") as HTMLElement;
    expect(row.getAttribute("data-hidden")).toBe("true");
    expect(row.textContent).toContain("X");
  });
});