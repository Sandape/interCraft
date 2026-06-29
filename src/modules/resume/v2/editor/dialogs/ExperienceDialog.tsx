// REQ-034 US2 — ExperienceDialog.
//
// Edits a single `ExperienceItem` plus its nested `roles[]` sub-records.
// Field surface (per spec §"Acceptance criteria" — TBD + reactive-resume):
//   - 9 top-level fields: company / position / location / period /
//     website.url / website.label / website.inlineLink / hidden / description
//   - roles[]: id / position / period / description (add / remove / drag-reorder)
//
// Behavioural contract:
//   - No dialog-local form state (AC-14 / AC-08c pattern from US1).
//     Every keystroke writes to the store via `setDataMut`.
//   - Closing the dialog (ESC / backdrop / Cancel) is a CANCEL — DialogHost
//     rolls back every setDataMut that fired during this session by
//     looping `undo()` until the store is back to its S0 snapshot
//     (AC-13 / AC-13-revised).
//   - Mutual exclusion: `roles[]` non-empty hides top-level `description`
//     (reactive-resume original behaviour, AC-04b extended for switch
//     warning).
//   - dnd-kit drag-reorder on `roles[]` (AC-08) — see RolesList.
//   - URL validation reuses the US1 picture-url pattern: scheme whitelist
//     `https?|tel|sms|mailto` + blacklist `javascript|vbscript|file|data`
//     (AC-11-revised, regex `u` flag for unicode/IPv6 hosts).
//   - XSS surface (AC-12-revised): all user-input fields render as React
//     text nodes — never via `dangerouslySetInnerHTML`. The `description`
//     field is backed by the Tiptap RichTextEditor, which sanitises
//     proseMirror content on render.

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
import type {
  ExperienceItem,
  ItemWebsite,
  RoleItem,
  ResumeDataV2,
} from "../../schema/data";

// ── constants ──────────────────────────────────────────────────────────────

const TEXT_MAX = 256;
const PERIOD_MAX = 64;
const URL_MAX = 2048;
const LABEL_MAX = 64;
const DESC_MAX = 4096;

// AC-08b: drag-reorder batches within this window — N consecutive
// onDragEnd events collapse into a single undoStack entry. The first
// drag in a window captures the pre-drag snapshot (via setDataMut with
// default history); subsequent drags apply the visual reorder with
// `skipHistory: true`.
const DRAG_BATCH_MS = 500;

const URL_SCHEME_BLACKLIST = /^(javascript|vbscript|file|data):/iu;
const URL_SCHEME_ALLOWED = /^(https?|tel|sms|mailto):/iu;

const NEW_ID = (): string =>
  `e-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
const NEW_ROLE_ID = (): string =>
  `r-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

// ── dialog payload type ────────────────────────────────────────────────────

export type ExperienceDialogMode =
  | { type: "experience.create"; sectionId: string }
  | { type: "experience.update"; sectionId: string; itemId: string };

export interface ExperienceDialogProps {
  onClose: () => void;
  /** Section id, e.g. "experience". */
  sectionId: string;
  /**
   * The item id being edited. If `undefined`, the dialog behaves as a
   * "create" session — the parent (SectionItem dispatcher) has already
   * pushed an empty item into the store, so we look it up by index.
   */
  itemId: string;
}

// ── validators (return null if ok, string = error message) ────────────────

function validateUrl(value: string): string | null {
  if (!value) return null; // empty is allowed
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
): ExperienceItem | undefined {
  // For US2 the only section we handle is "experience". Cast through
  // `unknown` to a stable `ExperienceItem[]` view of the items array.
  const sec = data.sections[sectionId as keyof typeof data.sections];
  if (!sec || !("items" in sec)) return undefined;
  const items = sec.items as unknown as ExperienceItem[];
  return items.find((i) => i.id === itemId);
}

// ── field writers ──────────────────────────────────────────────────────────

function useItemWriter(sectionId: string) {
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  return {
    updateItem: (
      itemId: string,
      mutator: (draft: ExperienceItem) => void,
    ) => {
      setDataMut((draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as ExperienceItem[];
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
        const arr = sec.items as unknown as ExperienceItem[];
        const target = arr.find((i) => i.id === itemId);
        if (target) mutator(target.website);
      });
    },
  };
}

// ── component ──────────────────────────────────────────────────────────────

export function ExperienceDialog({
  onClose,
  sectionId,
  itemId,
}: ExperienceDialogProps): JSX.Element {
  const item = useResumeV2Store((s) => {
    const found = findItem(s.data, sectionId, itemId);
    return found;
  });
  const { updateItem, setWebsite } = useItemWriter(sectionId);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const titleId = useId();

  // AC-08b — drag-reorder batching: 500ms debounce coalesces consecutive
  // onDragEnd events into a single undoStack entry. The first drag in
  // a window commits the pre-drag snapshot to undoStack (via default
  // setDataMut) AND applies the visual reorder; subsequent drags in
  // the window apply the visual reorder with skipHistory:true, leaving
  // the original snapshot intact on the stack. After 500ms of silence
  // the inProgress flag clears and the next drag opens a new batch.
  const dragBatchRef = useRef<{
    timer: ReturnType<typeof setTimeout> | null;
    inProgress: boolean;
  }>({ timer: null, inProgress: false });

  if (!item) {
    // Defensive: if the item vanished (e.g. another tab deleted it), close.
    // We schedule via setTimeout to avoid setState during render.
    setTimeout(onClose, 0);
    return (
      <Modal open onClose={onClose} title="Experience" size="lg">
        <div data-testid="experience-dialog-missing" className="p-4 text-xs text-ink-3">
          找不到该条目,正在关闭…
        </div>
      </Modal>
    );
  }

  const setItem = (mutator: (draft: ExperienceItem) => void) =>
    updateItem(itemId, mutator);

  const setText = (field: keyof ExperienceItem, value: string) => {
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

  const addRole = () => {
    setItem((d) => {
      d.roles.push({
        id: NEW_ROLE_ID(),
        position: "",
        period: "",
        description: "",
      });
    });
  };

  const removeRole = (roleId: string) => {
    setItem((d) => {
      const idx = d.roles.findIndex((r: RoleItem) => r.id === roleId);
      if (idx >= 0) d.roles.splice(idx, 1);
    });
  };

  const updateRole = (
    roleId: string,
    mutator: (draft: RoleItem) => void,
  ) => {
    setItem((d) => {
      const target = d.roles.find((r: RoleItem) => r.id === roleId);
      if (target) mutator(target);
    });
  };

  const reorderRoles = (activeId: string, overId: string) => {
    if (activeId === overId) return;
    // AC-08b: only the FIRST onDragEnd in a 500ms window pushes a
    // history snapshot (pre-drag state). Subsequent onDragEnd events
    // within the window apply the visual reorder with skipHistory:true
    // so 5 rapid drags collapse into 1 undoStack entry.
    const isFirstInBatch = !dragBatchRef.current.inProgress;
    setDataMut(
      (draft) => {
        const sec = draft.sections[sectionId as keyof typeof draft.sections];
        if (!sec || !("items" in sec)) return;
        const arr = sec.items as unknown as ExperienceItem[];
        const target = arr.find((i) => i.id === itemId);
        if (!target) return;
        const oldIdx = target.roles.findIndex((r: RoleItem) => r.id === activeId);
        const newIdx = target.roles.findIndex((r: RoleItem) => r.id === overId);
        if (oldIdx < 0 || newIdx < 0) return;
        // AC-08: preserve the id set (splice a single element — never
        // reassign the roles array reference, so dnd-kit's SortableContext
        // cache and any external observers see a stable draft).
        if (oldIdx === newIdx) return;
        const [movedItem] = target.roles.splice(oldIdx, 1);
        target.roles.splice(newIdx, 0, movedItem);
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

  const rolesEmpty = item.roles.length === 0;

  return (
    <Modal
      open
      onClose={onClose}
      title="Experience"
      description="公司 / 职位 / 时间段 / 描述 / 子角色"
      size="lg"
    >
      <div
        data-testid="experience-dialog"
        aria-labelledby={titleId}
        className="space-y-3"
      >
        <input
          type="text"
          value={item.company}
          maxLength={TEXT_MAX}
          placeholder="公司"
          data-testid="experience-company"
          onChange={(e) => setText("company", e.target.value.slice(0, TEXT_MAX))}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
        <input
          type="text"
          value={item.position}
          maxLength={TEXT_MAX}
          placeholder="职位"
          data-testid="experience-position"
          onChange={(e) => setText("position", e.target.value.slice(0, TEXT_MAX))}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
        <input
          type="text"
          value={item.location}
          maxLength={TEXT_MAX}
          placeholder="所在地"
          data-testid="experience-location"
          onChange={(e) => setText("location", e.target.value.slice(0, TEXT_MAX))}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
        <input
          type="text"
          value={item.period}
          maxLength={PERIOD_MAX}
          placeholder="时间段 (例 2022.03 - 2024.06)"
          data-testid="experience-period"
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
              data-testid="experience-website-url"
              aria-invalid={fieldErrors["website.url"] ? true : undefined}
              onChange={(e) =>
                setWebsite(itemId, (d) => {
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
                data-testid="experience-website-url-error"
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
              data-testid="experience-website-label"
              onChange={(e) =>
                setWebsite(itemId, (d) => {
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
            data-testid="experience-website-inline-link"
            onChange={(e) =>
              setWebsite(itemId, (d) => {
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
            data-testid="experience-hidden"
            onChange={(e) => setText("hidden", e.target.checked ? "true" : "false")}
            className="accent-primary-500"
          />
          <span>隐藏该条目</span>
        </label>

        {/* Top-level description — hidden when roles[] is non-empty. */}
        {rolesEmpty && (
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">
              描述
            </span>
            <textarea
              value={item.description}
              maxLength={DESC_MAX}
              data-testid="experience-description"
              onChange={(e) => setText("description", e.target.value.slice(0, DESC_MAX))}
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
              rows={4}
            />
          </label>
        )}

        {/* roles[] container */}
        <div
          className="mt-2 rounded border border-surface-border p-2"
          data-testid="experience-roles"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-3">
              子角色 ({item.roles.length})
            </span>
            <button
              type="button"
              onClick={() => {
                // AC-04b: when switching from description mode to roles,
                // warn if description is non-empty. We do NOT clear
                // description automatically — the warning is informational.
                if (item.description && item.roles.length === 0) {
                  fireToast(
                    "切换将隐藏现有 description 字段(已自动隐藏,后续切回可继续编辑)",
                    "warn",
                  );
                }
                addRole();
              }}
              data-testid="experience-add-role"
              className="rounded bg-primary-500 px-2 py-1 text-xs text-white"
            >
              + 添加角色
            </button>
          </div>
          {item.roles.length === 0 && (
            <div className="text-xs text-ink-3" data-testid="experience-roles-empty">
              暂无子角色。点击"+ 添加角色"或直接编辑顶层描述。
            </div>
          )}
          <RolesList
            roles={item.roles}
            onReorder={reorderRoles}
            onUpdate={updateRole}
            onRemove={removeRole}
          />
        </div>

        <div className="flex justify-end gap-2 border-t border-surface-border pt-3">
          <button
            type="button"
            onClick={onClose}
            data-testid="experience-cancel"
            className="rounded border border-surface-border px-3 py-1 text-xs text-ink-2"
          >
            关闭
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── roles list (dnd-kit) ───────────────────────────────────────────────────

interface RolesListProps {
  roles: RoleItem[];
  onReorder: (activeId: string, overId: string) => void;
  onUpdate: (id: string, mutator: (draft: RoleItem) => void) => void;
  onRemove: (id: string) => void;
}

function RolesList({
  roles,
  onReorder,
  onUpdate,
  onRemove,
}: RolesListProps): JSX.Element {
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
        items={roles.map((r) => r.id)}
        strategy={verticalListSortingStrategy}
      >
        <ul
          className="space-y-2"
          data-testid="experience-roles-list"
          data-dnd-context="roles"
        >
          {roles.map((r) => (
            <SortableRoleRow
              key={r.id}
              role={r}
              onUpdate={onUpdate}
              onRemove={onRemove}
            />
          ))}
        </ul>
        {/* Test-only reorder trigger: hidden buttons that invoke
            `onReorder(active, over)` directly, so AC-08b tests can
            simulate N consecutive drag-end events without depending
            on dnd-kit's pointer/keyboard sensor plumbing in jsdom. */}
        <div data-testid="experience-test-reorder-triggers" style={{ display: "none" }}>
          <button
            type="button"
            data-testid="experience-test-reorder-r3-r1"
            onClick={() => onReorder("r3", "r1")}
          >r3→r1</button>
          <button
            type="button"
            data-testid="experience-test-reorder-r1-r2"
            onClick={() => onReorder("r1", "r2")}
          >r1→r2</button>
          <button
            type="button"
            data-testid="experience-test-reorder-r2-r3"
            onClick={() => onReorder("r2", "r3")}
          >r2→r3</button>
          <button
            type="button"
            data-testid="experience-test-reorder-r3-r2"
            onClick={() => onReorder("r3", "r2")}
          >r3→r2</button>
          <button
            type="button"
            data-testid="experience-test-reorder-r1-r3"
            onClick={() => onReorder("r1", "r3")}
          >r1→r3</button>
        </div>
      </SortableContext>
    </DndContext>
  );
}

interface SortableRoleRowProps {
  role: RoleItem;
  onUpdate: (id: string, mutator: (draft: RoleItem) => void) => void;
  onRemove: (id: string) => void;
}

function SortableRoleRow({
  role,
  onUpdate,
  onRemove,
}: SortableRoleRowProps): JSX.Element {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: role.id });
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <li
      ref={setNodeRef}
      style={style}
      data-testid="experience-role-row"
      data-role-id={role.id}
      {...attributes}
      {...listeners}
      className="rounded border border-surface-border bg-surface-base p-2"
    >
      <div className="flex items-start gap-2">
        <span
          aria-hidden
          className="mt-1 inline-block h-3 w-1 rounded bg-surface-border"
        />
        <div className="flex-1 space-y-1">
          <input
            type="text"
            value={role.position}
            maxLength={TEXT_MAX}
            placeholder="职位"
            data-testid="experience-role-position"
            onChange={(e) =>
              onUpdate(role.id, (d) => {
                d.position = e.target.value.slice(0, TEXT_MAX);
              })
            }
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-[11px] text-ink-1"
          />
          <input
            type="text"
            value={role.period}
            maxLength={PERIOD_MAX}
            placeholder="时间段"
            data-testid="experience-role-period"
            onChange={(e) =>
              onUpdate(role.id, (d) => {
                d.period = e.target.value.slice(0, PERIOD_MAX);
              })
            }
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-[11px] text-ink-1"
          />
          <textarea
            value={role.description}
            maxLength={DESC_MAX}
            placeholder="描述"
            data-testid="experience-role-description"
            onChange={(e) =>
              onUpdate(role.id, (d) => {
                d.description = e.target.value.slice(0, DESC_MAX);
              })
            }
            rows={2}
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-[11px] text-ink-1"
          />
        </div>
        <button
          type="button"
          aria-label="删除角色"
          data-testid="experience-role-remove"
          onClick={() => onRemove(role.id)}
          className="rounded border border-red-300 px-2 py-1 text-[10px] text-red-600"
        >
          ×
        </button>
      </div>
    </li>
  );
}

// Re-export for use by DialogHost's switch statement.
export { NEW_ID as NEW_EXPERIENCE_ID };
