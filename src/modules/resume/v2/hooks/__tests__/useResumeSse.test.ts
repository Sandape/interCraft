/**
 * T109 — useResumeSse.test.ts (smoke test for SSE hook)
 *
 * Verifies:
 *   1. Hook opens an EventSource on the right URL
 *   2. On `resume.updated` event, store's `applyServerDiff` is called
 *   3. Unsubscribe closes the EventSource
 *
 * The EventSource is mocked because jsdom does not implement
 * Server-Sent Events. The mock implements the small subset of the
 * browser API the hook relies on: addEventListener, removeEventListener,
 * close, and a way to inject events.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

// Mock EventSource BEFORE the hook module is loaded
type Listener = (ev: any) => void;
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  withCredentials = false;
  readyState = 0;
  private listeners: Record<string, Listener[]> = {};
  closed = false;
  constructor(url: string, _init?: unknown) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, listener: Listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  removeEventListener(type: string, listener: Listener) {
    const arr = this.listeners[type];
    if (!arr) return;
    const i = arr.indexOf(listener);
    if (i >= 0) arr.splice(i, 1);
  }
  close() {
    this.closed = true;
  }
  /** test helper: dispatch an event */
  __fire(type: string, data: unknown) {
    const ev = { type, data: typeof data === "string" ? data : JSON.stringify(data) };
    for (const l of this.listeners[type] || []) l(ev);
  }
}

const mockApplyServerDiff = vi.fn();
const mockResetFromServer = vi.fn();
const mockGetState = vi.fn(() => ({ applyServerDiff: mockApplyServerDiff }));

vi.stubGlobal("EventSource", MockEventSource);

vi.mock("../../store", () => ({
  useResumeV2Store: {
    getState: () => ({
      applyServerDiff: mockApplyServerDiff,
      resetFromServer: mockResetFromServer,
      version: 0,
      data: {},
    }),
  },
}));

describe("useResumeSse", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    mockApplyServerDiff.mockReset();
    mockResetFromServer.mockReset();
    mockGetState.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("opens an EventSource on mount and closes on unmount", async () => {
    const { useResumeSse } = await import("../useResumeSse");
    const { unmount } = renderHook(() => useResumeSse("r1"));
    expect(MockEventSource.instances).toHaveLength(1);
    const es = MockEventSource.instances[0];
    expect(es.url).toContain("/api/v1/v2/resumes/events");
    expect(es.url).toContain("resume_id=r1");
    act(() => { unmount(); });
    expect(es.closed).toBe(true);
  });

  it("dispatches resume.updated to applyServerDiff", async () => {
    const { useResumeSse } = await import("../useResumeSse");
    renderHook(() => useResumeSse("r1"));
    const es = MockEventSource.instances[0];
    act(() => {
      es.__fire("resume.updated", {
        type: "resume.updated",
        resume_id: "r1",
        version: 9,
        user_id: "u1",
        updated_at: "2026-06-25T10:00:00Z",
        action: "updated",
      });
    });
    expect(mockApplyServerDiff).toHaveBeenCalledWith(
      expect.anything(),
      9,
    );
  });

  it("ignores events for a different resume_id", async () => {
    const { useResumeSse } = await import("../useResumeSse");
    renderHook(() => useResumeSse("r1"));
    const es = MockEventSource.instances[0];
    act(() => {
      es.__fire("resume.updated", {
        type: "resume.updated",
        resume_id: "r-other",
        version: 9,
        user_id: "u1",
        updated_at: "2026-06-25T10:00:00Z",
        action: "updated",
      });
    });
    expect(mockApplyServerDiff).not.toHaveBeenCalled();
  });
});
