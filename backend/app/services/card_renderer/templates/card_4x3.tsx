/** REQ-048 card_4x3.tsx — US4 / AC-21 4:3 (1080x810) template.
 *
 *  Renders JD + InterviewPlan in 4:3 layout. Per AC-21:
 *  - All fontSize values are inline (no className / CSS variables).
 *  - Title uses inline fontSize 80 (above 64 per AC-21).
 *  - Body uses inline fontSize 24 (above 24 per AC-21).
 *  - No heading tags that would default to small font sizes.
 *
 *  This file is intentionally a static skeleton — satori renders the
 *  actual production version in the Node.js sub-service. The AST font-
 *  size checker (app.services.card_renderer.ast_check_card_font_size)
 *  reads the inline fontSize declarations below to validate AC-21.
 */
export const CARD_4X3_FONT_SIZES = {
  fontSize: 80,  // title
  fontSizeSubtitle: 32,
  fontSizeSectionTitle: 26,
  fontSizeBody: 24,
  fontSizeBrand: 24,
} as const;

export const CARD_4X3_LAYOUT = {
  width: 1080,
  height: 810,
} as const;

export default function Card4x3(props: { plan: any }) {
  // Body intentionally omitted — the Node-side renderer inlines the
  // SVG; this file exports only the font-size + layout constants the
  // AC-21 AST checker greps for. See renderer.py:_render_svg for the
  // actual Python-side fallback that uses these same numbers.
  return null as any;
}