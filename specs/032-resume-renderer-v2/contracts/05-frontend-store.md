# Frontend Store Contract

**Module**: `frontend/src/modules/resume/v2/store/`
**State library**: Zustand 4.x + immer 10.x
**Consumers**: BuilderShell, SectionPanel, SettingsPanel, dock, dialogs.

---

## 1. Store shape

```ts
interface ResumeV2Store {
  // Data
  resume: ResumeV2Full | null               // includes version + metadata
  original: ResumeV2Full | null              // last server-confirmed snapshot
  isDirty: boolean                          // resume !== original
  lastSavedAt: number | null                // epoch ms

  // History (FR-101..103)
  undoStack: HistoryEntry[]                 // max depth 20
  redoStack: HistoryEntry[]                 // cleared on any new edit
  lastEditAt: number | null                 // for 30-min TTL

  // Concurrency
  pendingSave: AbortController | null       // in-flight PUT
  saving: boolean
  lastError: string | null

  // Hydration
  hydrated: boolean

  // Mutations
  setData: (mutator: (draft: Draft<ResumeDataV2>) => void) => void
  setMetadata: (patch: Partial<Metadata>) => void
  resetFromServer: (next: ResumeV2Full) => void
  applyServerDiff: (next: ResumeDataV2, version: number) => void

  // History
  undo: () => void
  redo: () => void
  pruneHistory: () => void                  // called by TTL timer

  // Persistence
  flushSave: () => Promise<void>            // called by beforeunload
  debouncedSave: () => void                 // 500ms debounced
}
```

---

## 2. History entry

```ts
interface HistoryEntry {
  ts: number                                // epoch ms at mutation time
  data: ResumeDataV2                        // full snapshot (cheap; < 50KB typical)
  label?: string                            // "edit Experience", "change template"
}
```

Depth cap: 20. When the stack is full, the oldest entry is dropped on push
(per FR-101).

---

## 3. Mutation contract

`setData(mutator)`:

1. If `lastEditAt` is null OR `Date.now() - lastEditAt > 30 * 60 * 1000`,
   clear both stacks (TTL per FR-103).
2. Run `mutator(draftResume.data)` on a draft.
3. Push current `data` to `undoStack`.
4. Clear `redoStack`.
5. Set `lastEditAt = Date.now()`.
6. Trigger `debouncedSave()`.

`undo()`:

1. Pop `undoStack`.
2. Push current `data` to `redoStack`.
3. Set `data = popped.data`.
4. Trigger `debouncedSave()`.

`redo()`: symmetric.

`resetFromServer(next)`:

1. Replace `resume = next`, `original = next`.
2. Clear both stacks.
3. Clear `pendingSave`.
4. Set `lastSavedAt = Date.now()`.

`applyServerDiff(next, version)`:

1. If `next.version > resume.version` AND no `pendingSave`: silently replace.
2. If `next.version > resume.version` AND `pendingSave` exists: toast
   "其他设备刚保存了更新，正在刷新数据"; do `resetFromServer(next)`.
3. If `next.version === resume.version`: no-op.

---

## 4. Persistence

### 4.1 Debounced save

`debouncedSave()` schedules a `setTimeout(flushSave, 500)`. Subsequent calls
reset the timer. When `flushSave` fires:

1. Cancel any existing `pendingSave` (AbortController).
2. Create a new AbortController.
3. PUT `/api/v1/v2/resumes/{id}` with header `If-Match: ${resume.version}`.
4. On 200: `resetFromServer(responseBody)`.
5. On 409: `applyServerDiff(body.latest_data, body.latest_version)`.
6. On 423: toast "已锁定" + revert last change.
7. On other 4xx/5xx: keep changes, surface error toast, retry on next edit.

### 4.2 beforeunload

```ts
window.addEventListener('beforeunload', (e) => {
  if (isDirty) {
    e.preventDefault()
    e.returnValue = ''  // required for Chrome to show prompt
    void store.getState().flushSave()       // best-effort; browser may abort
  }
})
```

### 4.3 SSE integration

```ts
useEffect(() => {
  if (!resumeId) return
  return subscribeResumeEvents(resumeId, (event) => {
    if (event.type === 'resume.updated') {
      void api.getResume(resumeId).then(resume => {
        store.getState().applyServerDiff(resume.data, resume.version)
      })
    }
    ...
  })
}, [resumeId])
```

---

## 5. Selectors

Pre-built selectors for components (memoized via `zustand/shallow`):

```ts
useTemplate()           => TemplateId
useSections()           => ResumeDataV2['sections']
useCustomSections()     => ResumeDataV2['customSections']
useMetadata()           => ResumeDataV2['metadata']
useIsDirty()            => boolean
useCanUndo()            => boolean
useCanRedo()            => boolean
useHistoryTTLExpired()  => boolean             // computed from lastEditAt
```

---

## 6. Hydration lifecycle

```
mount                       unmount
  │                            │
  ├─ api.getResume(id)         │
  │    ↓                       │
  │  resetFromServer(snapshot) │
  │                            │
  ├─ edit...                   │
  ├─ edit... (debounced save)  │
  ├─ SSE: resume.updated       │
  │    ↓                       │
  │  applyServerDiff(...)      │
  │                            │
  └─ beforeunload → flushSave  ┘
```

---

## 7. Test seam

The store is created with `createResumeV2Store()` factory so tests can build an
isolated instance per case:

```ts
const store = createResumeV2Store()
store.getState().setData(d => { d.basics.name = 'Test' })
expect(store.getState().resume?.data.basics.name).toBe('Test')
```

Network calls are abstracted behind `apiClient` so unit tests inject a mock.
Integration tests in `tests/e2e/032-*/` exercise the real backend.