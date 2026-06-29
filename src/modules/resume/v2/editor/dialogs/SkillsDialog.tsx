// REQ-034 US3 — SkillsDialog.
//
// Edits a single `SkillItem`. Field surface (per AC-06, R1 + R3):
//   - 7 top-level inputs: icon / iconColor (color picker) / name /
//     proficiency (free text) / level (slider 0..5) / hidden
//   - keywords[]: string[] (add / remove / drag-reorder with 500ms batch)
//   - NO `website` field (AC-13b)
//
// Behavioural contract mirrors EducationDialog (US2 pattern, R12):
//   - No dialog-local form state.
//   - Closing (ESC / backdrop / Cancel) is a CANCEL.
//   - `level` slider step=1; `level=0` shows "Hidden" label
//     (reactive-resume `Number(field.state.value) === 0 ? 'Hidden' : '${value} / 5'`,
//     AC-10 R3). Level=0 still writes to the store (independent of `hidden`).

import { useState, useId, useRef } from "react";
import { Modal } from "@/components/ui/Modal";
import { useResumeV2Store } from "../../store";
import { fireToast } from "../center/toast";
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
import { GripVertical, X } from "lucide-react";
import type {
  SkillItem,
  RgbaColorStr,
  ResumeDataV2,
} from "../../schema/data";

// ── constants ──────────────────────────────────────────────────────────────

const TEXT_MAX = 64;
const PROFICIENCY_MAX = 32;
const KEYWORD_MAX = 64;
const LEVEL_MIN = 0;
const LEVEL_MAX = 5;
const DRAG_BATCH_MS = 500;

const NEW_ID = (): string =>
  `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

// ── dialog props ───────────────────────────────────────────────────────────

export interface SkillsDialogProps {
  onClose: () => void;
  sectionId: string;
  itemId: string;
}

// ── item lookup ────────────────────────────────────────────────────────────

function findItem(
  data: ResumeDataV2,
  sectionId: string,
  itemId: string,
): SkillItem | undefined {
  const sec = data.sections[sectionId as keyof typeof data.sections];
  if (!sec || !("items" in sec)) return undefined;
  const items = sec.items as unknown as SkillItem[];
  if (!itemId) return items[items.length - 1];
  return items.find((i) => i.id === itemId);
}

// ── field writers ──────────────────────────────────────────────────────────

function useItemWriter(sectionId: string) {
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  return {
    updateItem: (
      itemId: string,
      mutator: (draft: SkillItem) => void,
    ) => {
      setDataMut((draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as SkillItem[];
        const target = arr.find((i) => i.id === itemId);
        if (target) mutator(target);
      });
    },
  };
}

// ── component ──────────────────────────────────────────────────────────────

export function SkillsDialog({
  onClose,
  sectionId,
  itemId,
}: SkillsDialogProps): JSX.Element {
  const item = useResumeV2Store((s) => findItem(s.data, sectionId, itemId));
  const { updateItem } = useItemWriter(sectionId);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const [levelError, setLevelError] = useState<string | null>(null);
  const titleId = useId();

  const dragBatchRef = useRef<{
    timer: ReturnType<typeof setTimeout> | null;
    inProgress: boolean;
  }>({ timer: null, inProgress: false });

  if (!item) {
    setTimeout(onClose, 0);
    return (
      <Modal open onClose={onClose} title="Skills" size="lg">
        <div data-testid="skills-dialog-missing" className="p-4 text-xs text-ink-3">
          找不到该条目,正在关闭…
        </div>
      </Modal>
    );
  }

  const targetId = item.id;

  const setItem = (mutator: (draft: SkillItem) => void) =>
    updateItem(targetId, mutator);

  const setText = (field: keyof SkillItem, value: string) => {
    setItem((d) => {
      (d as unknown as Record<string, string>)[field] = value;
    });
  };

  const setLevel = (raw: string) => {
    // AC-10 R3: slider step=1; number input must still reject non-integers.
    const trimmed = raw.trim();
    if (trimmed === "") {
      setLevelError("level 不能为空");
      fireToast("level 不能为空", "warn");
      return;
    }
    // Allow "3" or "3.0" (whole) but reject "3.7" (non-integer).
    const n = Number(trimmed);
    if (!Number.isFinite(n)) {
      setLevelError("level 必须是数字");
      fireToast("level 必须是数字", "warn");
      return;
    }
    if (!Number.isInteger(n)) {
      setLevelError("level 必须是整数 (0..5)");
      fireToast("level 必须是整数 (0..5)", "warn");
      return;
    }
    if (n < LEVEL_MIN || n > LEVEL_MAX) {
      setLevelError(`level 必须在 ${LEVEL_MIN}..${LEVEL_MAX} 之间`);
      fireToast(`level 必须在 ${LEVEL_MIN}..${LEVEL_MAX} 之间`, "warn");
      return;
    }
    setLevelError(null);
    setItem((d) => {
      d.level = n;
    });
  };

  const addKeyword = () => {
    setItem((d) => {
      d.keywords.push("");
    });
  };

  const removeKeyword = (idx: number) => {
    setItem((d) => {
      if (idx >= 0 && idx < d.keywords.length) d.keywords.splice(idx, 1);
    });
  };

  const updateKeyword = (idx: number, value: string) => {
    setItem((d) => {
      if (idx >= 0 && idx < d.keywords.length) d.keywords[idx] = value;
    });
  };

  const reorderKeywords = (activeId: string, overId: string) => {
    if (activeId === overId) return;
    const isFirstInBatch = !dragBatchRef.current.inProgress;
    setDataMut(
      (draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as SkillItem[];
        const target = arr.find((i) => i.id === targetId);
        if (!target) return;
        // For string[] arrays the dnd-kit id IS the index (stringified).
        const oldIdx = Number(activeId);
        const newIdx = Number(overId);
        if (
          !Number.isInteger(oldIdx) ||
          !Number.isInteger(newIdx) ||
          oldIdx < 0 ||
          newIdx < 0 ||
          oldIdx >= target.keywords.length ||
          newIdx >= target.keywords.length ||
          oldIdx === newIdx
        )
          return;
        const [moved] = target.keywords.splice(oldIdx, 1);
        target.keywords.splice(newIdx, 0, moved);
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

  const levelLabel =
    item.level === 0 ? "Hidden" : `${item.level} / ${LEVEL_MAX}`;

  return (
    <Modal
      open
      onClose={onClose}
      title="Skills"
      description="名称 / 熟练度 / 等级 / 关键词"
      size="lg"
    >
      <div
        data-testid="skills-dialog"
        aria-labelledby={titleId}
        className="space-y-3"
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">
              Icon (lucide key)
            </span>
            <input
              type="text"
              value={item.icon}
              maxLength={TEXT_MAX}
              placeholder="wrench"
              data-testid="skills-icon"
              onChange={(e) => setText("icon", e.target.value.slice(0, TEXT_MAX))}
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">
              Icon color
            </span>
            <input
              type="color"
              value={rgbaToHex(item.iconColor)}
              data-testid="skills-icon-color"
              onChange={(e) => {
                const rgba = hexToRgba(e.target.value);
                setItem((d) => {
                  d.iconColor = rgba;
                });
              }}
              className="h-7 w-full rounded border border-surface-border bg-surface-base"
            />
          </label>
        </div>
        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wide text-ink-3">
            名称
          </span>
          <input
            type="text"
            value={item.name}
            maxLength={TEXT_MAX}
            placeholder="(例 React)"
            data-testid="skills-name"
            onChange={(e) => setText("name", e.target.value.slice(0, TEXT_MAX))}
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wide text-ink-3">
            Proficiency (自由文本, 例 Fluent / Native)
          </span>
          <input
            type="text"
            value={item.proficiency}
            maxLength={PROFICIENCY_MAX}
            placeholder="Fluent"
            data-testid="skills-proficiency"
            onChange={(e) =>
              setText("proficiency", e.target.value.slice(0, PROFICIENCY_MAX))
            }
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
          />
        </label>
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">
              Level (0..5)
            </span>
            <span
              data-testid="skills-level-label"
              className="text-[11px] font-medium text-ink-2"
            >
              {levelLabel}
            </span>
          </div>
          <input
            type="range"
            min={LEVEL_MIN}
            max={LEVEL_MAX}
            step={1}
            value={item.level}
            data-testid="skills-level"
            onChange={(e) => setLevel(e.target.value)}
            className="w-full accent-primary-500"
          />
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">
              Or enter level as number
            </span>
            <input
              type="number"
              min={LEVEL_MIN}
              max={LEVEL_MAX}
              step={1}
              value={item.level}
              data-testid="skills-level-input"
              onChange={(e) => setLevel(e.target.value)}
              aria-invalid={levelError ? true : undefined}
              className={[
                "w-full rounded border bg-surface-base px-2 py-1 text-xs text-ink-1",
                levelError ? "border-red-500" : "border-surface-border",
              ].join(" ")}
            />
            {levelError && (
              <span
                role="alert"
                data-testid="skills-level-error"
                className="text-[10px] text-red-600"
              >
                {levelError}
              </span>
            )}
          </label>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={item.hidden}
            data-testid="skills-hidden"
            onChange={(e) => setText("hidden", e.target.checked ? "true" : "false")}
            className="accent-primary-500"
          />
          <span>隐藏该条目</span>
        </label>

        {/* keywords[] container */}
        <div
          className="mt-2 rounded border border-surface-border p-2"
          data-testid="skills-keywords"
          data-dnd-context="skills"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-3">
              关键词 ({item.keywords.length})
            </span>
            <button
              type="button"
              onClick={addKeyword}
              data-testid="skills-keywords-add"
              className="rounded bg-primary-500 px-2 py-1 text-xs text-white"
            >
              + 添加关键词
            </button>
          </div>
          {item.keywords.length === 0 && (
            <div className="text-xs text-ink-3" data-testid="skills-keywords-empty">
              暂无关键词。点击"+ 添加关键词"。
            </div>
          )}
          <KeywordsList
            keywords={item.keywords}
            onReorder={reorderKeywords}
            onUpdate={updateKeyword}
            onRemove={removeKeyword}
          />
        </div>

        <div className="flex justify-end gap-2 border-t border-surface-border pt-3">
          <button
            type="button"
            onClick={onClose}
            data-testid="skills-cancel"
            className="rounded border border-surface-border px-3 py-1 text-xs text-ink-2"
          >
            关闭
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── color helpers ──────────────────────────────────────────────────────────

function rgbaToHex(rgba: RgbaColorStr): string {
  // Accept "rgba(r,g,b,a)" or "rgb(r,g,b)" — extract r/g/b.
  const m = rgba.match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (!m) return "#000000";
  const r = Number(m[1]);
  const g = Number(m[2]);
  const b = Number(m[3]);
  const hex = (n: number) => n.toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}

function hexToRgba(hex: string): RgbaColorStr {
  const m = hex.replace("#", "").match(/^([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (!m) return "rgba(0,0,0,1)";
  const r = parseInt(m[1], 16);
  const g = parseInt(m[2], 16);
  const b = parseInt(m[3], 16);
  return `rgba(${r},${g},${b},1)`;
}

// ── keywords list (dnd-kit) ────────────────────────────────────────────────

interface KeywordsListProps {
  keywords: string[];
  onReorder: (activeId: string, overId: string) => void;
  onUpdate: (idx: number, value: string) => void;
  onRemove: (idx: number) => void;
}

function KeywordsList({
  keywords,
  onReorder,
  onUpdate,
  onRemove,
}: KeywordsListProps): JSX.Element {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (e: DragEndEvent) => {
    const activeId = String(e.active.id);
    const overId = e.over ? String(e.over.id) : null;
    if (!overId || activeId === overId) return;
    onReorder(activeId, overId);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={keywords.map((_, i) => String(i))}
        strategy={verticalListSortingStrategy}
      >
        <ul className="space-y-1" data-testid="skills-keywords-list">
          {keywords.map((k, i) => (
            <SortableKeywordRow
              key={i}
              idx={i}
              value={k}
              onUpdate={onUpdate}
              onRemove={onRemove}
            />
          ))}
        </ul>
        <div data-testid="skills-test-reorder-triggers" style={{ display: "none" }}>
          <button
            type="button"
            data-testid="skills-test-reorder-2-0"
            onClick={() => onReorder("2", "0")}
          >2→0</button>
          <button
            type="button"
            data-testid="skills-test-reorder-0-1"
            onClick={() => onReorder("0", "1")}
          >0→1</button>
          <button
            type="button"
            data-testid="skills-test-reorder-1-2"
            onClick={() => onReorder("1", "2")}
          >1→2</button>
          <button
            type="button"
            data-testid="skills-test-reorder-2-1"
            onClick={() => onReorder("2", "1")}
          >2→1</button>
          <button
            type="button"
            data-testid="skills-test-reorder-0-2"
            onClick={() => onReorder("0", "2")}
          >0→2</button>
        </div>
      </SortableContext>
    </DndContext>
  );
}

interface SortableKeywordRowProps {
  idx: number;
  value: string;
  onUpdate: (idx: number, value: string) => void;
  onRemove: (idx: number) => void;
}

function SortableKeywordRow({
  idx,
  value,
  onUpdate,
  onRemove,
}: SortableKeywordRowProps): JSX.Element {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: String(idx) });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <li
      ref={setNodeRef}
      style={style}
      data-testid={`skills-keyword-row-${idx}`}
      data-keyword-idx={idx}
      {...attributes}
      {...listeners}
      className="flex items-center gap-1 rounded border border-surface-border bg-surface-base px-2 py-1"
    >
      <GripVertical className="h-3 w-3 shrink-0 text-ink-3" aria-hidden />
      <input
        type="text"
        value={value}
        maxLength={KEYWORD_MAX}
        placeholder="关键词"
        data-testid={`skills-keyword-input-${idx}`}
        onChange={(e) => onUpdate(idx, e.target.value.slice(0, KEYWORD_MAX))}
        className="flex-1 rounded border border-surface-border bg-surface-base px-2 py-1 text-[11px] text-ink-1"
      />
      <button
        type="button"
        aria-label="删除关键词"
        data-testid={`skills-keyword-remove-${idx}`}
        onClick={() => onRemove(idx)}
        className="rounded p-1 text-red-600 hover:bg-red-50"
      >
        <X className="h-3 w-3" aria-hidden />
      </button>
    </li>
  );
}

export { NEW_ID as NEW_SKILL_ID };