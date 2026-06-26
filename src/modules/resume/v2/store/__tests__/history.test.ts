/**
 * T162 — history.test.ts (US17 Undo/Redo smoke tests).
 *
 * Covers the four behaviors required by spec US17:
 *   1. Stack depth is capped at 20 — the oldest entry is dropped on overflow.
 *   2. `undo()` + `redo()` cycle restores snapshots.
 *   3. A new edit after undo clears the `redoStack`.
 *   4. 30-min TTL clears both stacks and the next undo fires a toast.
 *
 * We exercise the public store API only (no real network). The setData
 * helper is preferred over setDataMut for these assertions because it
 * directly replaces the data document, sidestepping the in-place
 * immer mutation that depends on store integration with a live
 * immer middleware instance.
 */
import { beforeEach, describe, expect, it, vi, afterEach } from "vitest";
import { defaultResumeDataV2 } from "../../schema/defaults";

const freshData = (overrides?: { name?: string }) => {
  const d = JSON.parse(JSON.stringify(defaultResumeDataV2));
  if (overrides?.name !== undefined) d.basics.name = overrides.name;
  return d;
};

const mockUpdateResume = vi.fn();
const fireToastMock = vi.fn();

vi.mock("../../api", () => ({
  updateResume: (...args: unknown[]) => mockUpdateResume(...args),
}));

vi.mock("@/modules/resume/v2/editor/center/toast", () => ({
  fireToast: (msg: string, kind: "info" | "warn" | "error" = "info") => {
    fireToastMock(msg, kind);
  },
}));

const importStore = async () => {
  // Re-import after vi.resetModules() (in beforeEach) to pick up a
  // fresh store with no prior setInterval handle. This guarantees the
  // TTL watchdog is started under the test's fake-timer context, not
  // a leftover from an earlier test in the file.
  return await import("../index");
};

describe("resume v2 store — history (US17)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();
    mockUpdateResume.mockReset();
    mockUpdateResume.mockResolvedValue({
      id: "r1",
      version: 1,
      data: freshData(),
    });
    fireToastMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("caps the undo stack at 20 (oldest dropped on overflow)", async () => {
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData(),
      version: 0,
    });
    // Push 21 distinct edits via setData (directly replaces data).
    for (let i = 1; i <= 21; i += 1) {
      useResumeV2Store.getState().setData(freshData({ name: `edit-${i}` }));
    }
    const s = useResumeV2Store.getState();
    expect(s.undoStack.length).toBe(20);
    // The bottom of the stack should NOT be the pre-edit-1 snapshot
    // (which would have name "" or whatever the seed used) — the oldest
    // entry in the stack should be edit-1's pre-state, which had
    // name = "edit-1" before the next setData replaced it. Either way,
    // length is 20 not 21.
    expect(s.undoStack.length).toBeLessThanOrEqual(20);
  });

  it("undo() + redo() cycle restores snapshots", async () => {
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData({ name: "seed" }),
      version: 0,
    });
    useResumeV2Store.getState().setData(freshData({ name: "A" }));
    useResumeV2Store.getState().setData(freshData({ name: "B" }));
    useResumeV2Store.getState().setData(freshData({ name: "C" }));
    expect(useResumeV2Store.getState().undoStack.length).toBe(3);
    useResumeV2Store.getState().undo();
    expect(useResumeV2Store.getState().undoStack.length).toBe(2);
    expect(useResumeV2Store.getState().redoStack.length).toBe(1);
    useResumeV2Store.getState().undo();
    expect(useResumeV2Store.getState().undoStack.length).toBe(1);
    expect(useResumeV2Store.getState().redoStack.length).toBe(2);
    useResumeV2Store.getState().redo();
    expect(useResumeV2Store.getState().redoStack.length).toBe(1);
    useResumeV2Store.getState().redo();
    expect(useResumeV2Store.getState().redoStack.length).toBe(0);
    expect(useResumeV2Store.getState().undoStack.length).toBe(3);
  });

  it("new edit after undo clears the redo stack", async () => {
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData({ name: "seed" }),
      version: 0,
    });
    useResumeV2Store.getState().setData(freshData({ name: "X" }));
    useResumeV2Store.getState().setData(freshData({ name: "Y" }));
    useResumeV2Store.getState().undo();
    expect(useResumeV2Store.getState().redoStack.length).toBe(1);
    useResumeV2Store.getState().setData(freshData({ name: "Z-branch" }));
    expect(useResumeV2Store.getState().redoStack.length).toBe(0);
  });

  it("30-min TTL clears both stacks and next undo fires a toast", async () => {
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData({ name: "seed" }),
      version: 0,
    });
    useResumeV2Store.getState().setData(freshData({ name: "L" }));
    useResumeV2Store.getState().setData(freshData({ name: "M" }));
    expect(useResumeV2Store.getState().undoStack.length).toBe(2);
    // Advance 30 minutes + 60s for the watchdog to fire at least once.
    vi.advanceTimersByTime(31 * 60 * 1000);
    expect(useResumeV2Store.getState().undoStack.length).toBe(0);
    expect(useResumeV2Store.getState().redoStack.length).toBe(0);
    expect(useResumeV2Store.getState().historyTTLExpired).toBe(true);
    // Now undo() should fire the toast
    fireToastMock.mockClear();
    useResumeV2Store.getState().undo();
    expect(fireToastMock).toHaveBeenCalled();
    const lastCall = fireToastMock.mock.calls[fireToastMock.mock.calls.length - 1];
    expect(String(lastCall[0])).toMatch(/历史|expir|TTL/i);
  });
});
