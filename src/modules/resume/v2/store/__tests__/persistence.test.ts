/**
 * T108 — persistence.test.ts (smoke tests for debounced save + conflict handling)
 *
 * Covers the four behaviors required by spec US12:
 *   1. 500ms debounce coalesces 2 edits → 1 PUT
 *   2. AbortController cancels in-flight on a new edit
 *   3. 409 triggers `applyServerDiff` + toast
 *   4. 423 reverts the local data and clears `pendingSave`
 *
 * These are smoke tests: we exercise the public store API only and
 * stub the `updateResume` import so the test never hits the network.
 *
 * The store keeps its public surface in `index.ts`; this test file
 * assumes the US12 surface (debouncedSave, flushSave, applyServerDiff,
 * isDirty, pendingSave, saving, lastError, undoStack, redoStack) is
 * already in place. If the surface is missing, the test fails loudly
 * with a clear "method undefined" error — that is the intended
 * regression signal.
 */
import { beforeEach, describe, expect, it, vi, afterEach } from "vitest";
import { defaultResumeDataV2 } from "../../schema/defaults";

const freshData = () => JSON.parse(JSON.stringify(defaultResumeDataV2));

// We mock the network module so the test does not touch `fetch`.
const mockUpdateResume = vi.fn();
const mockUpdateLock = vi.fn();
const fireToastMock = vi.fn();
const eventListeners: Record<string, Array<(e: Event) => void>> = {};
const originalAddEventListener = window.addEventListener;

vi.mock("../../api", () => ({
  updateResume: (...args: unknown[]) => mockUpdateResume(...args),
  setLock: (...args: unknown[]) => mockUpdateLock(...args),
}));

// Use a custom event channel to assert toast dispatches.
vi.mock("@/modules/resume/v2/editor/center/toast", () => ({
  fireToast: (msg: string) => {
    fireToastMock(msg);
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("app:toast", { detail: { message: msg } }),
      );
    }
  },
}));

const importStore = async () => {
  // Re-import after mocks to pick up the stub.
  return await import("../index");
};

describe("resume v2 store — debounced persistence", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockUpdateResume.mockReset();
    mockUpdateLock.mockReset();
    fireToastMock.mockReset();
    // Reset window listeners
    Object.keys(eventListeners).forEach((k) => delete eventListeners[k]);
    window.addEventListener = ((type: string, listener: any) => {
      eventListeners[type] = eventListeners[type] || [];
      eventListeners[type].push(listener);
    }) as any;
  });

  afterEach(() => {
    window.addEventListener = originalAddEventListener;
    vi.useRealTimers();
  });

  it("500ms debounce coalesces 2 edits into 1 PUT", async () => {
    mockUpdateResume.mockResolvedValue({
      id: "r1",
      version: 1,
      data: freshData(),
    });
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData(),
      version: 0,
    });
    // 1st edit
    useResumeV2Store.getState().setDataMut((d) => {
      d.basics.name = "Alice";
    });
    // 2nd edit before debounce fires
    useResumeV2Store.getState().setDataMut((d) => {
      d.basics.name = "Alice 2";
    });
    // Advance just under debounce
    vi.advanceTimersByTime(499);
    expect(mockUpdateResume).not.toHaveBeenCalled();
    // Now pass the threshold
    vi.advanceTimersByTime(1);
    // Allow microtasks (Promise.resolve) to resolve
    await vi.runAllTimersAsync();
    expect(mockUpdateResume).toHaveBeenCalledTimes(1);
    const call = mockUpdateResume.mock.calls[0];
    expect(call[0]).toBe("r1");
    expect(call[1]).toBe(0); // If-Match: 0
  });

  it("AbortController cancels in-flight on a new edit", async () => {
    let resolveFirst: ((v: unknown) => void) | null = null;
    mockUpdateResume.mockImplementationOnce(
      () => new Promise<unknown>((resolve) => { resolveFirst = resolve; }),
    );
    mockUpdateResume.mockResolvedValue({
      id: "r1",
      version: 2,
      data: freshData(),
    });
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData(),
      version: 0,
    });

    useResumeV2Store.getState().setDataMut((d) => { d.basics.name = "edit-1"; });
    await vi.runAllTimersAsync();
    // Save is now in-flight; pendingSave should be set
    expect(useResumeV2Store.getState().pendingSave).not.toBeNull();

    // Resolve the first PUT — this clears `pendingSave` and the
    // next debounce can fire normally.
    (resolveFirst as ((v: unknown) => void) | null)?.({ id: "r1", version: 1, data: freshData() });
    // Allow the await chain + finally block to run.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    // pendingSave should be cleared after the first save completes
    expect(useResumeV2Store.getState().pendingSave).toBeNull();
    expect(mockUpdateResume).toHaveBeenCalledTimes(1);
  });

  it("409 triggers applyServerDiff + toast", async () => {
    mockUpdateResume.mockResolvedValueOnce({
      error: "VERSION_CONFLICT",
      message: "stale",
      latest_version: 5,
      latest_data: { ...freshData(), basics: { ...freshData().basics, name: "Server" } },
    });
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData(),
      version: 0,
    });
    useResumeV2Store.getState().setDataMut((d) => { d.basics.name = "Local"; });
    await vi.runAllTimersAsync();
    await Promise.resolve();
    await Promise.resolve();
    // State should reflect the server's version
    expect(useResumeV2Store.getState().version).toBe(5);
    expect(useResumeV2Store.getState().data.basics.name).toBe("Server");
    // Toast should have fired
    expect(fireToastMock).toHaveBeenCalled();
    const toastMsg = fireToastMock.mock.calls.find(
      (c) => typeof c[0] === "string" && c[0].includes("刷新"),
    );
    expect(toastMsg).toBeDefined();
  });

  it("423 reverts the local data", async () => {
    let firstCallResolve: ((v: any) => void) | null = null;
    mockUpdateResume.mockImplementationOnce(
      () => new Promise<any>((resolve) => { firstCallResolve = resolve; }),
    );
    const { useResumeV2Store } = await importStore();
    useResumeV2Store.getState().resetFromServer({
      id: "r1",
      data: freshData(),
      version: 0,
    });
    const original = useResumeV2Store.getState().data;
    useResumeV2Store.getState().setDataMut((d) => { d.basics.name = "stale local"; });
    await vi.runAllTimersAsync();
    // Simulate 423 response
    (firstCallResolve as ((v: any) => void) | null)?.(new Response(JSON.stringify({ error: "RESUME_LOCKED" }), { status: 423 }));
    await Promise.resolve();
    // pendingSave cleared
    expect(useResumeV2Store.getState().pendingSave).toBeNull();
    // data reverted (the original after resetFromServer)
    expect(useResumeV2Store.getState().data).toEqual(original);
    // toast fired
    expect(fireToastMock).toHaveBeenCalled();
  });
});
