// T045 — TemplateId literal union + Gallery registry.
//
// All 10 template IDs must exist here so the Template Gallery picker
// can render 10 thumbnails even though only Onyx actually renders
// in the 032 v2 MVP. The dispatcher (templates/index.ts) maps the
// other 9 ids to OnyxTemplate as a placeholder fallback.
//
// When the real templates ship (after MVP), each entry should be
// replaced with the matching component import.

import type { TemplateId } from "./data";

export type { TemplateId };

export const TEMPLATE_IDS: TemplateId[] = [
  "onyx",
  "azurill",
  "kakuna",
  "chikorita",
  "ditgar",
  "bronzor",
  "pikachu",
  "lapras",
  "scizor",
  "rhyhorn",
];

export const DEFAULT_TEMPLATE_ID: TemplateId = "onyx";

/** Lightweight schema describing each template for the Gallery UI.
 *  The MVP only ships real metadata for Onyx; the other 9 reuse
 *  the Onyx preview as a placeholder so the Gallery picker can be
 *  exercised in E2E tests before the real templates ship. */
export interface TemplateDescriptor {
  id: TemplateId;
  /** Display label shown in the Gallery thumbnail header. */
  label: string;
  /** Short description for the Gallery tooltip. */
  description: string;
}

export const TEMPLATE_DESCRIPTORS: Record<TemplateId, TemplateDescriptor> = {
  onyx: {
    id: "onyx",
    label: "Onyx",
    description: "Clean single-column resume — the v2 MVP default.",
  },
  azurill: { id: "azurill", label: "Azurill", description: "(placeholder — uses Onyx in MVP)" },
  kakuna: { id: "kakuna", label: "Kakuna", description: "(placeholder — uses Onyx in MVP)" },
  chikorita: { id: "chikorita", label: "Chikorita", description: "(placeholder — uses Onyx in MVP)" },
  ditgar: { id: "ditgar", label: "Ditgar", description: "(placeholder — uses Onyx in MVP)" },
  bronzor: { id: "bronzor", label: "Bronzor", description: "(placeholder — uses Onyx in MVP)" },
  pikachu: { id: "pikachu", label: "Pikachu", description: "(placeholder — uses Onyx in MVP)" },
  lapras: { id: "lapras", label: "Lapras", description: "(placeholder — uses Onyx in MVP)" },
  scizor: { id: "scizor", label: "Scizor", description: "(placeholder — uses Onyx in MVP)" },
  rhyhorn: { id: "rhyhorn", label: "Rhyhorn", description: "(placeholder — uses Onyx in MVP)" },
};

/** Alias kept for backward-compat with `templates/index.ts`. The full
 *  template schema lives in `data.ts` as the `TemplateId` union. */
export const templateSchema = TEMPLATE_IDS;