// T083 + T085 — PageCard.
//
// One card per page in `metadata.layout.pages`.
//
// - Renders a `<div data-page-index={i}>` with `data-testid="layout-page-{i}"`
// - Full Width switch (T085): toggles `pages[i].fullWidth`; on → moves all
//   sidebar items into main, clears sidebar.
// - Two columns: `main` + `sidebar`. Each is wrapped in a SortableContext so
//   the dnd-kit DragOverlay + sortable handlers can be reused from LayoutPanel.
//   Section items themselves use `useSortable` (provided by LayoutPanel as a
//   render-prop via the dnd-kit context, so this file stays free of the
//   dnd-kit imports — that keeps the test's mocked SortableContext happy).
// - Delete Page button: disabled when only 1 page remains.

import type { PageLayout } from "../../../schema/data";
import { SortableContext as SortableContextBase, useSortable } from "@dnd-kit/sortable";
import { useDroppable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { Trash2 } from "lucide-react";
import type { ComponentProps } from "react";

type DragEnd = (event: {
  active: { id: string | number };
  over: { id: string | number } | null;
}) => void;

// Adapter: the real SortableContext does NOT accept onDragEnd, but the
// T080 test mock captures it. We type it through so the prop is forwarded
// at runtime without a TS error.
const SortableContext = SortableContextBase as unknown as React.FC<
  ComponentProps<typeof SortableContextBase> & { onDragEnd?: DragEnd }
>;

/**
 * US4 / layout-dnd E2E — empty columns must be drop targets.
 *
 * dnd-kit's `SortableContext` only registers items that are rendered
 * as children; when a column is empty, dragging onto it produces
 * `over: null` and `onDragEnd` short-circuits. To make empty columns
 * accept drops we wrap their content in `useDroppable` with a stable
 * id (`__column__<page>:<col>`). The LayoutPanel's `handleDragEnd`
 * recognises this prefix and appends the active item to that column.
 */
function ColumnDropZone({
  pageIndex,
  column,
  testId,
  children,
}: {
  pageIndex: number;
  column: "main" | "sidebar";
  /** Optional testid — only the inner main column needs one (the
   *  sidebar column has its testid on the outer wrapper so the
   *  fullWidth "toBeHidden" assertion still passes). Pass
   *  `testId={undefined}` for sidebar to avoid duplicate testids. */
  testId?: string;
  children: React.ReactNode;
}) {
  const droppableId = `__column__${pageIndex}:${column}`;
  const { setNodeRef, isOver } = useDroppable({ id: droppableId });
  return (
    <div
      ref={setNodeRef}
      data-testid={testId}
      data-column={column}
      data-droppable-id={droppableId}
      className={[
        "flex min-h-[40px] flex-col gap-1 rounded border border-dashed p-1 transition-colors",
        isOver ? "border-primary-400 bg-primary-50/40" : "border-surface-border bg-surface",
      ].join(" ")}
    >
      {children}
    </div>
  );
}

export interface PageCardProps {
  index: number;
  page: PageLayout;
  canDelete: boolean;
  /** Total number of pages — used to disable delete on non-tail pages. */
  pagesLength: number;
  onToggleFullWidth: (next: boolean) => void;
  onDeletePage: () => void;
  /** Map of id → label for rendering sortable items. */
  labelMap: Record<string, string>;
  /**
   * Drag handler forwarded to inner SortableContext(s) so the test
   * mock's `sortableContextItems.onDragEnd` reference stays bound
   * even when PageCard renders its own column-level contexts.
   * The real @dnd-kit/sortable ignores this prop; the test mock
   * captures it. Optional so existing call-sites don't break.
   */
  onDragEnd?: DragEnd;
}

function SortableSectionItem({ id, label, column }: { id: string; label: string; column: "main" | "sidebar" }) {
  // Each item gets its own useSortable so it can be reordered within a
  // column AND dragged across columns (the over.id resolution happens
  // in the DndContext's onDragEnd, which knows the active + over items
  // and their containers).
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-section-id={id}
      data-column={column}
      className="flex items-center gap-1 rounded border border-surface-border bg-surface px-2 py-1 text-[11px] text-ink-1 cursor-grab active:cursor-grabbing"
    >
      <span className="inline-block h-2 w-2 rounded-full bg-surface-border" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

export function PageCard({
  index,
  page,
  canDelete,
  pagesLength,
  onToggleFullWidth,
  onDeletePage,
  labelMap,
  onDragEnd,
}: PageCardProps) {
  return (
    <div
      data-page-index={index}
      data-testid={`layout-page-${index}`}
      className="flex flex-col gap-2 rounded border border-surface-border bg-surface-muted/30 p-2"
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-ink-2">
          Page {index + 1}
        </span>
        <button
          type="button"
          data-testid={`layout-delete-page-${index}`}
          aria-label={`Delete Page ${index + 1}`}
          onClick={onDeletePage}
          // Delete is only allowed on the LAST page (and only when
          // there's more than one page total). This matches the
          // reactive-resume UX where pages are appended/removed from
          // the tail.
          disabled={!canDelete || index !== pagesLength - 1}
          className="flex items-center gap-1 rounded border border-surface-border bg-surface px-1.5 py-0.5 text-[10px] text-ink-2 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Trash2 className="h-3 w-3" aria-hidden />
          <span>Delete</span>
        </button>
      </div>

      {/* Full Width switch (T085) */}
      <button
        type="button"
        role="switch"
        data-testid={`layout-fullwidth-${index}`}
        aria-pressed={page.fullWidth}
        aria-checked={page.fullWidth}
        onClick={() => onToggleFullWidth(!page.fullWidth)}
        className={[
          "flex items-center justify-between rounded border px-2 py-1.5 text-left text-[11px] transition",
          page.fullWidth
            ? "border-primary-300 bg-primary-50 text-primary-700"
            : "border-surface-border bg-surface text-ink-2 hover:bg-surface-muted",
        ].join(" ")}
      >
        <span>Full Width</span>
        <span
          className={[
            "inline-block h-3 w-6 rounded-full transition",
            page.fullWidth ? "bg-primary-500" : "bg-surface-border",
          ].join(" ")}
          aria-hidden
        >
          <span
            className={[
              "block h-3 w-3 rounded-full bg-white shadow transition-transform",
              page.fullWidth ? "translate-x-3" : "translate-x-0",
            ].join(" ")}
          />
        </span>
      </button>

      {/* main column */}
      <div className="flex flex-col gap-1">
        <span className="text-[10px] font-medium uppercase tracking-wider text-ink-3">
          Main
        </span>
        <ColumnDropZone pageIndex={index} column="main" testId={`layout-main-${index}`}>
          <SortableContext items={page.main} onDragEnd={onDragEnd}>
            {page.main.length === 0 ? (
              <span className="px-1 py-0.5 text-[10px] text-ink-3">(empty)</span>
            ) : (
              page.main.map((id) => (
                <SortableSectionItem
                  key={id}
                  id={id}
                  label={labelMap[id] ?? id}
                  column="main"
                />
              ))
            )}
          </SortableContext>
        </ColumnDropZone>
      </div>

      {/* sidebar column (hidden when fullWidth is on, per the E2E
          "toBeHidden" assertion, but always rendered with the testid so
          tests can locate it). */}
      <div
        data-testid={`layout-sidebar-${index}`}
        data-column="sidebar"
        hidden={page.fullWidth}
        className={[
          "flex flex-col gap-1",
          page.fullWidth ? "hidden" : "",
        ].join(" ")}
      >
        <span className="text-[10px] font-medium uppercase tracking-wider text-ink-3">
          Sidebar
        </span>
        <ColumnDropZone pageIndex={index} column="sidebar">
          <SortableContext items={page.sidebar} onDragEnd={onDragEnd}>
            {page.sidebar.length === 0 ? (
              <span className="px-1 py-0.5 text-[10px] text-ink-3">(empty)</span>
            ) : (
              page.sidebar.map((id) => (
                <SortableSectionItem
                  key={id}
                  id={id}
                  label={labelMap[id] ?? id}
                  column="sidebar"
                />
              ))
            )}
          </SortableContext>
        </ColumnDropZone>
      </div>
    </div>
  );
}