// REQ-034 US2 — ExperienceSectionList (left-rail items list + add-button).
//
// Renders the experience section's `items[]` as a sortable list of rows.
// Each row exposes three inline actions:
//   - edit      → openDialog({ type: "experience.update", itemId })
//   - duplicate → setDataMut pushes a deep-copy with fresh ids; no dialog
//                 open (REQ-034 US2 AC-10-revised)
//   - delete    → setDataMut splices by id
//
// Drag-reorder of items is dnd-kit (AC-09), with the `data-dnd-context`
// attribute set to `"items"` so it can be distinguished from the layout
// column drag (AC-09b). Keyboard reorder uses the same dnd-kit
// KeyboardSensor — Space picks up, ArrowUp/Down moves, Space drops
// (AC-09c, WCAG 2.1.1).
//
// Rendering is intentionally text-node only (no `dangerouslySetInnerHTML`)
// so user-input fields cannot inject script tags (AC-12 + AC-12b).

import { useId, useRef } from "react";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Pencil, Copy, Trash2, Plus, GripVertical } from "lucide-react";
import { useResumeV2Store } from "../../store";
import { useDialogStore, type DialogSpec } from "../dialogs/DialogHost";
import type { ExperienceItem, RoleItem, ResumeDataV2 } from "../../schema/data";

// ── constants ──────────────────────────────────────────────────────────────

// AC-08b: drag-reorder batches within this window — N consecutive
// onDragEnd events collapse into a single undoStack entry.
const DRAG_BATCH_MS = 500;

// ── helpers ────────────────────────────────────────────────────────────────

function deepCloneItem(src: ExperienceItem): ExperienceItem {
  return {
    id: `e-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
    hidden: src.hidden,
    company: src.company,
    position: src.position,
    location: src.location,
    period: src.period,
    website: {
      url: src.website.url,
      label: src.website.label,
      inlineLink: src.website.inlineLink,
    },
    description: src.description,
    roles: src.roles.map(
      (r): RoleItem => ({
        id: `r-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}-${r.id}`,
        position: r.position,
        period: r.period,
        description: r.description,
      }),
    ),
  };
}

function freshItem(): ExperienceItem {
  return {
    id: `e-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
    hidden: false,
    company: "",
    position: "",
    location: "",
    period: "",
    website: { url: "", label: "", inlineLink: false },
    description: "",
    roles: [],
  };
}

// ── component ──────────────────────────────────────────────────────────────

export interface ExperienceSectionListProps {
  /** Section id, typically "experience". */
  sectionId?: string;
}

export function ExperienceSectionList({
  sectionId = "experience",
}: ExperienceSectionListProps): JSX.Element {
  const items = useResumeV2Store(
    (s) => (s.data.sections[sectionId as keyof ResumeDataV2["sections"]] as { items: ExperienceItem[] }).items,
  );
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const openDialog = useDialogStore((s) => s.openDialog);
  const titleId = useId();

  // AC-08b — drag-reorder batching. The first onDragEnd in a 500ms
  // window commits the pre-drag snapshot to undoStack; subsequent
  // onDragEnd events within the window apply the visual reorder with
  // skipHistory:true. After 500ms of silence the inProgress flag
  // clears and the next drag opens a new batch.
  const dragBatchRef = useRef<{
    timer: ReturnType<typeof setTimeout> | null;
    inProgress: boolean;
  }>({ timer: null, inProgress: false });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleAdd = () => {
    // Push a fresh empty item, then open the update dialog on it.
    let newId = "";
    setDataMut((draft) => {
      const sec = draft.sections[sectionId as keyof typeof draft.sections];
      if (!sec || !("items" in sec)) return;
      const arr = sec.items as unknown as ExperienceItem[];
      const next = freshItem();
      newId = next.id;
      arr.push(next);
    });
    if (newId) {
      const spec: DialogSpec = {
        type: "experience.update",
        payload: { sectionId, itemId: newId },
      };
      openDialog(spec);
    }
  };

  const handleEdit = (itemId: string) => {
    const spec: DialogSpec = {
      type: "experience.update",
      payload: { sectionId, itemId },
    };
    openDialog(spec);
  };

  const handleDuplicate = (itemId: string) => {
    setDataMut((draft) => {
      const sec = draft.sections[sectionId as keyof typeof draft.sections];
      if (!sec || !("items" in sec)) return;
      const arr = sec.items as unknown as ExperienceItem[];
      const idx = arr.findIndex((i) => i.id === itemId);
      if (idx < 0) return;
      const clone = deepCloneItem(arr[idx]);
      arr.splice(idx + 1, 0, clone);
    });
  };

  const handleDelete = (itemId: string) => {
    setDataMut((draft) => {
      const sec = draft.sections[sectionId as keyof typeof draft.sections];
      if (!sec || !("items" in sec)) return;
      const arr = sec.items as unknown as ExperienceItem[];
      const idx = arr.findIndex((i) => i.id === itemId);
      if (idx >= 0) arr.splice(idx, 1);
    });
  };

  const handleDragEnd = (e: DragEndEvent) => {
    const activeId = String(e.active.id);
    const overId = e.over ? String(e.over.id) : null;
    if (!overId || activeId === overId) return;
    // AC-09b: short-circuit if the over container is the layout
    // dnd-context (we don't actually mount that here, but defensive
    // guard for future test scenarios that simulate cross-context drag).
    const overCtx = e.over?.data?.current?.droppableContainer?.dataset
      ?.dndContext;
    if (overCtx && overCtx !== "items" && overCtx !== sectionId) {
      return;
    }
    // AC-08b: only the FIRST onDragEnd in a 500ms window pushes a
    // history snapshot (pre-drag state). Subsequent onDragEnd events
    // apply the visual reorder with skipHistory:true so 5 rapid drags
    // collapse into 1 undoStack entry.
    const isFirstInBatch = !dragBatchRef.current.inProgress;
    setDataMut(
      (draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as ExperienceItem[];
        const oldIdx = arr.findIndex((i) => i.id === activeId);
        const newIdx = arr.findIndex((i) => i.id === overId);
        if (oldIdx < 0 || newIdx < 0) return;
        if (oldIdx === newIdx) return;
        // AC-08: preserve the id set (splice a single element — never
        // reassign the array reference, so dnd-kit's SortableContext
        // cache and any external observers see a stable draft).
        const [movedItem] = arr.splice(oldIdx, 1);
        arr.splice(newIdx, 0, movedItem);
      },
      isFirstInBatch ? undefined : { skipHistory: true },
    );
    if (isFirstInBatch) {
      dragBatchRef.current.inProgress = true;
    }
    // Reset / start the 500ms idle window.
    if (dragBatchRef.current.timer) {
      clearTimeout(dragBatchRef.current.timer);
    }
    dragBatchRef.current.timer = setTimeout(() => {
      dragBatchRef.current.inProgress = false;
      dragBatchRef.current.timer = null;
    }, DRAG_BATCH_MS);
  };

  return (
    <div
      data-testid="experience-section-list"
      data-dnd-context="items"
      data-section-key={sectionId}
      aria-labelledby={titleId}
      className="mt-2 space-y-2"
    >
      <div className="flex items-center justify-between">
        <span id={titleId} className="text-[10px] font-semibold uppercase tracking-wide text-ink-3">
          Experience items ({items.length})
        </span>
        <button
          type="button"
          aria-label="添加 Experience 条目"
          onClick={handleAdd}
          data-testid="experience-add-item"
          className="flex items-center gap-1 rounded bg-primary-500 px-2 py-0.5 text-[10px] text-white"
        >
          <Plus className="h-3 w-3" aria-hidden />
          <span>Add</span>
        </button>
      </div>
      {items.length === 0 && (
        <div className="rounded border border-dashed border-surface-border p-2 text-[10px] text-ink-3" data-testid="experience-section-list-empty">
          暂无条目,点击 + Add 新增
        </div>
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={items.map((i) => i.id)}
          strategy={verticalListSortingStrategy}
        >
          <ul className="space-y-1" data-testid="experience-section-list-items">
            {items.map((item) => (
              <SortableItemRow
                key={item.id}
                item={item}
                onEdit={handleEdit}
                onDuplicate={handleDuplicate}
                onDelete={handleDelete}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
      {/* Test-only reorder trigger: hidden buttons that synthesise a
          dnd-kit DragEndEvent and feed it through `handleDragEnd` (the
          same code path dnd-kit invokes), so AC-08b tests can fire N
          consecutive drag-end events without depending on dnd-kit's
          pointer/keyboard sensor plumbing in jsdom. */}
      <div data-testid="experience-section-list-test-triggers" style={{ display: "none" }}>
        <button
          type="button"
          data-testid="experience-section-list-test-reorder-e3-e1"
          onClick={() =>
            handleDragEnd({
              active: { id: "e3" } as { id: string | number },
              over: { id: "e1" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >e3→e1</button>
        <button
          type="button"
          data-testid="experience-section-list-test-reorder-e1-e2"
          onClick={() =>
            handleDragEnd({
              active: { id: "e1" } as { id: string | number },
              over: { id: "e2" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >e1→e2</button>
        <button
          type="button"
          data-testid="experience-section-list-test-reorder-e2-e3"
          onClick={() =>
            handleDragEnd({
              active: { id: "e2" } as { id: string | number },
              over: { id: "e3" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >e2→e3</button>
        <button
          type="button"
          data-testid="experience-section-list-test-reorder-e3-e2"
          onClick={() =>
            handleDragEnd({
              active: { id: "e3" } as { id: string | number },
              over: { id: "e2" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >e3→e2</button>
        <button
          type="button"
          data-testid="experience-section-list-test-reorder-e1-e3"
          onClick={() =>
            handleDragEnd({
              active: { id: "e1" } as { id: string | number },
              over: { id: "e3" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >e1→e3</button>
      </div>
    </div>
  );
}

// ── row ────────────────────────────────────────────────────────────────────

interface SortableItemRowProps {
  item: ExperienceItem;
  onEdit: (id: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
}

function SortableItemRow({
  item,
  onEdit,
  onDuplicate,
  onDelete,
}: SortableItemRowProps): JSX.Element {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  // AC-12: hidden items get a strikethrough/gray visual cue but their
  // text content is still rendered as plain text nodes (no innerHTML).
  const subtitle =
    item.roles.length > 0
      ? `${item.roles.length} roles`
      : item.position || "—";
  return (
    <li
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-testid={`experience-item-row-${item.id}`}
      data-item-id={item.id}
      data-hidden={item.hidden ? "true" : "false"}
      className={[
        "flex items-center gap-1 rounded border border-surface-border bg-surface-base px-2 py-1 text-[11px] text-ink-1",
        item.hidden ? "opacity-60 line-through" : "",
      ].join(" ")}
    >
      <GripVertical
        className="h-3 w-3 shrink-0 text-ink-3"
        aria-hidden
      />
      <div className="flex-1 truncate">
        <div className="truncate font-medium">{item.company || "(未命名公司)"}</div>
        <div className="truncate text-[10px] text-ink-3">{subtitle}</div>
      </div>
      <div className="flex shrink-0 items-center gap-0.5">
        <button
          type="button"
          aria-label="编辑"
          data-testid={`experience-item-edit-${item.id}`}
          onClick={(e) => {
            e.stopPropagation();
            onEdit(item.id);
          }}
          className="rounded p-0.5 text-ink-2 hover:bg-surface-muted"
        >
          <Pencil className="h-3 w-3" aria-hidden />
        </button>
        <button
          type="button"
          aria-label="复制"
          data-testid={`experience-item-duplicate-${item.id}`}
          onClick={(e) => {
            e.stopPropagation();
            onDuplicate(item.id);
          }}
          className="rounded p-0.5 text-ink-2 hover:bg-surface-muted"
        >
          <Copy className="h-3 w-3" aria-hidden />
        </button>
        <button
          type="button"
          aria-label="删除"
          data-testid={`experience-item-delete-${item.id}`}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(item.id);
          }}
          className="rounded p-0.5 text-red-600 hover:bg-red-50"
        >
          <Trash2 className="h-3 w-3" aria-hidden />
        </button>
      </div>
    </li>
  );
}
