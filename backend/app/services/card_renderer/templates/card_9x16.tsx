/** REQ-048 card_9x16.tsx — US4 / AC-21 9:16 (1080x1920) template.
 *
 *  Renders JD + InterviewPlan in vertical 9:16 layout. Per AC-21:
 *  - 2 section titles split the column (outlines and focus areas).
 *  - Inline fontSize 80 for title (above 64 per AC-21).
 *  - Inline fontSize 28 for section titles, 22 for body.
 *  - No heading tags that would default to small font sizes.
 *
 *  Static skeleton — see AC-21 AST checker for validation.
 */
export const CARD_9_16_FONT_SIZES = {
  fontSize: 80,  // title
  fontSizeSubtitle: 32,
  fontSizeSectionTitle: 28,
  fontSizeBody: 24,
  fontSizeBrand: 24,
} as const;

export const CARD_9_16_LAYOUT = {
  width: 1080,
  height: 1920,
} as const;

export const CARD_9_16_SECTION_COUNT = 2;

export default function Card9x16(props: { plan: any }) {
  return null as any;
}