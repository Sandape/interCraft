// REQ-034 US1 — BasicsDialog.
//
// Edits the `data.basics` block of the v2 resume: name / headline /
// email / phone / location / website.url / website.label / customFields[].
//
// All writes route through `useResumeV2Store.setDataMut(draft => ...)`
// per AC-08c — there is NO dialog-local draft state. Closing the
// dialog (ESC / backdrop / Cancel) leaves the store in whatever state
// the user committed via real-time edits, matching the rest of the v2
// editor (REUSES store's 500ms debounce + undoStack + redoStack).
//
// Per AC-08b: closing the dialog does NOT cancel the pending debounce
// timer; the store's debounced PUT runs once the user navigates away or
// the 500ms window elapses. This is intentional — the field edits were
// already committed to `data.basics` (per AC-08c) and the autosave
// pipeline takes care of flushing them.

import { useState, useId } from "react";
import { Modal } from "@/components/ui/Modal";
import { useResumeV2Store } from "../../store";
import { fireToast } from "../center/toast";
import type { Basics, CustomField, ResumeDataV2 } from "../../schema/data";

// ── constants ──────────────────────────────────────────────────────────────

const NAME_MAX = 256;
const HEADLINE_MAX = 256;
const EMAIL_MAX = 254;
const PHONE_MAX = 30;
const LOCATION_MAX = 256;
const URL_MAX = 2048;
const LABEL_MAX = 64;
const CUSTOM_TEXT_MAX = 256;
const CUSTOM_ICON_MAX = 64;
const CUSTOM_LINK_MAX = 2048;

const PHONE_REGEX = /^[+0-9()\-\s]{5,30}$/;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_SCHEME_BLACKLIST = /^(javascript|data|vbscript|file):/i;
const URL_SCHEME_ALLOWED = /^https?:\/\//i;

const NEW_CUSTOM_FIELD_ID = (): string =>
  `cf-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`;

export interface BasicsDialogProps {
  onClose: () => void;
}

// ── field validators (return null if ok, string = error message) ──────────

function validatePhone(value: string): string | null {
  if (!value) return null; // empty is allowed
  if (value.length > PHONE_MAX) return `电话最多 ${PHONE_MAX} 个字符`;
  if (!PHONE_REGEX.test(value)) return "电话格式不合法";
  return null;
}

function validateEmail(value: string): string | null {
  if (!value) return null;
  if (value.length > EMAIL_MAX) return `邮箱最多 ${EMAIL_MAX} 个字符`;
  if (!EMAIL_REGEX.test(value)) return "邮箱格式不合法";
  return null;
}

function validateUrl(value: string): string | null {
  if (!value) return null;
  if (value.length > URL_MAX) return `链接最多 ${URL_MAX} 个字符`;
  if (URL_SCHEME_BLACKLIST.test(value)) return "链接协议被禁止";
  if (!URL_SCHEME_ALLOWED.test(value) && !/^data:image\//i.test(value)) {
    return "链接必须以 http(s):// 开头";
  }
  return null;
}

// ── component ──────────────────────────────────────────────────────────────

/**
 * Edits the `Basics` block. No local form state: every keystroke writes
 * directly to the store via `setDataMut`.
 */
export function BasicsDialog({ onClose }: BasicsDialogProps): JSX.Element {
  const basics = useResumeV2Store((s) => s.data.basics);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  // Local error state ONLY for inline red-box feedback. This is display
  // state, NOT form draft state (AC-08c: actual field values live in the
  // store). The validator reads the LATEST value from the store on blur.
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const titleId = useId();
  const descId = useId();

  const setField = (mutator: (draft: Basics) => void) => {
    setDataMut((draft: ResumeDataV2) => {
      mutator(draft.basics);
    });
  };

  const onTextFieldBlur = (
    field: keyof Basics | "website.url" | "website.label",
    value: string,
  ) => {
    let err: string | null = null;
    if (field === "phone") err = validatePhone(value);
    else if (field === "email") err = validateEmail(value);
    else if (field === "website.url") err = validateUrl(value);
    if (err) {
      setFieldErrors((prev) => ({ ...prev, [field]: err as string }));
      fireToast(err, "warn");
    } else {
      setFieldErrors((prev) => {
        if (!(field in prev)) return prev;
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  const addCustomField = () => {
    setField((draft) => {
      draft.customFields.push({
        id: NEW_CUSTOM_FIELD_ID(),
        icon: "",
        text: "",
        link: "",
      });
    });
  };

  const removeCustomField = (id: string) => {
    setField((draft) => {
      const idx = draft.customFields.findIndex((c: CustomField) => c.id === id);
      if (idx >= 0) draft.customFields.splice(idx, 1);
    });
  };

  const updateCustomField = (
    id: string,
    mutator: (draft: CustomField) => void,
  ) => {
    setField((draft) => {
      const target = draft.customFields.find((c: CustomField) => c.id === id);
      if (target) mutator(target);
    });
  };

  const moveCustomField = (id: string, dir: -1 | 1) => {
    setField((draft) => {
      const arr = draft.customFields;
      const idx = arr.findIndex((c: CustomField) => c.id === id);
      const target = idx + dir;
      if (idx < 0 || target < 0 || target >= arr.length) return;
      // Swap id-positions WITHOUT changing id set (AC-04b).
      const tmp = arr[idx];
      arr[idx] = arr[target];
      arr[target] = tmp;
    });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="基本信息"
      description="姓名 / 标题 / 邮箱 / 电话 / 所在地 / 主页 / 自定义字段"
      size="lg"
    >
      <div data-testid="basics-dialog" aria-labelledby={titleId} aria-describedby={descId} className="space-y-3">
        <Field
          label="姓名"
          value={basics.name}
          maxLength={NAME_MAX}
          error={fieldErrors.name}
          onChange={(v) =>
            setField((draft) => {
              draft.name = v.slice(0, NAME_MAX);
            })
          }
          onBlur={() => onTextFieldBlur("name", basics.name)}
          testid="basics-name"
        />
        <Field
          label="标题 (Headline)"
          value={basics.headline}
          maxLength={HEADLINE_MAX}
          error={fieldErrors.headline}
          onChange={(v) =>
            setField((draft) => {
              draft.headline = v.slice(0, HEADLINE_MAX);
            })
          }
          onBlur={() => onTextFieldBlur("headline", basics.headline)}
          testid="basics-headline"
        />
        <Field
          label="邮箱"
          value={basics.email}
          maxLength={EMAIL_MAX}
          error={fieldErrors.email}
          onChange={(v) =>
            setField((draft) => {
              draft.email = v.slice(0, EMAIL_MAX);
            })
          }
          onBlur={() => onTextFieldBlur("email", basics.email)}
          testid="basics-email"
          placeholder="you@example.com"
        />
        <Field
          label="电话"
          value={basics.phone}
          maxLength={PHONE_MAX}
          error={fieldErrors.phone}
          onChange={(v) =>
            setField((draft) => {
              draft.phone = v.slice(0, PHONE_MAX);
            })
          }
          onBlur={() => onTextFieldBlur("phone", basics.phone)}
          testid="basics-phone"
          placeholder="+86 138 0013 8000"
        />
        <Field
          label="所在地"
          value={basics.location}
          maxLength={LOCATION_MAX}
          error={fieldErrors.location}
          onChange={(v) =>
            setField((draft) => {
              draft.location = v.slice(0, LOCATION_MAX);
            })
          }
          onBlur={() => onTextFieldBlur("location", basics.location)}
          testid="basics-location"
        />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field
            label="主页 URL"
            value={basics.website.url}
            maxLength={URL_MAX}
            error={fieldErrors["website.url"]}
            onChange={(v) =>
              setField((draft) => {
                draft.website.url = v.slice(0, URL_MAX);
              })
            }
            onBlur={() => onTextFieldBlur("website.url", basics.website.url)}
            testid="basics-website-url"
            placeholder="https://example.com"
          />
          <Field
            label="主页标签"
            value={basics.website.label}
            maxLength={LABEL_MAX}
            error={fieldErrors["website.label"]}
            onChange={(v) =>
              setField((draft) => {
                draft.website.label = v.slice(0, LABEL_MAX);
              })
            }
            onBlur={() => onTextFieldBlur("website.label", basics.website.label)}
            testid="basics-website-label"
          />
        </div>

        {/* customFields */}
        <div
          className="mt-2 rounded border border-surface-border p-2"
          data-testid="basics-custom-fields"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-3">自定义字段</span>
            <button
              type="button"
              onClick={addCustomField}
              data-testid="basics-custom-field-add"
              className="rounded bg-primary-500 px-2 py-1 text-xs text-white"
            >
              + 添加
            </button>
          </div>
          {basics.customFields.length === 0 && (
            <div className="text-xs text-ink-3" data-testid="basics-custom-fields-empty">
              暂无自定义字段。点击"+ 添加"新增一行。
            </div>
          )}
          <ul className="space-y-2" data-testid="basics-custom-fields-list">
            {basics.customFields.map((cf, idx) => (
              <li
                key={cf.id}
                data-testid="basics-custom-field-row"
                data-custom-field-id={cf.id}
                className="rounded border border-surface-border bg-surface-base p-2"
              >
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_2fr_auto]">
                  <input
                    type="text"
                    value={cf.icon}
                    maxLength={CUSTOM_ICON_MAX}
                    placeholder="icon key"
                    aria-label="自定义字段图标"
                    data-testid="basics-custom-field-icon"
                    onChange={(e) =>
                      updateCustomField(cf.id, (d) => {
                        d.icon = e.target.value.slice(0, CUSTOM_ICON_MAX);
                      })
                    }
                    className="rounded border border-surface-border px-2 py-1 text-xs"
                  />
                  <input
                    type="text"
                    value={cf.text}
                    maxLength={CUSTOM_TEXT_MAX}
                    placeholder="展示文本"
                    aria-label="自定义字段文本"
                    data-testid="basics-custom-field-text"
                    onChange={(e) =>
                      updateCustomField(cf.id, (d) => {
                        d.text = e.target.value.slice(0, CUSTOM_TEXT_MAX);
                      })
                    }
                    className="rounded border border-surface-border px-2 py-1 text-xs"
                  />
                  <div className="flex gap-1">
                    <button
                      type="button"
                      aria-label="上移"
                      data-testid="basics-custom-field-up"
                      disabled={idx === 0}
                      onClick={() => moveCustomField(cf.id, -1)}
                      className="rounded border border-surface-border px-2 py-1 text-xs text-ink-2 disabled:opacity-40"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      aria-label="下移"
                      data-testid="basics-custom-field-down"
                      disabled={idx === basics.customFields.length - 1}
                      onClick={() => moveCustomField(cf.id, 1)}
                      className="rounded border border-surface-border px-2 py-1 text-xs text-ink-2 disabled:opacity-40"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      aria-label="删除"
                      data-testid="basics-custom-field-remove"
                      onClick={() => removeCustomField(cf.id)}
                      className="rounded border border-red-300 px-2 py-1 text-xs text-red-600"
                    >
                      ×
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  value={cf.link}
                  maxLength={CUSTOM_LINK_MAX}
                  placeholder="https://... (可选链接)"
                  aria-label="自定义字段链接"
                  data-testid="basics-custom-field-link"
                  onChange={(e) =>
                    updateCustomField(cf.id, (d) => {
                      d.link = e.target.value.slice(0, CUSTOM_LINK_MAX);
                    })
                  }
                  onBlur={() => onTextFieldBlur("website.url", cf.link)}
                  className="mt-2 w-full rounded border border-surface-border px-2 py-1 text-xs"
                />
              </li>
            ))}
          </ul>
        </div>

        <div className="flex justify-end gap-2 border-t border-surface-border pt-3">
          <button
            type="button"
            onClick={onClose}
            data-testid="basics-cancel"
            className="rounded border border-surface-border px-3 py-1 text-xs text-ink-2"
          >
            关闭
          </button>
        </div>
      </div>
    </Modal>
  );
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  onBlur?: () => void;
  maxLength?: number;
  error?: string;
  placeholder?: string;
  testid?: string;
}

function Field({
  label,
  value,
  onChange,
  onBlur,
  maxLength,
  error,
  placeholder,
  testid,
}: FieldProps): JSX.Element {
  return (
    <label className="block space-y-1">
      <span className="text-[10px] uppercase tracking-wide text-ink-3">{label}</span>
      <input
        type="text"
        value={value}
        maxLength={maxLength}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        data-testid={testid}
        aria-invalid={error ? true : undefined}
        className={[
          "w-full rounded border bg-surface-base px-2 py-1 text-xs text-ink-1",
          error ? "border-red-500" : "border-surface-border",
        ].join(" ")}
      />
      {error && (
        <span
          role="alert"
          data-testid={testid ? `${testid}-error` : undefined}
          className="text-[10px] text-red-600"
        >
          {error}
        </span>
      )}
    </label>
  );
}

export default BasicsDialog;