/**
 * T112–T114, T119 — Resume v2 Zustand store (US12).
 *
 * Adds to the Wave 3 minimal store:
 *   - `original` snapshot for isDirty comparison
 *   - `isDirty` / `saving` / `lastSavedAt` / `lastError` / `hydrated`
 *   - `pendingSave: AbortController | null` for in-flight cancellation
 *   - `undoStack` / `redoStack` (max 20) — scaffold for US17
 *   - `setData(mutator)` using immer `produce`
 *   - `debouncedSave()` (500ms) + `flushSave()` + `applyServerDiff`
 *
 * Persistence flow:
 *   1. `setData` mutates `data` in-place via immer
 *   2. The same `setData` call schedules a 500ms debounce
 *   3. After 500ms, the latest data is PUT to `/api/v1/v2/resumes/{id}`
 *      with `If-Match: <version>`
 *   4. 200 → `resetFromServer(response)` updates `version` + clears `original`
 *   5. 409 → `applyServerDiff(body.latest_data, body.latest_version)` + toast
 *   6. 423 → revert + toast
 *   7. Other 4xx/5xx → store `lastError`; retry on next edit
 */
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type { ResumeDataV2, Metadata } from "../schema/data";
import { defaultResumeDataV2 } from "../schema/defaults";
import { updateResume, type ResumeV2Conflict, type ResumeV2 } from "../api";
import { fireToast } from "../editor/center/toast";

// ── types ────────────────────────────────────────────────────────────────

export interface HistoryEntry {
  /** Snapshot of data BEFORE the mutation that produced this entry. */
  data: ResumeDataV2;
  /** Server version at the time of the snapshot. */
  version: number;
  /** Unix ms when the entry was pushed. */
  at: number;
}

const DEBOUNCE_MS = 500;
const MAX_HISTORY = 20;
const HISTORY_TTL_MS = 30 * 60 * 1000; // 30 min
const HISTORY_TTL_CHECK_MS = 60 * 1000; // 60s

export interface ResumeV2Store {
  // ── core data ──
  data: ResumeDataV2;
  /** Server-provided `version` for optimistic concurrency. */
  version: number;
  /** Resume id (when hydrated from server). */
  id: string | null;

  // ── persistence state ──
  /** Last server-confirmed snapshot — used for isDirty + revert. */
  original: ResumeDataV2 | null;
  /** True when `data !== original` (deep equality via JSON for simplicity). */
  isDirty: boolean;
  /** In-flight PUT, or null. The AbortController cancels the fetch. */
  pendingSave: AbortController | null;
  /** True while a PUT is in flight (debounce expired, awaiting response). */
  saving: boolean;
  /** Unix ms of the most recent successful save. */
  lastSavedAt: number | null;
  /** Most recent error message (cleared on next success). */
  lastError: string | null;
  /** True once resetFromServer has been called. */
  hydrated: boolean;
  /** Timestamp of the most recent local edit (used to throttle / display). */
  lastEditAt: number | null;

  // ── history (US17) ──
  undoStack: HistoryEntry[];
  redoStack: HistoryEntry[];
  /** True once the 30-min idle window has elapsed; stacks are wiped. */
  historyTTLExpired: boolean;

  // ── timers (kept in state for the test-suite's fake-timer support) ──
  debounceTimer: ReturnType<typeof setTimeout> | null;
  historyTTLTimer: ReturnType<typeof setInterval> | null;

  // ── actions ──
  /** Hydrate the store from a server-side resume fetch. */
  resetFromServer: (payload: { id: string; data: ResumeDataV2; version: number }) => void;
  /** Replace the whole data document (used by debouncedSave success). */
  setData: (next: ResumeDataV2) => void;
  /**
   * Mutate data via an immer producer. Triggers debouncedSave and pushes
   * the previous snapshot onto the undo stack.
   */
  setDataMut: (mutator: (draft: ResumeDataV2) => void, opts?: { skipHistory?: boolean }) => void;
  /**
   * Patch metadata with a partial. Kept for Wave 3 callers (T049 right-
   * side panels) — routes through the same debounced-save path.
   */
  setMetadata: (patch: Partial<Metadata>) => void;

  /** Cancel the pending debounce + abort in-flight save, then PUT now. */
  flushSave: () => Promise<void>;

  /** Apply a server-confirmed diff. Used by both 409 response + SSE event. */
  applyServerDiff: (next: ResumeDataV2, version: number) => void;

  /** Pop undo stack, push current data onto redo stack, restore. */
  undo: () => void;
  /** Pop redo stack, push current data onto undo stack, restore. */
  redo: () => void;
}

// ── helpers ──────────────────────────────────────────────────────────────

function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (typeof a !== "object") return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  // JSON round-trip is sufficient for our data shape; zod-validated.
  return JSON.stringify(a) === JSON.stringify(b);
}

// ── store ────────────────────────────────────────────────────────────────

export const useResumeV2Store = create<ResumeV2Store>()(
  immer((set, get) => {
    /**
     * Internal: schedule a debounced save (500ms). Subsequent calls
     * cancel the previous timer. The actual PUT runs once the timer
     * fires.
     */
    const scheduleDebouncedSave = () => {
      const existing = get().debounceTimer;
      if (existing) clearTimeout(existing);
      const timer = setTimeout(() => {
        // Snapshot the current state and run the PUT.
        const { id, data, version, pendingSave } = get();
        if (!id) return;
        if (pendingSave) {
          // Already in-flight — let the in-flight call complete; the
          // next debounce will pick up newer changes.
          return;
        }
        void runSave(id, data, version);
      }, DEBOUNCE_MS);
      set((s) => {
        s.debounceTimer = timer;
      });
    };

    /**
     * Internal: T168 — start the 30-min TTL watchdog. Runs at
     * HISTORY_TTL_CHECK_MS (60s) and wipes both stacks when the user
     * has been idle longer than HISTORY_TTL_MS. Idempotent.
     */
    const startHistoryTTL = () => {
      const existing = get().historyTTLTimer;
      if (existing) return;
      const handle = setInterval(() => {
        const s = get();
        if (!s.lastEditAt) return;
        if (Date.now() - s.lastEditAt <= HISTORY_TTL_MS) return;
        if (s.undoStack.length === 0 && s.redoStack.length === 0) {
          set((st) => { st.historyTTLExpired = true; });
          return;
        }
        set((st) => {
          st.undoStack = [];
          st.redoStack = [];
          st.historyTTLExpired = true;
        });
      }, HISTORY_TTL_CHECK_MS);
      set((s) => { s.historyTTLTimer = handle; });
    };

    /**
     * Internal: perform the PUT. Cancels any previous in-flight save
     * (we only allow one outstanding save at a time).
     */
    const runSave = async (
      id: string,
      data: ResumeDataV2,
      version: number,
      signal?: AbortSignal,
    ) => {
      const controller = new AbortController();
      set((s) => {
        s.saving = true;
        s.pendingSave = controller;
        s.lastError = null;
      });
      try {
        // Tie our internal signal to any externally-provided one.
        if (signal) {
          if (signal.aborted) controller.abort();
          else signal.addEventListener("abort", () => controller.abort(), { once: true });
        }
        const res = await updateResume(id, version, { data });
        // Did the user abort mid-flight?
        if (controller.signal.aborted) return;
        // 409 path: `updateResume` returns a ResumeV2Conflict shape.
        if (res && typeof res === "object" && "error" in res && (res as ResumeV2Conflict).error === "VERSION_CONFLICT") {
          const conflict = res as ResumeV2Conflict;
          fireToast("其他设备刚保存了更新,正在刷新数据");
          get().applyServerDiff(conflict.latest_data as ResumeDataV2, conflict.latest_version);
          return;
        }
        // 200 path
        const ok = res as ResumeV2;
        // REQ-032 layout-dnd fix: do NOT reset s.data to ok.data here.
        // The PUT response's `data` reflects whatever the server stored
        // from THIS specific PUT, but the local `s.data` may already
        // contain LATER edits made while this PUT was in flight (the
        // debounce path skips a new PUT while `pendingSave` is set, so
        // those later edits are not yet on the server). Replacing
        // `s.data` with `ok.data` would clobber those pending edits
        // with the older server snapshot — observed in the locked
        // T081 layout-dnd Playwright test where the drag's
        // main→sidebar move was reverted to the pre-drag layout.
        //
        // Instead, just bump the version + mark our local data as the
        // new authoritative baseline. The next debounce will pick up
        // any further edits and ship them.
        set((s) => {
          s.version = ok.version;
          s.original = JSON.parse(JSON.stringify(s.data));
          s.isDirty = !deepEqual(s.data, s.original);
          s.lastSavedAt = Date.now();
        });
      } catch (err: unknown) {
        // 423 LOCKED: revert data + toast
        const message = err instanceof Error ? err.message : String(err);
        if (message.includes("423")) {
          fireToast("已锁定");
          // Revert to the original snapshot.
          set((s) => {
            if (s.original) {
              s.data = JSON.parse(JSON.stringify(s.original));
            }
            s.isDirty = false;
          });
        } else if (message.includes("409")) {
          // Defensive: in case `updateResume` throws instead of returning
          // the conflict envelope. Trigger applyServerDiff via a follow-up
          // GET. We do not block here.
          fireToast("版本冲突,正在刷新");
          try {
            const { getResume } = await import("../api");
            const fresh = await getResume(id);
            get().applyServerDiff(fresh.data as ResumeDataV2, fresh.version);
          } catch {
            /* swallow — the next edit will retry */
          }
        } else {
          set((s) => {
            s.lastError = message;
          });
          fireToast("保存失败,将稍后重试");
        }
      } finally {
        set((s) => {
          s.saving = false;
          s.pendingSave = null;
        });
      }
    };

    return {
      data: JSON.parse(JSON.stringify(defaultResumeDataV2)),
      version: 0,
      id: null,
      original: null,
      isDirty: false,
      pendingSave: null,
      saving: false,
      lastSavedAt: null,
      lastError: null,
      hydrated: false,
      lastEditAt: null,
      undoStack: [],
      redoStack: [],
      historyTTLExpired: false,
      debounceTimer: null,
      historyTTLTimer: null,

      resetFromServer: ({ id, data, version }) => {
        set((s) => {
          s.id = id;
          s.data = JSON.parse(JSON.stringify(data));
          s.original = JSON.parse(JSON.stringify(data));
          s.version = version;
          s.hydrated = true;
          s.isDirty = false;
          s.lastError = null;
          // Clear history on a fresh hydration.
          s.undoStack = [];
          s.redoStack = [];
          s.historyTTLExpired = false;
        });
        // T168 — start the 30-min TTL watchdog on first hydration.
        startHistoryTTL();
      },

      setData: (next) => {
        set((s) => {
          const prev = s.data;
          s.undoStack.push({
            data: JSON.parse(JSON.stringify(prev)),
            version: s.version,
            at: Date.now(),
          });
          if (s.undoStack.length > MAX_HISTORY) s.undoStack.shift();
          s.redoStack = [];
          s.data = next;
          s.lastEditAt = Date.now();
          s.isDirty = !s.original || !deepEqual(s.data, s.original);
        });
        scheduleDebouncedSave();
      },

      setDataMut: (mutator, opts) => {
        set((s) => {
          const prev = s.data;
          if (!opts?.skipHistory) {
            // Push a history snapshot BEFORE applying the mutation.
            s.undoStack.push({
              data: JSON.parse(JSON.stringify(prev)),
              version: s.version,
              at: Date.now(),
            });
            if (s.undoStack.length > MAX_HISTORY) s.undoStack.shift();
            s.redoStack = [];
            s.historyTTLExpired = false;
          }
          // Apply the mutator against the immer-wrapped sub-draft
          // (`s.data` is a lazy draft proxy provided by zustand-immer,
          // so mutating it inside `set((s) => ...)` is tracked). We
          // intentionally do NOT call `produce(s.data, ...)` here — that
          // creates a separate immer scope and discards the result,
          // which is the bug fixed in this revision (see
          // lessons-learned.md 2026-06-26 032 setDataMut-immer bug).
          mutator(s.data as ResumeDataV2);
          s.lastEditAt = Date.now();
          s.isDirty = !s.original || !deepEqual(s.data, s.original);
        });
        scheduleDebouncedSave();
      },

      setMetadata: (patch) => {
        get().setDataMut((draft) => {
          draft.metadata = {
            ...draft.metadata,
            ...patch,
            design: patch.design
              ? {
                  ...draft.metadata.design,
                  ...patch.design,
                  colors: patch.design.colors
                    ? { ...draft.metadata.design.colors, ...patch.design.colors }
                    : draft.metadata.design.colors,
                  level: patch.design.level
                    ? { ...draft.metadata.design.level, ...patch.design.level }
                    : draft.metadata.design.level,
                }
              : draft.metadata.design,
            typography: patch.typography
              ? {
                  body: patch.typography.body
                    ? { ...draft.metadata.typography.body, ...patch.typography.body }
                    : draft.metadata.typography.body,
                  heading: patch.typography.heading
                    ? { ...draft.metadata.typography.heading, ...patch.typography.heading }
                    : draft.metadata.typography.heading,
                }
              : draft.metadata.typography,
            page: patch.page
              ? { ...draft.metadata.page, ...patch.page }
              : draft.metadata.page,
          } as Metadata;
        });
      },

      flushSave: async () => {
        // Cancel the debounce; run the save now.
        const t = get().debounceTimer;
        if (t) {
          clearTimeout(t);
          set((s) => { s.debounceTimer = null; });
        }
        const { id, data, version, pendingSave } = get();
        if (!id) return;
        if (pendingSave) {
          // Cancel the in-flight; the response will be discarded.
          pendingSave.abort();
        }
        await runSave(id, data, version);
      },

      applyServerDiff: (next, version) => {
        set((s) => {
          if (version === s.version && s.original && deepEqual(next, s.original)) {
            return; // no-op
          }
          if (s.pendingSave) {
            // Toast is fired by the caller; here we just merge.
          } else {
            fireToast("已自动加载其他设备的更新");
          }
          s.data = JSON.parse(JSON.stringify(next));
          s.original = JSON.parse(JSON.stringify(next));
          s.version = version;
          s.isDirty = false;
        });
      },

      // T166 — pop undo stack, push current data onto redo stack, restore.
      undo: () => {
        const s = get();
        if (s.historyTTLExpired || s.undoStack.length === 0) {
          fireToast("历史已过期", "warn");
          return;
        }
        const top = s.undoStack[s.undoStack.length - 1];
        const current = JSON.parse(JSON.stringify(s.data));
        set((st) => {
          st.redoStack.push({
            data: current,
            version: st.version,
            at: Date.now(),
          });
          if (st.redoStack.length > MAX_HISTORY) st.redoStack.shift();
          st.undoStack = st.undoStack.slice(0, -1);
          st.data = JSON.parse(JSON.stringify(top.data));
          st.version = top.version;
          st.lastEditAt = Date.now();
          st.isDirty = !st.original || !deepEqual(st.data, st.original);
        });
        scheduleDebouncedSave();
      },

      // T167 — pop redo stack, push current data onto undo stack, restore.
      redo: () => {
        const s = get();
        if (s.historyTTLExpired || s.redoStack.length === 0) {
          fireToast("历史已过期", "warn");
          return;
        }
        const top = s.redoStack[s.redoStack.length - 1];
        const current = JSON.parse(JSON.stringify(s.data));
        set((st) => {
          st.undoStack.push({
            data: current,
            version: st.version,
            at: Date.now(),
          });
          if (st.undoStack.length > MAX_HISTORY) st.undoStack.shift();
          st.redoStack = st.redoStack.slice(0, -1);
          st.data = JSON.parse(JSON.stringify(top.data));
          st.version = top.version;
          st.lastEditAt = Date.now();
          st.isDirty = !st.original || !deepEqual(st.data, st.original);
        });
        scheduleDebouncedSave();
      },
    };
  }),
);
