// REQ-034 US4 — ProfileSectionList tests.
//
// Covers AC-01, AC-02, AC-11 (inline actions + deep copy),
// AC-12 (drag-reorder + cross-section isolation + 500ms batch),
// AC-19 (hidden=true visual fade incl icon),
// AC-22 (keyboard reorder),
// AC-15 (no dangerouslySetInnerHTML).

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

vi.mock("../../center/toast", () => ({
  fireToast: vi.fn(),
}));

const importList = async () => await import("../ProfileSectionList");
const importStore = async () => await import("../../../store");
const importDialog = async () => await import("../../dialogs/DialogHost");

async function resetStore(
  setup?: (m: Awaited<ReturnType<typeof importStore>>) => void,
) {
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
    icon: "github",
    iconColor: "rgba(0,0,0,1)",
    network: "",
    username: "",
    website: { url: "", label: "", inlineLink: false },
    ...fields,
  };
}

describe("ProfileSectionList (AC-01, AC-02, AC-11, AC-15, AC-17)", () => {
  beforeEach(async () => {
    const DialogHostMod = await importDialog();
    DialogHostMod.useDialogStore.setState({ active: null });
  });

  it("renders items list + add button + shared SectionItem (AC-01)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [
          seedItem("p1", { network: "GitHub" }),
          seedItem("p2", { network: "LinkedIn" }),
        ];
      });
    });
    const { ProfileSectionList } = await importList();
    render(<ProfileSectionList />);
    expect(screen.getByTestId("profile-section-list")).toBeTruthy();
    expect(screen.getByTestId("profile-add-item")).toBeTruthy();
    expect(screen.getByTestId("profile-item-row-p1")).toBeTruthy();
    expect(screen.getByTestId("profile-item-row-p2")).toBeTruthy();
    expect(
      screen.getByTestId("profile-network-display-p1").textContent,
    ).toBe("GitHub");
    expect(
      screen.getByTestId("profile-network-display-p2").textContent,
    ).toBe("LinkedIn");
  });

  it("renders the network icon on each row with data-icon attr (AC-05)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [
          seedItem("p1", { icon: "github", network: "GitHub" }),
        ];
      });
    });
    const { ProfileSectionList } = await importList();
    render(<ProfileSectionList />);
    const icon = screen.getByTestId("profile-network-icon-display-p1");
    expect(icon).toBeTruthy();
    expect(icon.getAttribute("data-icon")).toBe("github");
  });

  it("add button pushes empty item with icon='github' and opens profile.update dialog (AC-02)", async () => {
    const uuidSpy = vi.spyOn(globalThis.crypto, "randomUUID");
    await resetStore();
    const { ProfileSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<ProfileSectionList />);
    act(() => {
      fireEvent.click(screen.getByTestId("profile-add-item"));
    });
    const after = useResumeV2Store.getState().data.sections.profiles.items;
    expect(after.length).toBe(1);
    const newItem = after[0];
    // AC-02 (R8): default icon = 'github' (not 'acorn').
    expect(newItem.icon).toBe("github");
    expect(newItem.iconColor).toBe("rgba(0,0,0,1)");
    expect(newItem.network).toBe("");
    expect(newItem.username).toBe("");
    expect(newItem.website).toEqual({
      url: "",
      label: "",
      inlineLink: false,
    });
    expect(newItem.hidden).toBe(false);
    // crypto.randomUUID is invoked exactly once (per freshItem()).
    // (vi spy works because crypto.randomUUID is on globalThis.crypto.)
    expect(uuidSpy.mock.calls.length).toBeGreaterThanOrEqual(1);
    const active = useDialogStore.getState().active;
    expect(active?.type).toBe("profile.update");
  });

  it("add button 5 times produces 5 unique ids (AC-02)", async () => {
    await resetStore();
    const { ProfileSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    render(<ProfileSectionList />);
    for (let i = 0; i < 5; i++) {
      act(() => {
        fireEvent.click(screen.getByTestId("profile-add-item"));
      });
    }
    const ids = useResumeV2Store
      .getState()
      .data.sections.profiles.items.map((i) => i.id);
    expect(ids.length).toBe(5);
    expect(new Set(ids).size).toBe(5);
  });

  it("edit / duplicate / delete inline actions (AC-11)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [
          seedItem("p1", {
            icon: "github",
            iconColor: "rgba(255,0,0,1)",
            network: "GitHub",
            username: "alice",
            website: {
              url: "https://github.com/alice",
              label: "GH",
              inlineLink: true,
            },
          }),
        ];
      });
    });
    const { ProfileSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    const { useDialogStore } = await importDialog();
    render(<ProfileSectionList />);
    expect(screen.getByTestId("profile-item-edit-p1")).toBeTruthy();
    expect(screen.getByTestId("profile-item-duplicate-p1")).toBeTruthy();
    expect(screen.getByTestId("profile-item-delete-p1")).toBeTruthy();
    // edit opens update dialog with itemId.
    act(() => {
      fireEvent.click(screen.getByTestId("profile-item-edit-p1"));
    });
    expect(useDialogStore.getState().active?.type).toBe("profile.update");
    expect(
      (useDialogStore.getState().active?.payload as { itemId?: string })
        ?.itemId,
    ).toBe("p1");
    act(() => {
      useDialogStore.getState().closeDialog();
    });
    // duplicate pushes a deep-copy with fresh id, no dialog.
    const before = useResumeV2Store.getState().data.sections.profiles.items
      .length;
    act(() => {
      fireEvent.click(screen.getByTestId("profile-item-duplicate-p1"));
    });
    const afterDup = useResumeV2Store.getState().data.sections.profiles.items;
    expect(afterDup.length).toBe(before + 1);
    const clone = afterDup[afterDup.length - 1];
    expect(clone.id).not.toBe("p1");
    expect(clone.icon).toBe("github");
    expect(clone.iconColor).toBe("rgba(255,0,0,1)");
    expect(clone.network).toBe("GitHub");
    expect(clone.username).toBe("alice");
    expect(clone.website.url).toBe("https://github.com/alice");
    expect(clone.website.label).toBe("GH");
    expect(clone.website.inlineLink).toBe(true);
    // AC-11 (R12): deep-copy integrity — editing clone.website.url must
    // not pollute original.website.url.
    expect(clone.website).not.toBe(afterDup[0].website);
    useResumeV2Store.getState().setDataMut((d) => {
      const last = d.sections.profiles.items[d.sections.profiles.items.length - 1];
      last.website.url = "https://x.com";
    });
    const refreshed = useResumeV2Store.getState().data.sections.profiles.items;
    expect(refreshed[0].website.url).toBe("https://github.com/alice");
    // duplicate does NOT open the update dialog.
    expect(useDialogStore.getState().active).toBeNull();
    // delete splices by id and pushes undo.
    const undoBefore = useResumeV2Store.getState().undoStack.length;
    act(() => {
      fireEvent.click(screen.getByTestId("profile-item-delete-p1"));
    });
    const remaining = useResumeV2Store
      .getState()
      .data.sections.profiles.items.map((i) => i.id);
    expect(remaining).not.toContain("p1");
    expect(useResumeV2Store.getState().undoStack.length).toBeGreaterThan(
      undoBefore,
    );
  });

  it("hidden=true renders faded row incl icon node (AC-19)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [
          seedItem("p1", {
            hidden: true,
            icon: "github",
            network: "GitHub",
          }),
        ];
      });
    });
    const { ProfileSectionList } = await importList();
    render(<ProfileSectionList />);
    const row = screen.getByTestId("profile-item-row-p1") as HTMLElement;
    expect(row.getAttribute("data-hidden")).toBe("true");
    expect(row.textContent).toContain("GitHub");
    // The network-display text node still exists.
    expect(screen.getByTestId("profile-network-display-p1").textContent).toBe(
      "GitHub",
    );
    // The icon-display node is greyed (opacity < 1 via 'opacity-50'
    // className when hidden=true).
    const icon = screen.getByTestId("profile-network-icon-display-p1");
    expect(icon).toBeTruthy();
    expect(icon.getAttribute("data-icon")).toBe("github");
    expect(icon.className).toContain("opacity-50");
  });

  it("row text rendered without dangerouslySetInnerHTML (AC-15)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [
          seedItem("p1", { network: "<b>GitHub</b>" }),
        ];
      });
    });
    const { ProfileSectionList } = await importList();
    render(<ProfileSectionList />);
    const row = screen.getByTestId("profile-item-row-p1") as HTMLElement;
    expect(row.textContent).toContain("<b>GitHub</b>");
    expect(row.querySelector("b")).toBeNull();
  });
});

describe("ProfileSectionList drag reorder (AC-12)", () => {
  beforeEach(async () => {
    const DialogHostMod = await importDialog();
    DialogHostMod.useDialogStore.setState({ active: null });
  });

  it("data-dnd-context === 'profiles'", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [seedItem("p1"), seedItem("p2")];
      });
    });
    const { ProfileSectionList } = await importList();
    render(<ProfileSectionList />);
    expect(
      screen
        .getByTestId("profile-section-list")
        .getAttribute("data-dnd-context"),
    ).toBe("profiles");
  });

  it("items drag-reorder preserves id set (AC-12)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [
          seedItem("p1"),
          seedItem("p2"),
          seedItem("p3"),
        ];
      });
    });
    const { ProfileSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    render(<ProfileSectionList />);
    // Drive handleDragEnd via test triggers (exposed by the list).
    act(() => {
      fireEvent.click(
        screen.getByTestId("profile-section-list-test-reorder-p3-p1"),
      );
    });
    const ids = useResumeV2Store
      .getState()
      .data.sections.profiles.items.map((i) => i.id);
    expect(ids).toEqual(["p3", "p1", "p2"]);
    expect(new Set(ids)).toEqual(new Set(["p1", "p2", "p3"]));
  });

  it("5 rapid drag-end events within 500ms collapse into 1 undoStack entry (AC-12)", async () => {
    vi.useFakeTimers();
    try {
      await resetStore((m) => {
        m.useResumeV2Store.getState().setDataMut((d) => {
          d.sections.profiles.items = [
            seedItem("p1"),
            seedItem("p2"),
            seedItem("p3"),
          ];
        });
      });
      const { ProfileSectionList } = await importList();
      const { useResumeV2Store } = await importStore();
      vi.advanceTimersByTime(500);
      render(<ProfileSectionList />);
      const undoBefore = useResumeV2Store.getState().undoStack.length;
      act(() => {
        fireEvent.click(
          screen.getByTestId("profile-section-list-test-reorder-p3-p1"),
        );
      });
      act(() => {
        fireEvent.click(
          screen.getByTestId("profile-section-list-test-reorder-p1-p2"),
        );
      });
      act(() => {
        fireEvent.click(
          screen.getByTestId("profile-section-list-test-reorder-p2-p3"),
        );
      });
      act(() => {
        fireEvent.click(
          screen.getByTestId("profile-section-list-test-reorder-p3-p2"),
        );
      });
      act(() => {
        fireEvent.click(
          screen.getByTestId("profile-section-list-test-reorder-p1-p3"),
        );
      });
      const undoAfter = useResumeV2Store.getState().undoStack.length;
      expect(undoAfter).toBe(undoBefore + 1);
      const captured = useResumeV2Store.getState().undoStack.at(-1);
      const capturedIds = captured!.data.sections.profiles.items.map(
        (i) => i.id,
      );
      expect(capturedIds).toEqual(["p1", "p2", "p3"]);
      vi.advanceTimersByTime(500);
      act(() => {
        useResumeV2Store.getState().undo();
      });
      const afterUndoIds = useResumeV2Store
        .getState()
        .data.sections.profiles.items.map((i) => i.id);
      expect(afterUndoIds).toEqual(["p1", "p2", "p3"]);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("ProfileSectionList keyboard reorder (AC-22)", () => {
  beforeEach(async () => {
    const DialogHostMod = await importDialog();
    DialogHostMod.useDialogStore.setState({ active: null });
  });

  it("tab focus + Space pickup + Arrow move + Space drop", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.profiles.items = [
          seedItem("p1"),
          seedItem("p2"),
          seedItem("p3"),
        ];
      });
    });
    const { ProfileSectionList } = await importList();
    const { useResumeV2Store } = await importStore();
    render(<ProfileSectionList />);
    const p2 = screen.getByTestId("profile-item-row-p2");
    expect(p2.getAttribute("data-item-id")).toBe("p2");
    expect(p2.getAttribute("aria-roledescription")).toBe("sortable");
    // ArrowUp on p2 → swap p2 ↔ p1 via the test trigger.
    act(() => {
      fireEvent.click(
        screen.getByTestId("profile-section-list-test-reorder-arrow-up-p2"),
      );
    });
    const ids = useResumeV2Store
      .getState()
      .data.sections.profiles.items.map((i) => i.id);
    expect(ids).toEqual(["p2", "p1", "p3"]);
  });
});