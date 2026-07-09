// v1 TemplateId literal union + Gallery registry.
//
// All 10 template IDs map to shipped template implementations. Keep these
// descriptors aligned with the public manifest so product copy does not drift
// back to old MVP placeholder language.

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

/** Lightweight schema describing each template for the Gallery UI. */
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
    description: "Clean single-column resume for ATS-friendly technical roles.",
  },
  azurill: { id: "azurill", label: "Azurill", description: "Two-column business layout with a left sidebar and timeline rhythm." },
  kakuna: { id: "kakuna", label: "Kakuna", description: "Centered single-column layout for academic and research profiles." },
  chikorita: { id: "chikorita", label: "Chikorita", description: "Creative right-sidebar layout with strong section contrast." },
  ditgar: { id: "ditgar", label: "Ditgar", description: "Tinted left sidebar with item rules for engineering resumes." },
  bronzor: { id: "bronzor", label: "Bronzor", description: "Compact row-style business layout with structured section labels." },
  pikachu: { id: "pikachu", label: "Pikachu", description: "Colorful header-card layout with a left sidebar for creative tech roles." },
  lapras: { id: "lapras", label: "Lapras", description: "Rounded card sections with a calmer product and operations feel." },
  scizor: { id: "scizor", label: "Scizor", description: "Editorial letterhead layout for brand, content, and creative leadership." },
  rhyhorn: { id: "rhyhorn", label: "Rhyhorn", description: "Compact professional header with pipe-separated contact details." },
};

/** Alias kept for backward-compat with `templates/index.ts`. The full
 *  template schema lives in `data.ts` as the `TemplateId` union. */
export const templateSchema = TEMPLATE_IDS;
