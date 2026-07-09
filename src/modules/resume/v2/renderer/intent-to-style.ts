// T132 — StyleIntent → CSSProperties converter.
//
// Bridges `StyleIntent` (the cross-platform schema shape, shared with
// reactive-resume's PDF renderer) and the inline `style={}` prop that
// React DOM uses. The PDF renderer has its own `toPdfStyle` (different
// key names — `fontSize` vs `font-size`, `backgroundColor` vs
// `background-color`, etc.) — this is its DOM cousin.
//
// Scope: we only emit properties that are valid React inline styles.
// The Schema `.strict()` already rejects unknown keys, so we can iterate
// safely. Numeric properties are clamped via the same ranges the PDF
// renderer uses (see reactive-resume style-rules.ts:33-40) so the on-
// screen preview and the exported PDF can never disagree by more than
// rounding.

import type { CSSProperties } from "react";
import type { StyleIntent } from "../schema/data";

const SPACING_PROPS = [
  "padding",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  "marginTop",
  "marginRight",
  "marginBottom",
  "marginLeft",
  "rowGap",
  "columnGap",
  "borderWidth",
  "borderRadius",
] as const;

const COLOR_PROPS = [
  "color",
  "backgroundColor",
  "borderColor",
  "textDecorationColor",
] as const;

const spacingRange = (
  prop: (typeof SPACING_PROPS)[number],
): { min: number; max: number } => {
  if (prop === "borderWidth") return { min: 0, max: 24 };
  if (prop === "borderRadius") return { min: 0, max: 72 };
  return { min: -72, max: 72 };
};

const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

export function intentToStyle(intent: StyleIntent | undefined): CSSProperties {
  if (!intent) return {};

  const style: Record<string, string | number> = {};

  // Colors pass through verbatim (rgba(r,g,b,a) is valid CSS).
  for (const prop of COLOR_PROPS) {
    const v = intent[prop];
    if (v) style[prop] = v;
  }

  if (intent.opacity !== undefined) {
    style.opacity = clamp(intent.opacity, 0, 1);
  }
  if (intent.fontSize !== undefined) {
    style.fontSize = clamp(intent.fontSize, 6, 48);
  }
  if (intent.fontWeight !== undefined) style.fontWeight = intent.fontWeight;
  if (intent.fontStyle !== undefined) style.fontStyle = intent.fontStyle;
  if (intent.lineHeight !== undefined) {
    style.lineHeight = clamp(intent.lineHeight, 0.5, 4);
  }
  if (intent.letterSpacing !== undefined) {
    style.letterSpacing = clamp(intent.letterSpacing, -16, 16);
  }
  if (intent.textDecoration !== undefined) {
    style.textDecoration = intent.textDecoration;
  }
  if (intent.textDecorationStyle !== undefined) {
    style.textDecorationStyle = intent.textDecorationStyle;
  }
  if (intent.textAlign !== undefined) style.textAlign = intent.textAlign;
  if (intent.textTransform !== undefined) {
    style.textTransform = intent.textTransform;
  }
  if (intent.borderStyle !== undefined) style.borderStyle = intent.borderStyle;

  // Spacing: padding can be a single number or 1-4 array (CSS shorthand).
  // React DOM accepts either form for `padding`. Other props are scalar.
  for (const prop of SPACING_PROPS) {
    if (prop === "padding") {
      const v = intent.padding;
      if (v === undefined) continue;
      const range = spacingRange(prop);
      if (Array.isArray(v)) {
        // React's CSSProperties doesn't list `number[]` for padding, but
        // it accepts it at runtime (it serializes via `toString`). Cast
        // through `unknown` to keep the strict build happy.
        style.padding = v.map((n) => clamp(n, range.min, range.max)) as unknown as string;
      } else {
        style.padding = clamp(v, range.min, range.max);
      }
      continue;
    }
    const v = intent[prop];
    if (v === undefined) continue;
    const range = spacingRange(prop);
    style[prop] = clamp(v, range.min, range.max);
  }

  return style as CSSProperties;
}