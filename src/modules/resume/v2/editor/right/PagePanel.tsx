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

import { useResumeV2Store } from "../../store";
import type { PageFormat } from "../../schema/data";

// ── constants ─────────────────────────────────────────────────────────────

const PAGE_FORMATS: readonly PageFormat[] = ["a4", "letter", "free-form"];
const MARGIN_MIN = 0;
const MARGIN_MAX = 200;
const LOCALE_HINT = "^[a-z]{2}(-[A-Z]{2})?$";
const LOCALE_REGEX = /^[a-z]{2}(-[A-Z]{2})?$/;

// ── helpers ───────────────────────────────────────────────────────────────

function clampNumber(n: number, min: number, max: number): number {
  if (Number.isNaN(n)) return min;
  return Math.max(min, Math.min(max, n));
}

// ── main panel ────────────────────────────────────────────────────────────

export default function PagePanel(): JSX.Element {
  const page = useResumeV2Store((s) => s.data.metadata.page);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);

  const patchPage = (mutator: (draft: typeof page) => void) => {
    setDataMut((draft) => {
      mutator(draft.metadata.page);
    });
  };

  const handleFormatChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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

  const handleLocaleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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
      <fieldset
        data-testid="page-format"
        className="space-y-1 rounded border border-surface-border bg-surface-base p-3"
      >
        <legend className="px-1 text-xs text-ink-2">Format</legend>
        {PAGE_FORMATS.map((f) => (
          <label
            key={f}
            className="flex cursor-pointer items-center gap-2 text-xs text-ink-1"
          >
            <input
              type="radio"
              name="page-format"
              value={f}
              checked={page.format === f}
              onChange={handleFormatChange}
              data-testid={`page-format-${f}`}
              className="accent-primary-500"
            />
            <span>{f}</span>
          </label>
        ))}
      </fieldset>

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
              data-testid="page-marginX"
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
              data-testid="page-marginY"
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
              data-testid="page-gapX"
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
              data-testid="page-gapY"
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
            <span className="text-xs text-ink-3">pt</span>
          </div>
        </label>
      </div>

      {/* ── locale ──────────────────────────────────────────────────── */}
      <label className="block space-y-1 rounded border border-surface-border bg-surface-base p-3">
        <span className="text-xs text-ink-2">Locale</span>
        <input
          type="text"
          value={page.locale}
          onChange={handleLocaleChange}
          pattern={LOCALE_HINT}
          placeholder="zh-CN"
          data-testid="page-locale"
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
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
            data-testid="page-hideLinkUnderline"
            className="accent-primary-500"
          />
          <span>Hide link underline</span>
        </label>

        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={page.hideIcons}
            onChange={handleToggle("hideIcons")}
            data-testid="page-hideIcons"
            className="accent-primary-500"
          />
          <span>Hide icons</span>
        </label>

        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
          <input
            type="checkbox"
            checked={page.hideSectionIcons}
            onChange={handleToggle("hideSectionIcons")}
            data-testid="page-hideSectionIcons"
            className="accent-primary-500"
          />
          <span>Hide section icons</span>
        </label>
      </div>
    </div>
  );
}