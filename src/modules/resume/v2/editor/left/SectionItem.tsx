// REQ-034 US3 — Shared SectionItem wrapper (list-row primitive).
//
// This component is the **single** list-row primitive shared by
// EducationSectionList / ProjectsSectionList / SkillsSectionList (R7).
// Each row exposes three inline actions: edit / duplicate / delete,
// plus a drag handle for items-level reorder.
//
// Why a shared wrapper vs 3 inlined row components?
//   - Visual consistency: hidden=true strikethrough + grey-out is
//     identical across sections (US2 AC-12-revised pattern, AC-04c/05c/06c)
//   - Reduced drift: 3 inline actions are wired identically across the
//     three sections, so a future US5 / US6 SectionList can re-use this
//     without re-implementing the action surface.
//   - testid / accessibility convention is centralised (screen readers
//     see "Edit / Duplicate / Delete" with consistent aria-label).
//
// Notes (R13):
//   - This file lives at `src/modules/resume/v2/editor/left/SectionItem.tsx`
//     (alongside SectionList) — the spec explicitly forbids shadows in
//     `dialogs/*.ts` (L008). It is the SINGLE SectionItem path on disk.
//
// Behaviour:
//   - The drag handle is provided by the parent SectionList's dnd-kit
//     context (we do NOT mount a DndContext here). The SectionList is
//     responsible for routing onDragEnd to the items array.
//   - `subtitle` is rendered as a text node only — never via
//     `dangerouslySetInnerHTML` (US2 AC-12 pattern → XSS escaping).
//   - `hidden=true` rows render as a faded/strikethrough row that is
//     STILL in the DOM (per AC-04c/05c/06c + US2 AC-12-revised).

import { GripVertical, Pencil, Copy, Trash2 } from "lucide-react";
import {
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type React from "react";

// ── props ───────────────────────────────────────────────────────────────────

export interface SectionItemRowProps {
  /** Unique id of the item being rendered (becomes the dnd-kit id). */
  id: string;
  /** Whether the item is hidden in the published resume. */
  hidden: boolean;
  /** Section key, e.g. "education" | "projects" | "skills". */
  sectionKey: string;
  /** Primary line of text, e.g. school name / project name / skill name. */
  title: string;
  /** Secondary line (period / level / role count). */
  subtitle: string;
  /** Optional testid for the title text node — defaults to
   *  `${sectionKey}-name-display` (matching AC-04c/05c/06c assertions). */
  titleTestId?: string;
  /** Handlers — typically `(id) => openDialog({...})` etc. */
  onEdit: (id: string) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
}

// ── component ───────────────────────────────────────────────────────────────

export function SectionItem({
  id,
  hidden,
  sectionKey,
  title,
  subtitle,
  titleTestId,
  onEdit,
  onDuplicate,
  onDelete,
}: SectionItemRowProps): JSX.Element {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-testid={`${sectionKey}-item-row-${id}`}
      data-item-id={id}
      data-section-key={sectionKey}
      data-hidden={hidden ? "true" : "false"}
      className={[
        "flex items-center gap-1 rounded border border-surface-border bg-surface-base px-2 py-1 text-[11px] text-ink-1",
        hidden ? "opacity-60 line-through" : "",
      ].join(" ")}
    >
      <GripVertical className="h-3 w-3 shrink-0 text-ink-3" aria-hidden />
      <div className="flex-1 truncate">
        <div
          className="truncate font-medium"
          data-testid={titleTestId ?? `${sectionKey}-name-display`}
        >
          {title || "(未命名)"}
        </div>
        <div className="truncate text-[10px] text-ink-3">{subtitle}</div>
      </div>
      <div className="flex shrink-0 items-center gap-0.5">
        <button
          type="button"
          aria-label="编辑"
          data-testid={`${sectionKey}-item-edit-${id}`}
          onClick={(e) => {
            e.stopPropagation();
            onEdit(id);
          }}
          className="rounded p-0.5 text-ink-2 hover:bg-surface-muted"
        >
          <Pencil className="h-3 w-3" aria-hidden />
        </button>
        <button
          type="button"
          aria-label="复制"
          data-testid={`${sectionKey}-item-duplicate-${id}`}
          onClick={(e) => {
            e.stopPropagation();
            onDuplicate(id);
          }}
          className="rounded p-0.5 text-ink-2 hover:bg-surface-muted"
        >
          <Copy className="h-3 w-3" aria-hidden />
        </button>
        <button
          type="button"
          aria-label="删除"
          data-testid={`${sectionKey}-item-delete-${id}`}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(id);
          }}
          className="rounded p-0.5 text-red-600 hover:bg-red-50"
        >
          <Trash2 className="h-3 w-3" aria-hidden />
        </button>
      </div>
    </li>
  );
}