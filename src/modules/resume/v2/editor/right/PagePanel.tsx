// REQ-032 v2 Batch 2 — PagePanel (real implementation).
//
// Wires the 9 page-format / margin / gap / locale / visibility controls
// to `useResumeV2Store` via `setDataMut`. All mutations hit the immer
// draft at `data.metadata.page` and flow through the same 500ms
// debounced save pipeline as the rest of the editor.
//
// Locale is validated against the backend regex
// `^[a-z]{2}(-[A-Z]{2})?$` (display hint only — we accept any value on
// the client; the backend rejects malformed locales on save).
//
// E2E selectors: every control carries `data-testid="page-{field}"`.
// The format radio's three options use a `name` attribute so they
// form a single radio group (clicking one deselects the others).

import { useEffect, useState } from "react";
import { useResumeV2Store } from "../../store";
import type { PageFormat, ResumeDataV2 } from "../../schema/data";

export interface PagePanelProps {
  data?: ResumeDataV2;
  onChange?: (next: ResumeDataV2) => void;
}

// ── constants ─────────────────────────────────────────────────────────────

const PAGE_FORMATS: readonly PageFormat[] = ["a4", "letter", "free-form"];
const PAGE_LOCALES = ["en-US", "zh-CN", "ja-JP", "ko-KR", "fr-FR", "de-DE", "es-ES"] as const;
const MARGIN_MIN = 0;
const MARGIN_MAX = 200;
const LOCALE_HINT = "^[a-z]{2}(-[A-Z]{2})?$";
const LOCALE_REGEX = /^[a-z]{2}(-[A-Z]{2})?$/;

function cloneData(data: ResumeDataV2): ResumeDataV2 {
  return JSON.parse(JSON.stringify(data)) as ResumeDataV2;
}

// ── helpers ───────────────────────────────────────────────────────────────

function clampNumber(n: number, min: number, max: number): number {
  if (Number.isNaN(n)) return min;
  return Math.max(min, Math.min(max, n));
}

// ── main panel ────────────────────────────────────────────────────────────

export function PagePanel(props: PagePanelProps = {}): JSX.Element {
  const storeData = useResumeV2Store((s) => s.data);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const [localData, setLocalData] = useState<ResumeDataV2 | null>(() =>
    props.data ? cloneData(props.data) : null,
  );

  useEffect(() => {
    if (props.data) setLocalData(cloneData(props.data));
  }, [props.data]);

  const data = props.data ? (localData ?? props.data) : storeData;
  const page = data.metadata.page;

  const patchPage = (mutator: (draft: typeof page) => void) => {
    if (props.data && props.onChange) {
      const next = cloneData(data);
      mutator(next.metadata.page);
      setLocalData(next);
      props.onChange(next);
      return;
    }
    setDataMut((draft) => {
      mutator(draft.metadata.page);
    });
  };

  const handleFormatChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value as PageFormat;
    patchPage((d) => {
      d.format = next;
    });
  };

  const handleNumberChange = (
    field: "marginX" | "marginY" | "gapX" | "gapY",
  ) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = Number.parseInt(e.target.value, 10);
    patchPage((d) => {
      d[field] = clampNumber(next, MARGIN_MIN, MARGIN_MAX);
    });
  };

  const handleLocaleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    patchPage((d) => {
      d.locale = e.target.value;
    });
  };

  const handleToggle = (
    field: "hideLinkUnderline" | "hideIcons" | "hideSectionIcons",
  ) => (e: React.ChangeEvent<HTMLInputElement>) => {
    patchPage((d) => {
      d[field] = e.target.checked;
    });
  };

  const localeValid = LOCALE_REGEX.test(page.locale);

  return (
    <div
      data-testid="page-panel"
      className="flex h-full flex-col gap-3 overflow-y-auto p-3"
    >
      <div className="text-xs font-semibold text-ink-3">Page</div>

      {/* ── format ───────────────────────────────────────────────────── */}
      <label className="block space-y-1 rounded border border-surface-border bg-surface-base p-3">
        <span className="text-xs text-ink-2">Format</span>
        <select
          data-testid="page-format"
          value={page.format}
          onChange={handleFormatChange}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        >
          {PAGE_FORMATS.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </label>

      {/* ── margins + gaps ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-2 rounded border border-surface-border bg-surface-base p-3">
        <label className="block space-y-1">
          <span className="text-xs text-ink-2">Margin X (pt)</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              min={MARGIN_MIN}
              max={MARGIN_MAX}
              step={1}
              value={page.marginX}
              onChange={handleNumberChange("marginX")}
              data-testid="page-margin-x"
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
            <span className="text-xs text-ink-3">pt</span>
          </div>
        </label>

        <label className="block space-y-1">
          <span className="text-xs text-ink-2">Margin Y (pt)</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              min={MARGIN_MIN}
              max={MARGIN_MAX}
              step={1}
              value={page.marginY}
              onChange={handleNumberChange("marginY")}
              data-testid="page-margin-y"
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
            <span className="text-xs text-ink-3">pt</span>
          </div>
        </label>

        <label className="block space-y-1">
          <span className="text-xs text-ink-2">Gap X (pt)</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              min={MARGIN_MIN}
              max={MARGIN_MAX}
              step={1}
              value={page.gapX}
              onChange={handleNumberChange("gapX")}
              data-testid="page-gap-x"
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
            <span className="text-xs text-ink-3">pt</span>
          </div>
        </label>

        <label className="block space-y-1">
          <span className="text-xs text-ink-2">Gap Y (pt)</span>
          <div className="flex items-center gap-1">
            <input
              type="number"
              min={MARGIN_MIN}
              max={MARGIN_MAX}
              step={1}
              value={page.gapY}
              onChange={handleNumberChange("gapY")}
              data-testid="page-gap-y"
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
            <span className="text-xs text-ink-3">pt</span>
          </div>
        </label>
      </div>

      {/* ── locale ──────────────────────────────────────────────────── */}
      <label className="block space-y-1 rounded border border-surface-border bg-surface-base p-3">
        <span className="text-xs text-ink-2">Language</span>
        <select
          value={page.locale}
          onChange={handleLocaleChange}
          data-testid="page-language"
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        >
          {PAGE_LOCALES.map((locale) => (
            <option key={locale} value={locale}>
              {locale}
            </option>
          ))}
        </select>
        <span
          className={
            "block text-[10px] " +
            (localeValid ? "text-ink-3" : "text-amber-600")
          }
        >
          {localeValid
            ? `Format: ${LOCALE_HINT}`
            : `Invalid locale — must match ${LOCALE_HINT}`}
        </span>
      </label>

      {/* ── toggles ─────────────────────────────────────────────────── */}
      <div className="space-y-1 rounded border border-surface-border bg-surface-base p-3">
        <div className="text-xs text-ink-2">Visibility</div>

        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={page.hideLinkUnderline}
            onChange={handleToggle("hideLinkUnderline")}
            data-testid="page-hide-link-underline"
            className="accent-primary-500"
          />
          <span>Hide link underline</span>
        </label>

        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={page.hideIcons}
            onChange={handleToggle("hideIcons")}
            data-testid="page-hide-icons"
            className="accent-primary-500"
          />
          <span>Hide icons</span>
        </label>

        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={page.hideSectionIcons}
            onChange={handleToggle("hideSectionIcons")}
            data-testid="page-hide-section-icons"
            className="accent-primary-500"
          />
          <span>Hide section icons</span>
        </label>
      </div>
    </div>
  );
}

export default PagePanel;
