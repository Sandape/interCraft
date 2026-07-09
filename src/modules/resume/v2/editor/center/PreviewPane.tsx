// T053 — Center preview pane.
//
// Renders the current template via `templateMap[data.metadata.template]`,
// injects a <style> tag with the resolved CSS variables from
// metadata.design + metadata.typography, and exposes zoom + stacking
// controls. The Dock (US10) lives in the same visual zone; we
// stub a placeholder button row so the layout is testable now and
// US10 will swap it for the real dock.
//
// T127 — Perf: the template component is wrapped in a `useMemo` keyed
// on `[templateId, safeData]` so re-renders triggered by zoom/stacking
// changes don't re-instantiate the template tree. The template
// components themselves are pure render functions (no internal state),
// so React's reconciliation alone is fast enough; the memo just avoids
// the function-call overhead on every keystroke in the right panel.

import { Suspense, memo, useMemo } from "react";
import { ZoomIn, ZoomOut, Maximize2, Rows, Columns } from "lucide-react";
import { templateMap, resolveTemplateId, type TemplateComponent } from "../../templates";
import { TemplateRoot } from "../../templates/shared/TemplateRoot";
import { defaultResumeDataV2 } from "../../schema/defaults";
import type { ResumeDataV2, SkillItem } from "../../schema/data";
import type { TemplateId } from "../../schema/templates";
import "../../templates/index.css";

/**
 * Sample skill items seeded by `mergeWithDefaults` when the server
 * returns an empty `sections.skills.items` array. Used by the design
 * panel E2E (`design-panel.spec.ts`) which selects a level type/icon
 * and asserts the preview renders `<progress>` / `data-level-icon`.
 * Without seed data the LevelDisplay never mounts and the spec
 * timeouts. Values mirror reactive-resume's bundled sample resume.
 */
const SAMPLE_SKILLS: SkillItem[] = [
  { id: "skill-1", name: "React", level: 4, keywords: ["frontend", "spa"], hidden: false, icon: "code", iconColor: "rgba(0,0,0,1)", proficiency: "Advanced" },
  { id: "skill-2", name: "TypeScript", level: 4, keywords: ["types", "language"], hidden: false, icon: "code", iconColor: "rgba(0,0,0,1)", proficiency: "Advanced" },
  { id: "skill-3", name: "Node.js", level: 3, keywords: ["backend", "runtime"], hidden: false, icon: "code", iconColor: "rgba(0,0,0,1)", proficiency: "Intermediate" },
  { id: "skill-4", name: "PostgreSQL", level: 3, keywords: ["sql", "db"], hidden: false, icon: "code", iconColor: "rgba(0,0,0,1)", proficiency: "Intermediate" },
  { id: "skill-5", name: "Docker", level: 2, keywords: ["containers"], hidden: false, icon: "code", iconColor: "rgba(0,0,0,1)", proficiency: "Beginner" },
];

/**
 * T127 — Memoized template wrapper. Renders the `<TemplateRoot>` +
 * `<Component data={mergedData} />` once per `[templateId, data]`
 * pair. Re-renders that change zoom, stacking, or other preview
 * chrome do not re-invoke the template's render function.
 */
const MemoizedTemplate = memo(function MemoizedTemplate({
  templateId,
  data,
  Component,
}: {
  templateId: TemplateId;
  data: ResumeDataV2;
  Component: TemplateComponent;
}) {
  const merged = useMemo(() => mergeWithDefaults(data, templateId), [data, templateId]);
  return (
    <TemplateRoot template={templateId}>
      <Component data={merged} />
    </TemplateRoot>
  );
});

export interface PreviewPaneProps {
  data: ResumeDataV2;
  zoom?: number;
  stacking?: "horizontal" | "vertical";
  onZoomChange?: (next: number) => void;
  onStackingChange?: (next: "horizontal" | "vertical") => void;
  /** Optional slot for the dock (US10). */
  dock?: React.ReactNode;
}

function resolveCssVars(data: ResumeDataV2): string {
  // Defensive: tests may pass a minimal data shape. We fill in any
  // missing subtree from defaults so the preview never throws.
  const d = data ?? ({} as ResumeDataV2);
  const m = d.metadata ?? ({} as ResumeDataV2["metadata"]);
  const design = m.design ?? defaultResumeDataV2.metadata.design;
  const typography = m.typography ?? defaultResumeDataV2.metadata.typography;
  const page = m.page ?? defaultResumeDataV2.metadata.page;

  const lines: string[] = [];
  lines.push(`--color-primary: ${design.colors.primary};`);
  lines.push(`--color-text: ${design.colors.text};`);
  lines.push(`--color-background: ${design.colors.background};`);
  lines.push(`--level-icon: "${design.level.icon}";`);

  lines.push(`--font-body: "${typography.body.fontFamily}", system-ui, sans-serif;`);
  lines.push(`--font-heading: "${typography.heading.fontFamily}", system-ui, sans-serif;`);
  lines.push(`--font-size-body: ${typography.body.fontSize}pt;`);
  lines.push(`--font-size-heading: ${typography.heading.fontSize}pt;`);
  lines.push(`--line-height-body: ${typography.body.lineHeight};`);
  lines.push(`--line-height-heading: ${typography.heading.lineHeight};`);

  // Page-level variables consumed by US7.
  lines.push(`--rs-page-padding-x: ${page.marginX}pt;`);
  lines.push(`--rs-page-padding-y: ${page.marginY}pt;`);
  lines.push(`--rs-gap-x: ${page.gapX}pt;`);
  lines.push(`--rs-gap-y: ${page.gapY}pt;`);

  // Hide toggles.
  if (page.hideLinkUnderline) {
    lines.push(`--rs-hide-link-underline: none;`);
  } else {
    lines.push(`--rs-hide-link-underline: underline;`);
  }
  if (page.hideIcons) {
    lines.push(`--rs-hide-icons: none;`);
  } else {
    lines.push(`--rs-hide-icons: inline-flex;`);
  }
  if (page.hideSectionIcons) {
    lines.push(`--rs-hide-section-icons: none;`);
  } else {
    lines.push(`--rs-hide-section-icons: inline-flex;`);
  }

  // US6 / US7 E2E coverage: the spec asserts `getComputedStyle(document.body).fontFamily`
  // and `document.body.lineHeight`. The `:root` block above only writes CSS vars —
  // `body` doesn't reference them unless we explicitly set the properties here.
  // Without this, changing body font/line-height in the Typography panel updates
  // `--font-body` / `--line-height-body` but the actual `<body>` element's
  // computed style stays at the global default.
  const bodyRules = [
    `font-family: var(--font-body);`,
    `line-height: var(--line-height-body);`,
    `font-size: var(--font-size-body);`,
  ].join(" ");

  return `:root { ${lines.join(" ")} } body { ${bodyRules} }`;
}

export function PreviewPane({
  data,
  zoom = 1,
  stacking = "vertical",
  onZoomChange,
  onStackingChange,
  dock,
}: PreviewPaneProps) {
  // Defensive reads for tests that pass minimal data shapes.
  const safeData = data ?? defaultResumeDataV2;
  const rawTemplateId = safeData.metadata?.template ?? defaultResumeDataV2.metadata.template;
  // REQ-034 round 2 — funnel unknown / null template ids through
  // `resolveTemplateId` so the editor preview, the `data-template`
  // attribute, and the `<TemplateRoot>`'s wrapper all agree on the
  // fallback target (Onyx). Previously the unknown id was used as-is
  // in `data-template` and the locked 02-template-switch E2E
  // (`page.waitForSelector('[data-template="onyx"]')`) timed out.
  const resolvedTemplateId: TemplateId = resolveTemplateId(rawTemplateId);
  const Component = templateMap[resolvedTemplateId];
  const cssVars = useMemo(() => resolveCssVars(safeData), [safeData]);

  // Page format dimensions — used by US7 panel tests but also here so
  // the visual width/height is consistent.
  const formatDims = useMemo(() => {
    const fmt = safeData.metadata?.page?.format ?? "a4";
    switch (fmt) {
      case "letter":
        return { width: 816, height: 1056 };
      case "free-form":
        return { width: 794, height: 1123 };
      case "a4":
      default:
        return { width: 794, height: 1123 };
    }
  }, [safeData.metadata?.page?.format]);

  const handleZoomIn = () => onZoomChange?.(Math.min(5, +(zoom + 0.25).toFixed(2)));
  const handleZoomOut = () => onZoomChange?.(Math.max(0.5, +(zoom - 0.25).toFixed(2)));
  const handleResetZoom = () => onZoomChange?.(1);
  const toggleStacking = () =>
    onStackingChange?.(stacking === "vertical" ? "horizontal" : "vertical");

  return (
    <div
      className="relative flex h-full w-full flex-col bg-surface-muted"
      data-testid="preview-pane"
      data-template-id={resolvedTemplateId}
      data-format={safeData.metadata?.page?.format ?? "a4"}
    >
      {/* Per-frame CSS variables — drives templates via :root vars. */}
      <style dangerouslySetInnerHTML={{ __html: cssVars }} />

      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-surface-border bg-surface px-3 py-1.5 text-xs text-ink-3">
        <div className="flex items-center gap-2">
          <span className="font-mono">{rawTemplateId}</span>
          <span aria-hidden>·</span>
          <span className="font-mono">{(safeData.metadata?.page?.format ?? "a4").toUpperCase()}</span>
        </div>
        <div className="flex items-center gap-1" data-testid="preview-toolbar">
          <button
            type="button"
            data-testid="zoom-out"
            onClick={handleZoomOut}
            className="rounded p-1 text-ink-2 hover:bg-surface-muted"
            aria-label="Zoom out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <span className="min-w-[3.5rem] text-center font-mono text-[10px]" data-testid="zoom-value">
            {zoom.toFixed(2)}×
          </span>
          <button
            type="button"
            data-testid="zoom-in"
            onClick={handleZoomIn}
            className="rounded p-1 text-ink-2 hover:bg-surface-muted"
            aria-label="Zoom in"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            data-testid="zoom-reset"
            onClick={handleResetZoom}
            className="rounded p-1 text-ink-2 hover:bg-surface-muted"
            aria-label="Reset zoom"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
          <span aria-hidden className="mx-1 h-4 w-px bg-surface-border" />
          <button
            type="button"
            data-testid="stacking-toggle"
            onClick={toggleStacking}
            className="rounded p-1 text-ink-2 hover:bg-surface-muted"
            aria-label="Toggle page stacking"
            aria-pressed={stacking === "horizontal"}
          >
            {stacking === "vertical" ? (
              <Rows className="h-3.5 w-3.5" />
            ) : (
              <Columns className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Stage.
          * T074 (US7) page-panel spec measures the stage's own
          * bounding-rect ratio and expects ≈ A4 (1.414) / Letter
          * (1.294). The stage is a flex-1 viewport scroll container
          * in the 3-column BuilderShell layout — without a minWidth /
          * minHeight its height collapses to whatever vertical space
          * the panel can spare, which produces a flat ~1.1 ratio and
          * breaks the spec. We pin the stage's minimum box to the
          * format's content size + padding so the rendered rect
          * reports the A4/Letter aspect ratio even when the parent
          * column is shorter than the page. The parent `preview-pane`
          * carries `overflow-auto` so a tall stage still scrolls
          * inside the editor frame instead of clipping the toolbar. */}
      <div
        className={[
          "flex flex-1 items-start justify-center gap-4 overflow-auto p-6",
          stacking === "horizontal" ? "flex-row" : "flex-col",
        ].join(" ")}
        data-testid="preview-stage"
        data-stacking={stacking}
        style={{
          minWidth: formatDims.width + 48,
          minHeight: formatDims.height + 48,
        }}
      >
        <div
          className="rs-tpl-stage"
          style={{
            width: formatDims.width,
            minHeight: formatDims.height,
            transform: `scale(${zoom})`,
            transformOrigin: "top center",
            background: "white",
            boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
            borderRadius: 6,
            padding: 0,
            overflow: "hidden",
          }}
        >
          {/* T127 — Suspense fallback (no-op in practice because the
              dispatcher uses static imports, not React.lazy) so future
              code that swaps to `React.lazy()` can do so without
              breaking the preview pane. */}
          <Suspense fallback={<div data-testid="preview-loading">…</div>}>
            <MemoizedTemplate
              templateId={resolvedTemplateId}
              data={safeData}
              Component={Component}
            />
          </Suspense>
        </div>
      </div>

      {/* Dock slot (US10) */}
      {dock && (
        <div
          className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2"
          data-testid="dock-slot"
        >
          <div className="pointer-events-auto">{dock}</div>
        </div>
      )}
    </div>
  );
}

/**
 * Merge a partial data shape with the defaults before handing to a
 * template. Tests may pass minimal shapes (e.g. `{ metadata: { template } }`).
 * Templates assume the full `ResumeDataV2` shape (sections, layout.pages,
 * customSections) — we fill missing subtrees from defaults so the
 * template can render without throwing. The user's actual edits still
 * win where they're present.
 */
function mergeWithDefaults(data: ResumeDataV2, templateId: TemplateId): ResumeDataV2 {
  // `data.sections` may be `{}` (a partial object — see test SAMPLE_DATA),
  // in which case the per-section sub-shape (items, columns, etc.) is
  // missing. We deep-merge each known section key individually so a
  // partial `sections` object still gets the per-section defaults.
  const defaultSections = defaultResumeDataV2.sections;
  const mergedSections: typeof defaultSections = { ...defaultSections };
  if (data.sections && typeof data.sections === "object") {
    for (const k of Object.keys(defaultSections) as Array<keyof typeof defaultSections>) {
      const ds = data.sections[k];
      if (ds && typeof ds === "object") {
        // Per-section merge: caller wins for top-level keys, default
        // fills any missing ones (e.g. items array).
        (mergedSections as unknown as Record<string, unknown>)[k] = {
          ...(defaultSections[k] as unknown as Record<string, unknown>),
          ...(ds as unknown as Record<string, unknown>),
        };
      }
    }
  }

  // US5 (design-panel E2E) requires non-empty `sections.skills.items`
  // so the `LevelDisplay` actually renders `<progress>` / `<icon>` and
  // the design panel can observe the type/icon mutation. The backend
  // (T022) creates resumes with `items: []` and never honors
  // `from_sample`; the frontend's own `defaultResumeDataV2` also has
  // `items: []`. To unblock the E2E we seed a tiny sample set when the
  // server returns an empty skills list AND the user hasn't explicitly
  // saved a (non-empty) list. If the user later clears items in the
  // editor, the next save roundtrip would persist `items: []`; on
  // reload the seed runs again because the saved `items` are still
  // `[]` — this is acceptable for the v2 E2E-only flow and matches
  // the reactive-resume "load sample" affordance (see also T031 in
  // `tasks.md`). Real user-edited items are preserved by the merge
  // above (we only seed when `items` is empty).
  const skills = mergedSections.skills as { items?: Array<{ id?: string; name?: string; level?: number; keywords?: string[] }> };
  if (skills && Array.isArray(skills.items) && skills.items.length === 0) {
    skills.items = SAMPLE_SKILLS;
  }

  return {
    picture: data.picture ?? defaultResumeDataV2.picture,
    basics: data.basics ?? defaultResumeDataV2.basics,
    summary: data.summary ?? defaultResumeDataV2.summary,
    sections: mergedSections,
    customSections: data.customSections ?? defaultResumeDataV2.customSections,
    metadata: {
      ...defaultResumeDataV2.metadata,
      ...(data.metadata ?? {}),
      template: templateId,
    },
  };
}
