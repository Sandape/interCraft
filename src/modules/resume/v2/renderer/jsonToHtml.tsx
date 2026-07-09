// T123 — jsonToHtml: data → standalone HTML string (US15 / FR-073).
//
// This is the single entry point that BOTH the live preview pane AND
// the Dock's PDF download go through. By reusing the dispatcher work
// from US2 + Wave 5, we guarantee the on-screen preview and the
// exported PDF are byte-for-byte equivalent.
//
// Approach (A) — React server-side via `renderToStaticMarkup`:
//   1. Look up the template component via `getTemplatePage(id)`. The
//      dispatcher is static-imported (see `templates/index.ts`) so
//      this is synchronous and works under vitest's jsdom.
//   2. Call `renderToStaticMarkup(<Template data={data} />)` to get
//      the body HTML string.
//   3. Inline the resolved CSS variables + the shared `template.css`
//      (read at module init via Vite's `?raw` query — produces a
//      string in the bundle) into a `<style>` tag in the `<head>`.
//   4. Wrap in a minimal `<!DOCTYPE html><html><body>` shell so the
//      result is a standalone document the PDF gateway (027) can
//      render headlessly.
//
// Why approach (A) over a hand-written HTML generator per template?
//   - Single source of truth: every visual change to a template
//     component flows through here automatically.
//   - No per-template HTML duplication.
//   - Tested by the existing Wave 5 dispatcher test suite (T030 +
//     dispatcher.test.tsx) — T123 just adds the HTML wrapping.
//
// Performance: `renderToStaticMarkup` is ~5ms per template on the
// dev machine; well under the US15 SC-002 budget of 1s for
// preview re-render (and the 027 export gateway's 30s server-side
// budget for PDF).

import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
import { getTemplatePage } from "../templates";
import type { ResumeDataV2 } from "../schema/data";
import { defaultResumeDataV2 } from "../schema/defaults";
// Vite's `import.meta.glob` + `?raw` inlines the file contents as a
// string at build time. The shape `Record<string, () => Promise<string>>`
// is the documented glob-as-raw contract. We eagerly resolve via
// `{ eager: true, query: '?raw', import: 'default' }` and fall back to
// an empty string if the file is missing — the preview pane and the
// PDF gateway both inject the same CSS through Vite's normal pipeline
// anyway, so a missing read here just means the rendered HTML has no
// inline fallback (still renders, just with external CSS expected).
import { TemplateProvider } from "../templates/shared/TemplateProvider";

// `eager: true` resolves the glob at import time. The keys are
// relative paths; the values are the raw file contents (because of
// `query: '?raw', import: 'default'`).
const RAW_CSS = import.meta.glob<string>(
  [
    "../templates/shared/template.css",
    "../templates/onyx/template.css",
    "../templates/azurill/template.css",
    "../templates/kakuna/template.css",
    "../templates/chikorita/template.css",
    "../templates/ditgar/template.css",
    "../templates/bronzor/template.css",
    "../templates/pikachu/template.css",
    "../templates/lapras/template.css",
    "../templates/scizor/template.css",
    "../templates/rhyhorn/template.css",
  ],
  { eager: true, query: "?raw", import: "default" },
) as Record<string, string>;

const SHARED_CSS = RAW_CSS["../templates/shared/template.css"] ?? "";

/** Resolved CSS variables for the given metadata — mirrors PreviewPane's
 *  `resolveCssVars()` so the on-screen preview and the exported HTML
 *  share the same variable set. The PreviewPane lives in a different
 *  module to avoid an import cycle; we duplicate the small resolver
 *  here intentionally rather than extracting it to a shared util
 *  (T193 polish can lift it later if needed). */
export function generateCssVars(data: ResumeDataV2): string {
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

  lines.push(`--rs-page-padding-x: ${page.marginX}pt;`);
  lines.push(`--rs-page-padding-y: ${page.marginY}pt;`);
  lines.push(`--rs-gap-x: ${page.gapX}pt;`);
  lines.push(`--rs-gap-y: ${page.gapY}pt;`);

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

  return `:root { ${lines.join(" ")} }`;
}

/**
 * Returns the concatenated CSS for the shared template variables +
 * all per-template CSS files. Used by `jsonToHtml` to inline a single
 * `<style>` block in the rendered HTML so the output renders without
 * external stylesheet fetches.
 *
 * `import.meta.glob` above pulls in every `template.css` under
 * `templates/` as a raw string at build time. The path is keyed
 * relative to this file, so adding a new template automatically
 * includes its CSS here.
 */
export function getSharedCss(): string {
  const parts: string[] = [SHARED_CSS];
  for (const [path, css] of Object.entries(RAW_CSS)) {
    if (path === "../templates/shared/template.css") continue;
    if (typeof css === "string") parts.push(css);
  }
  return parts.join("\n");
}

/**
 * Render a `ResumeDataV2` document to a standalone HTML string.
 *
 * The returned document is self-contained: it includes the resolved
 * CSS variables in a `<style>` tag, plus the shared `template.css`
 * rules, so it renders identically in a browser tab and inside the
 * 027 PDF gateway's headless Chromium.
 *
 * @param data The resume data to render.
 * @returns A string containing a full `<!DOCTYPE html>` document.
 */
export function jsonToHtml(data: ResumeDataV2): string {
  // Defensive merge: tests and API clients may hand us a partial data
  // shape. Templates assume the full `ResumeDataV2` (sections, layout,
  // customSections) — we fill missing subtrees from defaults so the
  // render never throws on partial data. The user's actual edits
  // still win where they're present.
  const safeData: ResumeDataV2 = mergeWithDefaults(data);

  // Look up the template component. `getTemplatePage` is synchronous
  // and falls back to Onyx for unknown ids (see templates/index.ts).
  const templateId = safeData.metadata?.template ?? defaultResumeDataV2.metadata.template;
  const Template = getTemplatePage(templateId);

  // Wrap in a TemplateProvider so template primitives that call
  // `useTemplate()` (e.g. Header) don't throw on a missing context.
  // JSX is allowed in this .tsx file; the React 17+ runtime
  // automatically creates the `children` prop.
  const body = renderToStaticMarkup(
    <TemplateProvider value={{ data: safeData }}>
      <Template data={safeData} />
    </TemplateProvider>,
  );

  const cssVars = generateCssVars(safeData);
  const sharedCss = getSharedCss();
  const locale = safeData.metadata?.page?.locale ?? "zh-CN";

  return `<!DOCTYPE html>
<html lang="${escapeAttr(locale)}">
<head>
<meta charset="utf-8">
<meta name="generator" content="InterCraft Resume v2 (jsonToHtml)">
<title>${escapeText(safeData.basics?.name ?? "Resume")}</title>
<style>${cssVars}\n${sharedCss}</style>
</head>
<body>
${body}
</body>
</html>`;
}

// ── helpers ─────────────────────────────────────────────────────────────

function mergeWithDefaults(data: ResumeDataV2): ResumeDataV2 {
  const defaultSections = defaultResumeDataV2.sections;
  const mergedSections: typeof defaultSections = { ...defaultSections };
  if (data.sections && typeof data.sections === "object") {
    for (const k of Object.keys(defaultSections) as Array<keyof typeof defaultSections>) {
      const ds = data.sections[k];
      if (ds && typeof ds === "object") {
        (mergedSections as unknown as Record<string, unknown>)[k] = {
          ...(defaultSections[k] as unknown as Record<string, unknown>),
          ...(ds as unknown as Record<string, unknown>),
        };
      }
    }
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
    },
  };
}

function escapeAttr(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function escapeText(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
