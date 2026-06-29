// T045 — Template dispatcher.
//
// `templateMap` maps each TemplateId to a React component.
// `getTemplatePage(id)` returns the component (falling back to Onyx for
// unknown ids) — this is the single entry point used by the editor
// preview, the export pipeline, and the snapshot tests.
//
// REQ-032 v2 MVP scope: only Onyx has a real component. The other
// 9 TemplateIds are placeholder fallbacks — they all resolve to the
// Onyx template so the Template Gallery picker can render 10
// thumbnails without crashing. When the real templates ship
// (after MVP), replace each entry with the matching `import`
// + component reference.

import type { ComponentType } from "react";
import type { TemplateId } from "../schema/templates";
import type { ResumeDataV2 } from "../schema/data";

import OnyxTemplate from "./onyx/Template";

export interface TemplateProps {
  data: ResumeDataV2;
}

export type TemplateComponent = ComponentType<TemplateProps>;

export const templateMap: Record<TemplateId, TemplateComponent> = {
  onyx: OnyxTemplate,
  // 9/10 templates are placeholders for the 032 v2 MVP — they fall
  // back to Onyx until the real layouts ship.
  azurill: OnyxTemplate,
  kakuna: OnyxTemplate,
  chikorita: OnyxTemplate,
  ditgar: OnyxTemplate,
  bronzor: OnyxTemplate,
  pikachu: OnyxTemplate,
  lapras: OnyxTemplate,
  scizor: OnyxTemplate,
  rhyhorn: OnyxTemplate,
};

/**
 * REQ-034 round 2 — Returns the canonical `TemplateId` for an arbitrary
 * string, falling back to `"onyx"` for unknown / null / undefined ids.
 *
 * This is the single source of truth for the unknown-template fallback
 * (REQ-034: PUT with `metadata.template = "definitely-not-a-template"`
 * must still render Onyx in the editor preview). Callers (PreviewPane,
 * MemoizedTemplate) use this to resolve the effective id BEFORE
 * indexing into `templateMap` or rendering `<TemplateRoot template={id}>`
 * — otherwise the unknown id leaks into the DOM as `data-template`
 * and the fallback never appears.
 *
 * Unrecognized ids are also logged via `console.warn` so production
 * debugging surfaces them immediately (previously a silent fallback
 * made E2E failures hard to diagnose).
 */
export function resolveTemplateId(id: string | null | undefined): TemplateId {
  if (id && (id as TemplateId) in templateMap) {
    return id as TemplateId;
  }
  if (id) {
    // Unknown id from server / store / legacy PUT — fall back to onyx.
    // Log only in dev to avoid noise in production logs.
    if (typeof console !== "undefined" && typeof console.warn === "function") {
      console.warn(
        `[v2 templates] Unknown template id "${id}" — falling back to "onyx".`,
      );
    }
  }
  return "onyx";
}

/**
 * Returns the template component for the given id, falling back to Onyx
 * for unknown ids. Wrap in `<Suspense>` if you switch this back to
 * `React.lazy()` later (currently it returns a synchronous component).
 */
export function getTemplatePage(id: string | null | undefined): TemplateComponent {
  return templateMap[resolveTemplateId(id)];
}

export { TEMPLATE_IDS, templateSchema } from "../schema/templates";