// REQ-034 US5 — InterestsSectionList (left-rail items list + add-button).
//
// Renders the interests section's `items[]` as a sortable list of rows.
// Each row uses the shared SectionItem wrapper (US3 AC-01, R7).
//
// `data-dnd-context="interests"` for cross-section isolation
// (AC-04b: 11 list coexistence).
//
// InterestItem has 4 non-id fields: `icon / iconColor / name / keywords[]`.

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
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Plus } from "lucide-react";
import { useResumeV2Store } from "../../store";
import { useDialogStore, type DialogSpec } from "../dialogs/DialogHost";
import type { InterestItem, ResumeDataV2 } from "../../schema/data";
import { SectionItem } from "./SectionItem";

// ── constants ──────────────────────────────────────────────────────────────

const DRAG_BATCH_MS = 500;

// ── helpers ────────────────────────────────────────────────────────────────

function newId(): string {
  if (
    typeof globalThis.crypto !== "undefined" &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return globalThis.crypto.randomUUID();
  }
  return `i-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function freshItem(): InterestItem {
  return {
    id: newId(),
    hidden: false,
    icon: "heart",
    iconColor: "rgba(0,0,0,1)",
    name: "",
    keywords: [],
  };
}

function deepCloneItem(src: InterestItem): InterestItem {
  return {
    id: newId(),
    hidden: src.hidden,
    icon: src.icon,
    iconColor: src.iconColor,
    name: src.name,
    keywords: src.keywords.slice(),
  };
}

// ── component ──────────────────────────────────────────────────────────────

export interface InterestsSectionListProps {
  /** Section id, typically "interests". */
  sectionId?: string;
}

export function InterestsSectionList({
  sectionId = "interests",
}: InterestsSectionListProps): JSX.Element {
  const items = useResumeV2Store(
    (s) =>
      (s.data.sections[sectionId as keyof ResumeDataV2["sections"]] as {
        items: InterestItem[];
      }).items,
  );
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const openDialog = useDialogStore((s) => s.openDialog);
  const titleId = useId();

  const dragBatchRef = useRef<{
    timer: ReturnType<typeof setTimeout> | null;
    inProgress: boolean;
  }>({ timer: null, inProgress: false });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleAdd = () => {
    let newItemId = "";
    setDataMut((draft) => {
      const sec = draft.sections[sectionId as keyof typeof draft.sections];
      if (!sec || !("items" in sec)) return;
      const arr = sec.items as unknown as InterestItem[];
      const next = freshItem();
      newItemId = next.id;
      arr.push(next);
    });
    if (newItemId) {
      const spec: DialogSpec = {
        type: "interests.update",
        payload: { sectionId, itemId: newItemId },
      };
      openDialog(spec);
    }
  };

  const handleEdit = (itemId: string) => {
    const spec: DialogSpec = {
      type: "interests.update",
      payload: { sectionId, itemId },
    };
    openDialog(spec);
  };

  const handleDuplicate = (itemId: string) => {
    setDataMut((draft) => {
      const sec = draft.sections[sectionId as keyof typeof draft.sections];
      if (!sec || !("items" in sec)) return;
      const arr = sec.items as unknown as InterestItem[];
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
      const arr = sec.items as unknown as InterestItem[];
      const idx = arr.findIndex((i) => i.id === itemId);
      if (idx >= 0) arr.splice(idx, 1);
    });
  };

  const handleDragEnd = (e: DragEndEvent) => {
    const activeId = String(e.active.id);
    const overId = e.over ? String(e.over.id) : null;
    if (!overId || activeId === overId) return;
    const overCtx = e.over?.data?.current?.droppableContainer?.dataset
      ?.dndContext;
    if (overCtx && overCtx !== sectionId) return;
    const isFirstInBatch = !dragBatchRef.current.inProgress;
    setDataMut(
      (draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as InterestItem[];
        const oldIdx = arr.findIndex((i) => i.id === activeId);
        const newIdx = arr.findIndex((i) => i.id === overId);
        if (oldIdx < 0 || newIdx < 0 || oldIdx === newIdx) return;
        const [movedItem] = arr.splice(oldIdx, 1);
        arr.splice(newIdx, 0, movedItem);
      },
      isFirstInBatch ? undefined : { skipHistory: true },
    );
    if (isFirstInBatch) dragBatchRef.current.inProgress = true;
    if (dragBatchRef.current.timer) clearTimeout(dragBatchRef.current.timer);
    dragBatchRef.current.timer = setTimeout(() => {
      dragBatchRef.current.inProgress = false;
      dragBatchRef.current.timer = null;
    }, DRAG_BATCH_MS);
  };

  return (
    <div
      data-testid="interests-section-list"
      data-dnd-context="interests"
      data-section-key={sectionId}
      aria-labelledby={titleId}
      className="mt-2 space-y-2"
    >
      <div className="flex items-center justify-between">
        <span
          id={titleId}
          className="text-[10px] font-semibold uppercase tracking-wide text-ink-3"
        >
          Interests items ({items.length})
        </span>
        <button
          type="button"
          aria-label="添加 Interests 条目"
          onClick={handleAdd}
          data-testid="interests-add-item"
          className="flex items-center gap-1 rounded bg-primary-500 px-2 py-0.5 text-[10px] text-white"
        >
          <Plus className="h-3 w-3" aria-hidden />
          <span>Add</span>
        </button>
      </div>
      {items.length === 0 && (
        <div
          className="rounded border border-dashed border-surface-border p-2 text-[10px] text-ink-3"
          data-testid="interests-section-list-empty"
        >
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
          <ul className="space-y-1" data-testid="interests-section-list-items">
            {items.map((item) => {
              const subtitle =
                item.keywords.length > 0
                  ? `${item.keywords.length} keywords`
                  : "—";
              return (
                <SectionItem
                  key={item.id}
                  id={item.id}
                  hidden={item.hidden}
                  sectionKey={sectionId}
                  title={item.name}
                  subtitle={subtitle}
                  titleTestId={`interests-name-display-${item.id}`}
                  onEdit={handleEdit}
                  onDuplicate={handleDuplicate}
                  onDelete={handleDelete}
                />
              );
            })}
          </ul>
        </SortableContext>
      </DndContext>
    </div>
  );
}
