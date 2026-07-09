// T132 — StyledSection wrapper.
//
// Drop-in replacement for `<Section>` that resolves the user's style
// rules for the "section" slot and applies them as an inline style
// override on the `<section>` element. Each template switches its
// `<Section id={id}>` to `<StyledSection id={id} data={data}>` and
// the rest of the rendering stays the same.
//
// Why a wrapper and not patching `Section` itself?
//   - `Section` is exported as part of the shared primitives API; many
//     templates + the dispatcher test rely on it staying a pure
//     presentation primitive (no data dependencies).
//   - The wrapper carries the `data` reference, which is what
//     `resolveStyleIntentForSlot` needs to compute the per-slot
//     intent. Templates already pass `data` to their template root, so
//     forwarding it once is cheap.
//
// For now we resolve ONLY the "section" slot. The other 14 slots
// (heading, item, text, secondaryText, link, icon, level, rich*) are
// best-effort in later waves — adding them here would mean patching
// every Heading/Text/Link/Icon call site across all 11 templates.
// Per spec: "For now, apply only to <Section> wrapper (slot: section);
// other slots are best-effort."

import { type ReactNode } from "react";
import { Section } from "./primitives";
import { resolveStyleIntentForSlot } from "../../schema/style-rules";
import { intentToStyle } from "../../renderer/intent-to-style";
import type { ResumeDataV2 } from "../../schema/data";

export interface StyledSectionProps {
  id: string;
  title?: ReactNode;
  columns?: number;
  hidden?: boolean;
  /** Column the section lives in (US4 layout-dnd). Forwarded to
   *  `<Section>` so the rendered element carries `data-column`. */
  column?: "main" | "sidebar";
  data: ResumeDataV2;
  className?: string;
  children?: ReactNode;
}

/**
 * Resolve and apply section-slot style rules. Returns the underlying
 * `<Section>` with the resolved inline style pre-merged into the
 * `style` prop. Empty rules → no style override (template's CSS wins).
 */
export const StyledSection = ({
  id,
  title,
  columns,
  hidden,
  column,
  data,
  className,
  children,
}: StyledSectionProps) => {
  const intent = resolveStyleIntentForSlot(data, {
    slot: "section",
    sectionId: id,
  });
  const style = intentToStyle(intent);
  return (
    <Section
      id={id}
      title={title}
      columns={columns}
      hidden={hidden}
      column={column}
      className={className}
      style={Object.keys(style).length > 0 ? style : undefined}
    >
      {children}
    </Section>
  );
};