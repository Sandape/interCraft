import { DndContext, closestCenter, type DragEndEvent } from "@dnd-kit/core";
import type { ResumeDataV2 } from "../../schema/data";
import { useResumeV2Store } from "../../store";
import { PageCard } from "./layout/PageCard";

export interface LayoutPanelProps {
  data?: ResumeDataV2;
  onChange?: (next: ResumeDataV2) => void;
}

type Column = "main" | "sidebar";

function cloneData(data: ResumeDataV2): ResumeDataV2 {
  return JSON.parse(JSON.stringify(data)) as ResumeDataV2;
}

function buildLabelMap(data: ResumeDataV2): Record<string, string> {
  const labels: Record<string, string> = {
    summary: data.summary.title || "Summary",
  };
  for (const [id, section] of Object.entries(data.sections)) {
    labels[id] = section.title || id;
  }
  for (const section of data.customSections) {
    labels[section.id] = section.title || section.id;
  }
  return labels;
}

function findSection(
  data: ResumeDataV2,
  sectionId: string,
): { pageIndex: number; column: Column; index: number } | null {
  for (let pageIndex = 0; pageIndex < data.metadata.layout.pages.length; pageIndex += 1) {
    const page = data.metadata.layout.pages[pageIndex];
    const mainIndex = page.main.indexOf(sectionId);
    if (mainIndex >= 0) return { pageIndex, column: "main", index: mainIndex };
    const sidebarIndex = page.sidebar.indexOf(sectionId);
    if (sidebarIndex >= 0) return { pageIndex, column: "sidebar", index: sidebarIndex };
  }
  return null;
}

function parseColumnDrop(id: string): { pageIndex: number; column: Column } | null {
  const match = /^__column__(\d+):(main|sidebar)$/.exec(id);
  if (!match) return null;
  return { pageIndex: Number(match[1]), column: match[2] as Column };
}

export function LayoutPanel(props: LayoutPanelProps = {}): JSX.Element {
  const storeData = useResumeV2Store((s) => s.data);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const data = props.data ?? storeData;
  const pages = data.metadata.layout.pages;
  const labelMap = buildLabelMap(data);

  const commit = (mutator: (draft: ResumeDataV2) => void) => {
    if (props.data && props.onChange) {
      const next = cloneData(props.data);
      mutator(next);
      props.onChange(next);
      return;
    }
    setDataMut(mutator);
  };

  const setSidebarWidth = (value: number) => {
    const clamped = Math.min(50, Math.max(10, value));
    commit((draft) => {
      draft.metadata.layout.sidebarWidth = clamped;
    });
  };

  const addPage = () => {
    commit((draft) => {
      draft.metadata.layout.pages.push({ fullWidth: false, main: [], sidebar: [] });
    });
  };

  const deletePage = (pageIndex: number) => {
    commit((draft) => {
      if (draft.metadata.layout.pages.length <= 1) return;
      const removed = draft.metadata.layout.pages[pageIndex];
      const targetIndex = Math.max(0, pageIndex - 1);
      draft.metadata.layout.pages[targetIndex].main.push(...removed.main);
      draft.metadata.layout.pages[targetIndex].sidebar.push(...removed.sidebar);
      draft.metadata.layout.pages.splice(pageIndex, 1);
    });
  };

  const toggleFullWidth = (pageIndex: number, next: boolean) => {
    commit((draft) => {
      const page = draft.metadata.layout.pages[pageIndex];
      page.fullWidth = next;
      if (next && page.sidebar.length > 0) {
        page.main.push(...page.sidebar);
        page.sidebar = [];
      }
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const activeId = String(event.active.id);
    const overId = event.over ? String(event.over.id) : "";
    if (!overId || activeId === overId) return;

    commit((draft) => {
      const origin = findSection(draft, activeId);
      if (!origin) return;

      const columnDrop = parseColumnDrop(overId);
      const overSection = columnDrop ? null : findSection(draft, overId);
      const target = columnDrop
        ? {
            pageIndex: columnDrop.pageIndex,
            column: columnDrop.column,
            index: draft.metadata.layout.pages[columnDrop.pageIndex][columnDrop.column].length,
          }
        : overSection;
      if (!target) return;

      const originItems = draft.metadata.layout.pages[origin.pageIndex][origin.column];
      const [moved] = originItems.splice(origin.index, 1);
      if (!moved) return;

      const targetItems = draft.metadata.layout.pages[target.pageIndex][target.column];
      const insertAt =
        origin.pageIndex === target.pageIndex &&
        origin.column === target.column &&
        origin.index < target.index
          ? target.index - 1
          : target.index;
      targetItems.splice(Math.max(0, insertAt), 0, moved);
    });
  };

  return (
    <div data-testid="layout-panel" className="flex h-full flex-col gap-3 overflow-y-auto p-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-3">Layout</div>
        <button
          type="button"
          data-testid="layout-add-page"
          onClick={addPage}
          className="h-7 rounded border border-surface-border bg-surface px-2 text-xs text-ink-1 hover:bg-surface-muted"
        >
          Add Page
        </button>
      </div>

      <section className="rounded border border-surface-border bg-surface-base p-3">
        <label className="block space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-ink-2">Sidebar width</span>
            <span className="text-xs font-medium text-ink-1">{data.metadata.layout.sidebarWidth}%</span>
          </div>
          <input
            type="range"
            min={10}
            max={50}
            step={1}
            data-testid="layout-sidebar-width"
            value={data.metadata.layout.sidebarWidth}
            onChange={(event) => setSidebarWidth(Number(event.target.value))}
            className="w-full accent-primary-500"
          />
        </label>
      </section>

      <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div className="space-y-2">
          {pages.map((page, index) => (
            <PageCard
              key={index}
              index={index}
              page={page}
              canDelete={pages.length > 1}
              pagesLength={pages.length}
              onToggleFullWidth={(next) => toggleFullWidth(index, next)}
              onDeletePage={() => deletePage(index)}
              labelMap={labelMap}
              onDragEnd={(event) => handleDragEnd(event as DragEndEvent)}
            />
          ))}
        </div>
      </DndContext>
    </div>
  );
}

export default LayoutPanel;
