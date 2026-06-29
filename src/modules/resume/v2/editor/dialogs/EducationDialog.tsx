// REQ-034 US3 — EducationDialog.
//
// Edits a single `EducationItem`. Field surface (per AC-04):
//   - 11 top-level inputs: school / degree / area / grade / location /
//     period / website.url / website.label / website.inlineLink /
//     hidden / description
//   - courses[]: string[] (add / remove / drag-reorder with 500ms batch)
//
// Behavioural contract (US2 pattern, R12):
//   - No dialog-local form state (AC-14 / AC-08c). Every keystroke writes
//     to the store via `setDataMut`.
//   - Closing (ESC / backdrop / Cancel) is a CANCEL — DialogHost rolls
//     back every setDataMut that fired during this session via a
//     looped `undo()` (AC-15, R10/R14).
//   - `period` is a single free-form input (AC-11, R2/R11) — matches
//     reactive-resume + schema (no startDate/endDate split).
//   - URL validation reuses the US1/US2 picture-url pattern: scheme
//     whitelist `https?|tel|sms|mailto` + blacklist `javascript|vbscript|file|data`,
//     regex `u` flag for unicode/IPv6 hosts (AC-13, R4).

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
import { GripVertical, Plus, X } from "lucide-react";
import type {
  EducationItem,
  ItemWebsite,
  ResumeDataV2,
} from "../../schema/data";

// ── constants ──────────────────────────────────────────────────────────────

const TEXT_MAX = 256;
const PERIOD_MAX = 64;
const URL_MAX = 2048;
const LABEL_MAX = 64;
const DESC_MAX = 4096;
const COURSE_MAX = 256;
const DRAG_BATCH_MS = 500;

const URL_SCHEME_BLACKLIST = /^(javascript|vbscript|file|data):/iu;
const URL_SCHEME_ALLOWED = /^(https?|tel|sms|mailto):/iu;

const NEW_ID = (): string =>
  `ed-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

// ── dialog props ───────────────────────────────────────────────────────────

export interface EducationDialogProps {
  onClose: () => void;
  /** Section id, e.g. "education". */
  sectionId: string;
  /**
   * The item id being edited. If empty, behaves as a "create" session —
   * parent has already pushed an empty item, we look it up by last index.
   */
  itemId: string;
}

// ── validators ─────────────────────────────────────────────────────────────

function validateUrl(value: string): string | null {
  if (!value) return null;
  if (value.length > URL_MAX) return `链接最多 ${URL_MAX} 个字符`;
  if (URL_SCHEME_BLACKLIST.test(value)) return "链接协议被禁止";
  if (!URL_SCHEME_ALLOWED.test(value)) {
    return "链接必须以 http(s) / tel / sms / mailto 开头";
  }
  return null;
}

// ── item lookup ────────────────────────────────────────────────────────────

function findItem(
  data: ResumeDataV2,
  sectionId: string,
  itemId: string,
): EducationItem | undefined {
  const sec = data.sections[sectionId as keyof typeof data.sections];
  if (!sec || !("items" in sec)) return undefined;
  const items = sec.items as unknown as EducationItem[];
  if (!itemId) {
    return items[items.length - 1];
  }
  return items.find((i) => i.id === itemId);
}

// ── field writers ──────────────────────────────────────────────────────────

function useItemWriter(sectionId: string) {
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  return {
    updateItem: (
      itemId: string,
      mutator: (draft: EducationItem) => void,
    ) => {
      setDataMut((draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as EducationItem[];
        const target = arr.find((i) => i.id === itemId);
        if (target) mutator(target);
      });
    },
    setWebsite: (
      itemId: string,
      mutator: (draft: ItemWebsite) => void,
    ) => {
      setDataMut((draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as EducationItem[];
        const target = arr.find((i) => i.id === itemId);
        if (target) mutator(target.website);
      });
    },
  };
}

// ── component ──────────────────────────────────────────────────────────────

export function EducationDialog({
  onClose,
  sectionId,
  itemId,
}: EducationDialogProps): JSX.Element {
  const item = useResumeV2Store((s) => findItem(s.data, sectionId, itemId));
  const { updateItem, setWebsite } = useItemWriter(sectionId);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const titleId = useId();

  const dragBatchRef = useRef<{
    timer: ReturnType<typeof setTimeout> | null;
    inProgress: boolean;
  }>({ timer: null, inProgress: false });

  if (!item) {
    setTimeout(onClose, 0);
    return (
      <Modal open onClose={onClose} title="Education" size="lg">
        <div data-testid="education-dialog-missing" className="p-4 text-xs text-ink-3">
          找不到该条目,正在关闭…
        </div>
      </Modal>
    );
  }

  const targetId = item.id;

  const setItem = (mutator: (draft: EducationItem) => void) =>
    updateItem(targetId, mutator);

  const setText = (field: keyof EducationItem, value: string) => {
    setItem((d) => {
      (d as unknown as Record<string, string>)[field] = value;
    });
  };

  const onWebsiteUrlBlur = (value: string) => {
    const err = validateUrl(value);
    if (err) {
      setFieldErrors((p) => ({ ...p, "website.url": err }));
      fireToast(err, "warn");
    } else {
      setFieldErrors((p) => {
        if (!("website.url" in p)) return p;
        const next = { ...p };
        delete next["website.url"];
        return next;
      });
    }
  };

  const addCourse = () => {
    setItem((d) => {
      d.courses.push("");
    });
  };

  const removeCourse = (idx: number) => {
    setItem((d) => {
      if (idx >= 0 && idx < d.courses.length) d.courses.splice(idx, 1);
    });
  };

  const updateCourse = (idx: number, value: string) => {
    setItem((d) => {
      if (idx >= 0 && idx < d.courses.length) d.courses[idx] = value;
    });
  };

  const reorderCourses = (activeId: string, overId: string) => {
    if (activeId === overId) return;
    const isFirstInBatch = !dragBatchRef.current.inProgress;
    setDataMut(
      (draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as EducationItem[];
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
          oldIdx >= target.courses.length ||
          newIdx >= target.courses.length ||
          oldIdx === newIdx
        )
          return;
        const [moved] = target.courses.splice(oldIdx, 1);
        target.courses.splice(newIdx, 0, moved);
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
    <Modal
      open
      onClose={onClose}
      title="Education"
      description="学校 / 学位 / 专业 / 时间段 / 课程 / 描述"
      size="lg"
    >
      <div
        data-testid="education-dialog"
        aria-labelledby={titleId}
        className="space-y-3"
      >
        <input
          type="text"
          value={item.school}
          maxLength={TEXT_MAX}
          placeholder="学校"
          data-testid="education-school"
          onChange={(e) => setText("school", e.target.value.slice(0, TEXT_MAX))}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
        <input
          type="text"
          value={item.degree}
          maxLength={TEXT_MAX}
          placeholder="学位 (例 Bachelor / Master / PhD)"
          data-testid="education-degree"
          onChange={(e) => setText("degree", e.target.value.slice(0, TEXT_MAX))}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <input
            type="text"
            value={item.area}
            maxLength={TEXT_MAX}
            placeholder="专业 (例 Computer Science)"
            data-testid="education-area"
            onChange={(e) => setText("area", e.target.value.slice(0, TEXT_MAX))}
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
          />
          <input
            type="text"
            value={item.grade}
            maxLength={TEXT_MAX}
            placeholder="成绩 (例 3.8/4.0)"
            data-testid="education-grade"
            onChange={(e) => setText("grade", e.target.value.slice(0, TEXT_MAX))}
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
          />
        </div>
        <input
          type="text"
          value={item.location}
          maxLength={TEXT_MAX}
          placeholder="所在地"
          data-testid="education-location"
          onChange={(e) => setText("location", e.target.value.slice(0, TEXT_MAX))}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
        <input
          type="text"
          value={item.period}
          maxLength={PERIOD_MAX}
          placeholder="时间段 (例 2018-09 ~ 2022-06)"
          data-testid="education-period"
          onChange={(e) => setText("period", e.target.value.slice(0, PERIOD_MAX))}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">主页 URL</span>
            <input
              type="text"
              value={item.website.url}
              maxLength={URL_MAX}
              placeholder="https://...  / tel:  / mailto:"
              data-testid="education-website-url"
              aria-invalid={fieldErrors["website.url"] ? true : undefined}
              onChange={(e) =>
                setWebsite(targetId, (d) => {
                  d.url = e.target.value.slice(0, URL_MAX);
                })
              }
              onBlur={() => onWebsiteUrlBlur(item.website.url)}
              className={[
                "w-full rounded border bg-surface-base px-2 py-1 text-xs text-ink-1",
                fieldErrors["website.url"] ? "border-red-500" : "border-surface-border",
              ].join(" ")}
            />
            {fieldErrors["website.url"] && (
              <span
                role="alert"
                data-testid="education-website-url-error"
                className="text-[10px] text-red-600"
              >
                {fieldErrors["website.url"]}
              </span>
            )}
          </label>
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">主页标签</span>
            <input
              type="text"
              value={item.website.label}
              maxLength={LABEL_MAX}
              data-testid="education-website-label"
              onChange={(e) =>
                setWebsite(targetId, (d) => {
                  d.label = e.target.value.slice(0, LABEL_MAX);
                })
              }
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
          </label>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={item.website.inlineLink}
            data-testid="education-website-inline-link"
            onChange={(e) =>
              setWebsite(targetId, (d) => {
                d.inlineLink = e.target.checked;
              })
            }
            className="accent-primary-500"
          />
          <span>在公开页将 label 渲染为可点击链接</span>
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={item.hidden}
            data-testid="education-hidden"
            onChange={(e) => setText("hidden", e.target.checked ? "true" : "false")}
            className="accent-primary-500"
          />
          <span>隐藏该条目</span>
        </label>

        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wide text-ink-3">
            描述
          </span>
          <textarea
            value={item.description}
            maxLength={DESC_MAX}
            data-testid="education-description"
            onChange={(e) => setText("description", e.target.value.slice(0, DESC_MAX))}
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            rows={4}
          />
        </label>

        {/* courses[] container */}
        <div
          className="mt-2 rounded border border-surface-border p-2"
          data-testid="education-courses"
          data-dnd-context="education"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-3">
              课程 ({item.courses.length})
            </span>
            <button
              type="button"
              onClick={addCourse}
              data-testid="education-add-course"
              className="rounded bg-primary-500 px-2 py-1 text-xs text-white"
            >
              + 添加课程
            </button>
          </div>
          {item.courses.length === 0 && (
            <div className="text-xs text-ink-3" data-testid="education-courses-empty">
              暂无课程。点击"+ 添加课程"。
            </div>
          )}
          <CoursesList
            courses={item.courses}
            onReorder={reorderCourses}
            onUpdate={updateCourse}
            onRemove={removeCourse}
          />
        </div>

        <div className="flex justify-end gap-2 border-t border-surface-border pt-3">
          <button
            type="button"
            onClick={onClose}
            data-testid="education-cancel"
            className="rounded border border-surface-border px-3 py-1 text-xs text-ink-2"
          >
            关闭
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── courses list (dnd-kit) ─────────────────────────────────────────────────

interface CoursesListProps {
  courses: string[];
  onReorder: (activeId: string, overId: string) => void;
  onUpdate: (idx: number, value: string) => void;
  onRemove: (idx: number) => void;
}

function CoursesList({
  courses,
  onReorder,
  onUpdate,
  onRemove,
}: CoursesListProps): JSX.Element {
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

  // Use index-as-id for drag. dnd-kit ids are string|number; we stringify index.
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={courses.map((_, i) => String(i))}
        strategy={verticalListSortingStrategy}
      >
        <ul
          className="space-y-1"
          data-testid="education-courses-list"
        >
          {courses.map((c, i) => (
            <SortableCourseRow
              key={i}
              idx={i}
              value={c}
              onUpdate={onUpdate}
              onRemove={onRemove}
            />
          ))}
        </ul>
        {/* Test-only reorder trigger: hidden buttons that invoke
            `onReorder(active, over)` directly. */}
        <div data-testid="education-test-reorder-triggers" style={{ display: "none" }}>
          <button
            type="button"
            data-testid="education-test-reorder-2-0"
            onClick={() => onReorder("2", "0")}
          >2→0</button>
          <button
            type="button"
            data-testid="education-test-reorder-0-1"
            onClick={() => onReorder("0", "1")}
          >0→1</button>
          <button
            type="button"
            data-testid="education-test-reorder-1-2"
            onClick={() => onReorder("1", "2")}
          >1→2</button>
          <button
            type="button"
            data-testid="education-test-reorder-2-1"
            onClick={() => onReorder("2", "1")}
          >2→1</button>
          <button
            type="button"
            data-testid="education-test-reorder-0-2"
            onClick={() => onReorder("0", "2")}
          >0→2</button>
        </div>
      </SortableContext>
    </DndContext>
  );
}

interface SortableCourseRowProps {
  idx: number;
  value: string;
  onUpdate: (idx: number, value: string) => void;
  onRemove: (idx: number) => void;
}

function SortableCourseRow({
  idx,
  value,
  onUpdate,
  onRemove,
}: SortableCourseRowProps): JSX.Element {
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
      data-testid={`education-course-row-${idx}`}
      data-course-idx={idx}
      {...attributes}
      {...listeners}
      className="flex items-center gap-1 rounded border border-surface-border bg-surface-base px-2 py-1"
    >
      <GripVertical className="h-3 w-3 shrink-0 text-ink-3" aria-hidden />
      <input
        type="text"
        value={value}
        maxLength={COURSE_MAX}
        placeholder="课程名"
        data-testid={`education-course-input-${idx}`}
        onChange={(e) => onUpdate(idx, e.target.value.slice(0, COURSE_MAX))}
        className="flex-1 rounded border border-surface-border bg-surface-base px-2 py-1 text-[11px] text-ink-1"
      />
      <button
        type="button"
        aria-label="删除课程"
        data-testid={`education-course-remove-${idx}`}
        onClick={() => onRemove(idx)}
        className="rounded p-1 text-red-600 hover:bg-red-50"
      >
        <X className="h-3 w-3" aria-hidden />
      </button>
    </li>
  );
}

export { NEW_ID as NEW_EDUCATION_ID };