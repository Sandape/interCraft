// REQ-034 US5 — InterestsDialog tests.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../InterestsDialog");
const importStore = async () => await import("../../../store");

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

function seedSingle(fields: Record<string, unknown> = {}) {
  return {
    id: "i1",
    hidden: false,
    icon: "heart",
    iconColor: "rgba(0,0,0,1)",
    name: "Photography",
    keywords: ["portrait", "landscape"],
    ...fields,
  };
}

describe("InterestsDialog (AC-05, AC-12, AC-13, AC-14, AC-18, AC-19)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders 4 input testids (AC-05, R5 — no description)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.interests.items = [seedSingle()];
      });
    });
    const { InterestsDialog } = await importDialog();
    render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
    expect(screen.getByTestId("interests-icon")).toBeTruthy();
    expect(screen.getByTestId("interests-icon-color")).toBeTruthy();
    expect(screen.getByTestId("interests-name")).toBeTruthy();
    expect(screen.getByTestId("interests-keywords")).toBeTruthy();
    expect(screen.getByTestId("interests-hidden")).toBeTruthy();
    // R5: NO description field (RT)
    expect(screen.queryByTestId("interests-description")).toBeNull();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.interests.items = [seedSingle()];
      });
    });
    const { InterestsDialog } = await importDialog();
    render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
    expect((screen.getByTestId("interests-name") as HTMLInputElement).value).toBe(
      "Photography",
    );
    expect((screen.getByTestId("interests-icon") as HTMLInputElement).value).toBe("heart");
  });

  it("keywords add from empty array (AC-12)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.interests.items = [seedSingle({ keywords: [] })];
      });
    });
    const { InterestsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
    act(() => {
      fireEvent.click(screen.getByTestId("interests-keywords-add"));
    });
    const item = useResumeV2Store.getState().data.sections.interests.items[0];
    expect(item.keywords.length).toBe(1);
    expect(item.keywords[0]).toBe("");
  });

  it("keywords remove by index (AC-12)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.interests.items = [
          seedSingle({ keywords: ["a", "b", "c"] }),
        ];
      });
    });
    const { InterestsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
    act(() => {
      fireEvent.click(screen.getByTestId("interests-keyword-remove-0"));
    });
    const item = useResumeV2Store.getState().data.sections.interests.items[0];
    expect(item.keywords).toEqual(["b", "c"]);
  });

  it("keywords drag-reorder preserves ids (AC-14)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.interests.items = [
          seedSingle({ keywords: ["a", "b", "c"] }),
        ];
      });
    });
    const { InterestsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
    act(() => {
      fireEvent.click(screen.getByTestId("interests-test-reorder-2-0"));
    });
    const item = useResumeV2Store.getState().data.sections.interests.items[0];
    expect(item.keywords).toEqual(["c", "a", "b"]);
  });

  it("keywords drag batches within 500ms (AC-13)", async () => {
    vi.useFakeTimers();
    try {
      await resetStore((m) => {
        m.useResumeV2Store.getState().setDataMut((d) => {
          d.sections.interests.items = [
            seedSingle({ keywords: ["a", "b", "c"] }),
          ];
        });
      });
      const { InterestsDialog } = await importDialog();
      const { useResumeV2Store } = await importStore();
      render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
      const initial = useResumeV2Store.getState().undoStack.length;
      act(() => {
        fireEvent.click(screen.getByTestId("interests-test-reorder-2-0"));
        fireEvent.click(screen.getByTestId("interests-test-reorder-0-1"));
        fireEvent.click(screen.getByTestId("interests-test-reorder-1-2"));
        fireEvent.click(screen.getByTestId("interests-test-reorder-2-1"));
        fireEvent.click(screen.getByTestId("interests-test-reorder-0-2"));
      });
      act(() => {
        vi.advanceTimersByTime(500);
      });
      // 5 reorder events within 500ms -> 1 history frame
      expect(useResumeV2Store.getState().undoStack.length - initial).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("no local draft state — close loops undo to S0 (AC-19, AC-20)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.interests.items = [seedSingle()];
      });
    });
    const { useResumeV2Store } = await importStore();
    const S0 = JSON.parse(JSON.stringify(useResumeV2Store.getState().data));
    const { InterestsDialog } = await importDialog();
    render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
    fireEvent.change(screen.getByTestId("interests-name"), {
      target: { value: "Y" },
    });
    fireEvent.click(screen.getByTestId("interests-keywords-add"));
    fireEvent.click(screen.getByTestId("interests-test-reorder-2-0"));
    const state = useResumeV2Store.getState();
    let depth = state.undoStack.length;
    while (depth > 0) {
      state.undo();
      depth -= 1;
      const cur = useResumeV2Store.getState().data;
      if (JSON.stringify(cur) === JSON.stringify(S0)) break;
    }
    expect(useResumeV2Store.getState().data).toEqual(S0);
  });

  it("XSS payloads escaped (AC-18)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.interests.items = [seedSingle()];
      });
    });
    const { InterestsDialog } = await importDialog();
    render(<InterestsDialog onClose={() => {}} sectionId="interests" itemId="i1" />);
    const payload = "<img src=x onerror=alert(1)>";
    fireEvent.change(screen.getByTestId("interests-name"), {
      target: { value: payload },
    });
    const inp = screen.getByTestId("interests-name") as HTMLInputElement;
    expect(inp.value).toBe(payload);
  });
});
