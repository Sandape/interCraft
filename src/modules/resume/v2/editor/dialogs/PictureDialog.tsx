// REQ-034 US1 — PictureDialog.
//
// Edits the `data.picture` block (10 fields: hidden / url / size /
// rotation / aspectRatio / borderRadius / borderColor / borderWidth /
// shadowColor / shadowWidth). The `url` field is backed by an `<input
// type="file">` that uploads via the v1 avatar S3 client
// (`src/api/avatar.ts` → `uploadAvatar`). Per AC-05b we REUSE the v1
// client — there is no `src/services/storage/picture.ts`.
//
// Numeric fields clamp on blur (AC-06 extended + R5 / R9): size
// [32,512] / rotation [0,360] / aspectRatio [0.5,2.5] / borderRadius
// [0,100] / borderWidth [0,40] / shadowWidth [0,40]. Non-numeric / NaN /
// Infinity inputs surface as a red box + toast and do NOT mutate the
// store (clamp guards `typeof value === "number" && !isNaN(value) &&
// isFinite(value)`).
//
// URL validation (AC-09b): length ≤ 2048 and scheme must be `http(s):` or
// `data:image/{png,jpeg,webp}`; empty string is allowed (the user clears
// the picture). `javascript:` / `data:text/html` / `vbscript:` / `file:`
// are rejected on blur with a toast.
//
// All writes go through `useResumeV2Store.setDataMut(draft => ...)`
// (AC-08c). No dialog-local form state.

import { useState, useRef, useId } from "react";
import { Modal } from "@/components/ui/Modal";
import { useResumeV2Store } from "../../store";
import { fireToast } from "../center/toast";
import { uploadAvatar } from "@/api/avatar";
import type { PictureConfig, ResumeDataV2 } from "../../schema/data";

// ── numeric bounds ─────────────────────────────────────────────────────────

const BOUNDS = {
  size: { min: 32, max: 512 },
  rotation: { min: 0, max: 360 },
  aspectRatio: { min: 0.5, max: 2.5 },
  borderRadius: { min: 0, max: 100 },
  borderWidth: { min: 0, max: 40 },
  shadowWidth: { min: 0, max: 40 },
} as const;

const ALLOWED_MIME = new Set(["image/png", "image/jpeg", "image/webp"]);
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MB
const URL_MAX = 2048;
const URL_SCHEME_BLACKLIST = /^(javascript|vbscript|file):/i;
const URL_SCHEME_ALLOWED = /^https?:\/\//i;
const URL_DATA_IMAGE = /^data:image\/(png|jpeg|webp);/i;

function clampNum(
  value: unknown,
  min: number,
  max: number,
): { ok: true; value: number } | { ok: false } {
  if (typeof value === "string" && value.trim() === "") return { ok: false };
  const n = typeof value === "number" ? value : Number(value);
  if (typeof n !== "number" || !Number.isFinite(n) || Number.isNaN(n)) {
    return { ok: false };
  }
  if (n < min) return { ok: true, value: min };
  if (n > max) return { ok: true, value: max };
  return { ok: true, value: n };
}

function validatePictureUrl(value: string): string | null {
  if (!value) return null;
  if (value.length > URL_MAX) return `链接最长 ${URL_MAX} 字符`;
  if (URL_SCHEME_BLACKLIST.test(value)) return "链接协议被禁止";
  if (URL_SCHEME_ALLOWED.test(value)) return null;
  if (URL_DATA_IMAGE.test(value)) return null;
  return "链接必须以 http(s):// 或 data:image/ 开头";
}

// ── component ──────────────────────────────────────────────────────────────

export interface PictureDialogProps {
  onClose: () => void;
}

export function PictureDialog({ onClose }: PictureDialogProps): JSX.Element {
  const picture = useResumeV2Store((s) => s.data.picture);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const titleId = useId();

  const setField = (mutator: (draft: PictureConfig) => void) => {
    setDataMut((draft: ResumeDataV2) => {
      mutator(draft.picture);
    });
  };

  const onNumericBlur = (
    field: keyof typeof BOUNDS,
    raw: string,
  ) => {
    const { min, max } = BOUNDS[field];
    const result = clampNum(raw, min, max);
    if (!result.ok) {
      const msg = `请输入合法数字 (${min}~${max})`;
      setFieldErrors((prev) => ({ ...prev, [field]: msg }));
      fireToast(msg, "warn");
      return;
    }
    const before = picture[field];
    if (result.value === before) {
      setFieldErrors((prev) => {
        if (!(field in prev)) return prev;
        const next = { ...prev };
        delete next[field];
        return next;
      });
      return;
    }
    setField((draft) => {
      // Safe-cast: BOUNDS field names are all `number` in PictureConfig.
      (draft as unknown as Record<string, number>)[field] = result.value;
    });
    if (result.value !== Number(raw)) {
      // Only toast when clamping actually happened (not on plain re-edit).
      fireToast(`已自动夹紧到 ${min}~${max}`, "warn");
    }
    setFieldErrors((prev) => {
      if (!(field in prev)) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const onUrlBlur = (value: string) => {
    const err = validatePictureUrl(value);
    if (err) {
      setFieldErrors((prev) => ({ ...prev, url: err }));
      fireToast(err, "warn");
    } else {
      setFieldErrors((prev) => {
        if (!("url" in prev)) return prev;
        const next = { ...prev };
        delete next.url;
        return next;
      });
    }
  };

  const handleFileChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // AC-05b: client-side mime + size validation BEFORE any network call.
    if (!ALLOWED_MIME.has(file.type)) {
      fireToast("仅支持 PNG / JPEG / WebP", "error");
      e.target.value = "";
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      fireToast("图片不能超过 5 MB", "error");
      e.target.value = "";
      return;
    }
    setUploading(true);
    try {
      const result = await uploadAvatar(file);
      setField((draft) => {
        draft.url = result.url;
      });
      fireToast("头像已上传", "info");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "上传失败";
      fireToast(msg, "error");
      // AC-07: do NOT mutate store on upload failure — keep original url.
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="头像"
      description="上传头像 + 调整大小 / 圆角 / 阴影"
      size="md"
    >
      <div data-testid="picture-dialog" aria-labelledby={titleId} className="space-y-3">
        {/* hidden + file picker */}
        <div className="flex items-center justify-between gap-2">
          <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
            <input
              type="checkbox"
              checked={picture.hidden}
              data-testid="picture-hidden"
              onChange={(e) =>
                setField((draft) => {
                  draft.hidden = e.target.checked;
                })
              }
              className="accent-primary-500"
            />
            <span>隐藏头像</span>
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            data-testid="picture-file-input"
            onChange={handleFileChange}
            disabled={uploading}
            className="text-xs"
          />
        </div>

        {/* url */}
        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wide text-ink-3">头像 URL</span>
          <input
            type="text"
            value={picture.url}
            placeholder="https://... 或 data:image/png;base64,..."
            data-testid="picture-url"
            aria-invalid={fieldErrors.url ? true : undefined}
            onChange={(e) =>
              setField((draft) => {
                draft.url = e.target.value;
              })
            }
            onBlur={() => onUrlBlur(picture.url)}
            className={[
              "w-full rounded border bg-surface-base px-2 py-1 text-xs text-ink-1",
              fieldErrors.url ? "border-red-500" : "border-surface-border",
            ].join(" ")}
          />
          {fieldErrors.url && (
            <span role="alert" data-testid="picture-url-error" className="text-[10px] text-red-600">
              {fieldErrors.url}
            </span>
          )}
        </label>

        {/* numeric fields — 6 inputs in a grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3" data-testid="picture-numeric-grid">
          <NumberField
            label="尺寸 (32-512)"
            testid="picture-size"
            value={picture.size}
            bounds={BOUNDS.size}
            error={fieldErrors.size}
            onCommit={(v) => onNumericBlur("size", v)}
            onChange={(v) =>
              setField((draft) => {
                draft.size = v;
              })
            }
          />
          <NumberField
            label="旋转 (0-360)"
            testid="picture-rotation"
            value={picture.rotation}
            bounds={BOUNDS.rotation}
            error={fieldErrors.rotation}
            onCommit={(v) => onNumericBlur("rotation", v)}
            onChange={(v) =>
              setField((draft) => {
                draft.rotation = v;
              })
            }
          />
          <NumberField
            label="宽高比 (0.5-2.5)"
            testid="picture-aspect-ratio"
            value={picture.aspectRatio}
            bounds={BOUNDS.aspectRatio}
            step={0.1}
            error={fieldErrors.aspectRatio}
            onCommit={(v) => onNumericBlur("aspectRatio", v)}
            onChange={(v) =>
              setField((draft) => {
                draft.aspectRatio = v;
              })
            }
          />
          <NumberField
            label="圆角 (0-100)"
            testid="picture-border-radius"
            value={picture.borderRadius}
            bounds={BOUNDS.borderRadius}
            error={fieldErrors.borderRadius}
            onCommit={(v) => onNumericBlur("borderRadius", v)}
            onChange={(v) =>
              setField((draft) => {
                draft.borderRadius = v;
              })
            }
          />
          <NumberField
            label="边框宽度 (0-40)"
            testid="picture-border-width"
            value={picture.borderWidth}
            bounds={BOUNDS.borderWidth}
            error={fieldErrors.borderWidth}
            onCommit={(v) => onNumericBlur("borderWidth", v)}
            onChange={(v) =>
              setField((draft) => {
                draft.borderWidth = v;
              })
            }
          />
          <NumberField
            label="阴影宽度 (0-40)"
            testid="picture-shadow-width"
            value={picture.shadowWidth}
            bounds={BOUNDS.shadowWidth}
            error={fieldErrors.shadowWidth}
            onCommit={(v) => onNumericBlur("shadowWidth", v)}
            onChange={(v) =>
              setField((draft) => {
                draft.shadowWidth = v;
              })
            }
          />
        </div>

        {/* colors */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">边框颜色</span>
            <input
              type="text"
              value={picture.borderColor}
              data-testid="picture-border-color"
              onChange={(e) =>
                setField((draft) => {
                  draft.borderColor = e.target.value;
                })
              }
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">阴影颜色</span>
            <input
              type="text"
              value={picture.shadowColor}
              data-testid="picture-shadow-color"
              onChange={(e) =>
                setField((draft) => {
                  draft.shadowColor = e.target.value;
                })
              }
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-surface-border pt-3">
          <button
            type="button"
            onClick={onClose}
            data-testid="picture-cancel"
            className="rounded border border-surface-border px-3 py-1 text-xs text-ink-2"
          >
            关闭
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── NumberField: keeps uncontrolled internal text so partial typing ("-",
// "1.") does NOT spuriously clamp / toast. Commits on blur only. ──────────

interface NumberFieldProps {
  label: string;
  testid: string;
  value: number;
  bounds: { min: number; max: number };
  step?: number;
  error?: string;
  onChange: (next: number) => void;
  onCommit: (raw: string) => void;
}

function NumberField({
  label,
  testid,
  value,
  bounds,
  step,
  error,
  onChange,
  onCommit,
}: NumberFieldProps): JSX.Element {
  // Keep a local string so the user can type "-", "1.", or "" without the
  // parent re-clamping on every keystroke. `onCommit` runs on blur and
  // performs clamp + toast.
  const [draft, setDraft] = useState<string>(String(value));
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Re-sync the draft when the upstream `value` changes externally
  // (e.g. undo/redo, server diff).
  if (String(value) !== draft && document.activeElement !== inputRef.current) {
    // Defer to avoid setState during render.
    setTimeout(() => setDraft(String(value)), 0);
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.value;
    setDraft(next);
    const parsed = next === "" ? NaN : Number(next);
    if (Number.isFinite(parsed)) {
      onChange(parsed);
    }
  };

  const handleBlur = () => {
    onCommit(draft);
    // After commit, sync local draft back to canonical (clamped) value.
    setDraft(String(value));
  };

  return (
    <label className="block space-y-1">
      <span className="text-[10px] uppercase tracking-wide text-ink-3">{label}</span>
      <input
        ref={inputRef}
        type="number"
        value={draft}
        step={step ?? 1}
        min={bounds.min}
        max={bounds.max}
        data-testid={testid}
        aria-invalid={error ? true : undefined}
        onChange={handleChange}
        onBlur={handleBlur}
        className={[
          "w-full rounded border bg-surface-base px-2 py-1 text-xs text-ink-1",
          error ? "border-red-500" : "border-surface-border",
        ].join(" ")}
      />
      {error && (
        <span role="alert" data-testid={`${testid}-error`} className="text-[10px] text-red-600">
          {error}
        </span>
      )}
    </label>
  );
}

export default PictureDialog;