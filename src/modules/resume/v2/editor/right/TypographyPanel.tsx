// REQ-032 v2 Batch 2 — TypographyPanel (real implementation).
//
// Wires the 12 font controls to `useResumeV2Store` so changes flow
// through `setDataMut` → immer draft → 500ms debounced PUT (handled
// inside the store). The panel is split into two visually identical
// sub-panels ("Body" + "Heading") that share a `TypographyRow` sub-
// component to keep JSX DRY.
//
// Mutation contract:
//   - Each control mutates `data.metadata.typography.{body|heading}`
//     in place. The store's `setDataMut` wraps the draft in immer
//     and automatically schedules the debounced save + pushes an
//     undo snapshot.
//   - `fontWeights` is stored as `FontWeight[]` (a subset of the
//     union). The chip selector toggles membership in the array.
//
// E2E selectors:
//   - Every input has a `data-testid` of the form
//     `typography-{body|heading}-{family|fontSize|lineHeight|weights}`
//     so Playwright tests can address controls by role.

import { useResumeV2Store } from "../../store";
import type { FontWeight, TypographyItem } from "../../schema/data";

// ── constants ─────────────────────────────────────────────────────────────

const FONT_FAMILIES: readonly string[] = [
  "Inter",
  "Roboto",
  "Open Sans",
  "Lato",
  "Source Sans Pro",
  "system-ui",
];

const FONT_WEIGHT_OPTIONS: readonly FontWeight[] = [
  "300",
  "400",
  "500",
  "600",
  "700",
  "800",
];

const FONT_SIZE_MIN = 6;
const FONT_SIZE_MAX = 24;
const LINE_HEIGHT_MIN = 0.5;
const LINE_HEIGHT_MAX = 4.0;
const LINE_HEIGHT_STEP = 0.1;

// ── shared row ────────────────────────────────────────────────────────────

interface TypographyRowProps {
  /** Either "body" or "heading" — used to namespace the testid prefix. */
  scope: "body" | "heading";
  /** The slice of `data.metadata.typography.{scope}` to bind to. */
  value: TypographyItem;
}

function TypographyRow({ scope, value }: TypographyRowProps): JSX.Element {
  const setDataMut = useResumeV2Store((s) => s.setDataMut);

  const patch = (mutator: (draft: TypographyItem) => void) => {
    setDataMut((draft) => {
      mutator(draft.metadata.typography[scope]);
    });
  };

  const handleFamilyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    patch((d) => {
      d.fontFamily = e.target.value;
    });
  };

  const handleFontSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = Number.parseInt(e.target.value, 10);
    if (Number.isNaN(next)) return;
    const clamped = Math.max(FONT_SIZE_MIN, Math.min(FONT_SIZE_MAX, next));
    patch((d) => {
      d.fontSize = clamped;
    });
  };

  const handleLineHeightChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = Number.parseFloat(e.target.value);
    if (Number.isNaN(next)) return;
    const clamped = Math.max(
      LINE_HEIGHT_MIN,
      Math.min(LINE_HEIGHT_MAX, next),
    );
    patch((d) => {
      d.lineHeight = Math.round(clamped * 100) / 100;
    });
  };

  const toggleWeight = (w: FontWeight) => {
    patch((d) => {
      const idx = d.fontWeights.indexOf(w);
      if (idx >= 0) {
        d.fontWeights.splice(idx, 1);
      } else {
        d.fontWeights.push(w);
      }
    });
  };

  return (
    <section
      data-testid={`typography-${scope}-section`}
      className="space-y-3 rounded border border-surface-border bg-surface-base p-3"
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-3">
        {scope === "body" ? "Body" : "Heading"}
      </div>

      <label className="block space-y-1">
        <span className="text-xs text-ink-2">Font family</span>
        <select
          data-testid={`typography-${scope}-family`}
          value={value.fontFamily}
          onChange={handleFamilyChange}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        >
          {FONT_FAMILIES.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </label>

      <label className="block space-y-1">
        <span className="text-xs text-ink-2">Font size (pt)</span>
        <div className="flex items-center gap-1">
          <input
            type="number"
            min={FONT_SIZE_MIN}
            max={FONT_SIZE_MAX}
            step={1}
            value={value.fontSize}
            onChange={handleFontSizeChange}
            data-testid={`typography-${scope}-fontSize`}
            className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
          />
          <span className="text-xs text-ink-3">pt</span>
        </div>
      </label>

      <label className="block space-y-1">
        <span className="text-xs text-ink-2">Line height</span>
        <input
          type="number"
          min={LINE_HEIGHT_MIN}
          max={LINE_HEIGHT_MAX}
          step={LINE_HEIGHT_STEP}
          value={value.lineHeight}
          onChange={handleLineHeightChange}
          data-testid={`typography-${scope}-lineHeight`}
          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
        />
      </label>

      <div className="space-y-1">
        <span className="text-xs text-ink-2">Font weights</span>
        <div
          className="flex flex-wrap gap-1"
          data-testid={`typography-${scope}-weights`}
        >
          {FONT_WEIGHT_OPTIONS.map((w) => {
            const active = value.fontWeights.includes(w);
            return (
              <button
                key={w}
                type="button"
                onClick={() => toggleWeight(w)}
                aria-pressed={active}
                data-testid={`typography-${scope}-weight-${w}`}
                className={
                  "rounded border px-2 py-0.5 text-xs " +
                  (active
                    ? "border-primary-400 bg-primary-100 text-primary-700"
                    : "border-surface-border bg-surface-muted text-ink-2 hover:bg-surface-base")
                }
              >
                {w}
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ── main panel ────────────────────────────────────────────────────────────

export default function TypographyPanel(): JSX.Element {
  const typography = useResumeV2Store((s) => s.data.metadata.typography);

  return (
    <div
      data-testid="typography-panel"
      className="flex h-full flex-col gap-3 overflow-y-auto p-3"
    >
      <div className="text-xs font-semibold text-ink-3">Typography</div>
      <TypographyRow scope="body" value={typography.body} />
      <TypographyRow scope="heading" value={typography.heading} />
    </div>
  );
}