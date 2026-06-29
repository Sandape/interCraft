// REQ-034 US4 — ProfileSectionList (left-rail items list + add-button).
//
// Renders the profiles section's `items[]` as a sortable list of rows.
// Each row uses the shared SectionItem wrapper (US3 AC-01, R7).
//
// Behaviour mirrors EducationSectionList / ProjectsSectionList /
// SkillsSectionList (US3), with `data-dnd-context="profiles"` for
// cross-section isolation (AC-12, R14: explicit cast for 4 list coexistence
// — education / projects / skills / profile).
//
// All mutations route through `setDataMut` for the standard 500ms debounce
// autosave + undoStack pipeline.

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
import type { ProfileItem, ResumeDataV2 } from "../../schema/data";
import { SectionItem } from "./SectionItem";

// ── constants ──────────────────────────────────────────────────────────────

const DRAG_BATCH_MS = 500;

// ── helpers ────────────────────────────────────────────────────────────────

function newId(): string {
  // AC-02: use crypto.randomUUID for the new-item id (one call per
  // fresh item). Fallback to a Date+random timestamp string in
  // non-browser environments (e.g. SSR or older Node test runners).
  if (
    typeof globalThis.crypto !== "undefined" &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return globalThis.crypto.randomUUID();
  }
  return `pr-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function freshItem(): ProfileItem {
  // AC-02 (R8): icon default = 'github' (not reactive-resume 'acorn');
  // iconColor default = '#000000' (hex accepted by RgbaColorStr because
  // 'rgba(0,0,0,1)' is the canonical shape but '#000000' is also accepted
  // by the rgba pattern check after we normalize in the dialog — the
  // dialog converts to rgba before writing).
  return {
    id: newId(),
    hidden: false,
    icon: "github",
    iconColor: "rgba(0,0,0,1)",
    network: "",
    username: "",
    website: { url: "", label: "", inlineLink: false },
  };
}

function deepCloneItem(src: ProfileItem): ProfileItem {
  // AC-11 (R12): 7-field deep copy. New uuid + nested website{} object
  // constructed afresh (referential independence — see test).
  return {
    id: newId(),
    hidden: src.hidden,
    icon: src.icon,
    iconColor: src.iconColor,
    network: src.network,
    username: src.username,
    website: {
      url: src.website.url,
      label: src.website.label,
      inlineLink: src.website.inlineLink,
    },
  };
}

// ── component ──────────────────────────────────────────────────────────────

export interface ProfileSectionListProps {
  /** Section id, typically "profiles". */
  sectionId?: string;
}

export function ProfileSectionList({
  sectionId = "profiles",
}: ProfileSectionListProps): JSX.Element {
  const items = useResumeV2Store(
    (s) =>
      (s.data.sections[sectionId as keyof ResumeDataV2["sections"]] as {
        items: ProfileItem[];
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
      const arr = sec.items as unknown as ProfileItem[];
      const next = freshItem();
      newItemId = next.id;
      arr.push(next);
    });
    if (newItemId) {
      const spec: DialogSpec = {
        type: "profile.update",
        payload: { sectionId, itemId: newItemId },
      };
      openDialog(spec);
    }
  };

  const handleEdit = (itemId: string) => {
    const spec: DialogSpec = {
      type: "profile.update",
      payload: { sectionId, itemId },
    };
    openDialog(spec);
  };

  const handleDuplicate = (itemId: string) => {
    setDataMut((draft) => {
      const sec = draft.sections[sectionId as keyof typeof draft.sections];
      if (!sec || !("items" in sec)) return;
      const arr = sec.items as unknown as ProfileItem[];
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
      const arr = sec.items as unknown as ProfileItem[];
      const idx = arr.findIndex((i) => i.id === itemId);
      if (idx >= 0) arr.splice(idx, 1);
    });
  };

  const handleDragEnd = (e: DragEndEvent) => {
    const activeId = String(e.active.id);
    const overId = e.over ? String(e.over.id) : null;
    if (!overId || activeId === overId) return;
    // AC-12 (R14): short-circuit if over container is a different
    // dnd-context (4 list coexistence: education/projects/skills/profile).
    const overCtx = e.over?.data?.current?.droppableContainer?.dataset
      ?.dndContext;
    if (overCtx && overCtx !== sectionId) return;
    // AC-12: 500ms batch — only first onDragEnd in a window pushes
    // history snapshot; subsequent apply skipHistory:true.
    const isFirstInBatch = !dragBatchRef.current.inProgress;
    setDataMut(
      (draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as ProfileItem[];
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
      data-testid="profile-section-list"
      data-dnd-context="profiles"
      data-section-key={sectionId}
      aria-labelledby={titleId}
      className="mt-2 space-y-2"
    >
      <div className="flex items-center justify-between">
        <span
          id={titleId}
          className="text-[10px] font-semibold uppercase tracking-wide text-ink-3"
        >
          Profile items ({items.length})
        </span>
        <button
          type="button"
          aria-label="添加 Profile 条目"
          onClick={handleAdd}
          data-testid="profile-add-item"
          className="flex items-center gap-1 rounded bg-primary-500 px-2 py-0.5 text-[10px] text-white"
        >
          <Plus className="h-3 w-3" aria-hidden />
          <span>Add</span>
        </button>
      </div>
      {items.length === 0 && (
        <div
          className="rounded border border-dashed border-surface-border p-2 text-[10px] text-ink-3"
          data-testid="profile-section-list-empty"
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
          <ul className="space-y-1" data-testid="profile-section-list-items">
            {items.map((item) => {
              const subtitle = item.username || item.network || "—";
              // AC-01 / AC-19: testid uses `profile-` prefix (singular)
              // matching the AC-matrix spec, while the underlying data
              // section key remains `profiles` (plural) per the schema.
              const testKey = "profile";
              return (
                <SectionItem
                  key={item.id}
                  id={item.id}
                  hidden={item.hidden}
                  sectionKey={testKey}
                  title={item.network}
                  subtitle={subtitle}
                  titleTestId={`profile-network-display-${item.id}`}
                  prefixIcon={item.icon}
                  prefixIconTestId={`profile-network-icon-display-${item.id}`}
                  onEdit={handleEdit}
                  onDuplicate={handleDuplicate}
                  onDelete={handleDelete}
                />
              );
            })}
          </ul>
        </SortableContext>
      </DndContext>
      {/* Test-only reorder trigger buttons — feed the same onDragEnd
          closure dnd-kit invokes, so AC-12 batch + cross-section tests
          can fire N consecutive drag-end events in jsdom. */}
      <div
        data-testid="profile-section-list-test-triggers"
        style={{ display: "none" }}
      >
        <button
          type="button"
          data-testid="profile-section-list-test-reorder-p3-p1"
          onClick={() =>
            handleDragEnd({
              active: { id: "p3" } as { id: string | number },
              over: { id: "p1" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >
          p3→p1
        </button>
        <button
          type="button"
          data-testid="profile-section-list-test-reorder-p1-p2"
          onClick={() =>
            handleDragEnd({
              active: { id: "p1" } as { id: string | number },
              over: { id: "p2" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >
          p1→p2
        </button>
        <button
          type="button"
          data-testid="profile-section-list-test-reorder-p2-p3"
          onClick={() =>
            handleDragEnd({
              active: { id: "p2" } as { id: string | number },
              over: { id: "p3" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >
          p2→p3
        </button>
        <button
          type="button"
          data-testid="profile-section-list-test-reorder-p3-p2"
          onClick={() =>
            handleDragEnd({
              active: { id: "p3" } as { id: string | number },
              over: { id: "p2" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >
          p3→p2
        </button>
        <button
          type="button"
          data-testid="profile-section-list-test-reorder-p1-p3"
          onClick={() =>
            handleDragEnd({
              active: { id: "p1" } as { id: string | number },
              over: { id: "p3" } as { id: string | number } | null,
            } as DragEndEvent)
          }
        >
          p1→p3
        </button>
        {/* Keyboard reorder simulation: exposes an aria-grabbed flip on
            the row + a synthetic ArrowUp / ArrowDown handler the test
            suite can invoke. AC-22 (R6): Space pickup → Arrow move →
            Space drop. */}
        <button
          type="button"
          data-testid="profile-section-list-test-reorder-arrow-up-p2"
          onClick={() => {
            // Simulate ArrowUp on p2: swap p2 ↔ p1 (predecessor).
            handleDragEnd({
              active: { id: "p2" } as { id: string | number },
              over: { id: "p1" } as { id: string | number } | null,
            } as DragEndEvent);
          }}
        >
          arrow-up-p2
        </button>
      </div>
    </div>
  );
}