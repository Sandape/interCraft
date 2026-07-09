// T064 — LevelDisplay primitive.
//
// Renders a 0..5 proficiency indicator in one of 7 modes based on
// `metadata.design.level.type`. Each template uses this for skills
// and languages. The component is pure: the caller passes `level`
// (0..5) + the type + the icon name (only used for `type === "icon"`).
//
// Modes:
//   - hidden           → returns null
//   - circle           → 5 circles, N filled
//   - square           → 5 squares, N filled
//   - rectangle        → 5 rectangles, N filled
//   - rectangle-full   → 1 filled rectangle per N (5 levels of fill)
//   - progress-bar     → <progress value={N} max={5}>
//   - icon             → N copies of the level icon (lucide-react)

import * as Lucide from "lucide-react";
import type { ReactNode } from "react";
import type { LevelType } from "./levels";

export interface LevelDisplayProps {
  level: number;
  type: LevelType;
  icon?: string;
  size?: number;
}

function Shape({
  shape,
  filled,
  size,
}: {
  shape: "circle" | "square" | "rectangle";
  filled: boolean;
  size: number;
}) {
  const base = "inline-block";
  const w = shape === "rectangle" ? size * 1.6 : size;
  const h = size;
  const dim: React.CSSProperties = {
    width: w,
    height: h,
    border: "1px solid currentColor",
    background: filled ? "currentColor" : "transparent",
    marginRight: 2,
    verticalAlign: "middle",
  };
  if (shape === "circle") {
    return (
      <span
        aria-hidden
        className={base}
        style={{
          ...dim,
          borderRadius: "50%",
        }}
      />
    );
  }
  return <span aria-hidden className={base} style={dim} />;
}

function toPascal(name: string): string {
  return name
    .split(/[-_\s]+/)
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : ""))
    .join("");
}

export function LevelDisplay({
  level,
  type,
  icon = "star",
  size = 8,
}: LevelDisplayProps): ReactNode {
  if (type === "hidden") return null;

  const clamped = Math.max(0, Math.min(5, Math.round(level)));

  if (type === "progress-bar") {
    return (
      <progress
        value={clamped}
        max={5}
        data-level-display="progress-bar"
        style={{ width: size * 8, height: size }}
      />
    );
  }

  if (type === "icon") {
    const pascal = toPascal(icon);
    const Cmp =
      (Lucide as unknown as Record<string, React.ComponentType<{ size?: number; className?: string }>>)[pascal] ??
      Lucide.Circle;
    return (
      <span data-level-display="icon" className="inline-flex items-center" aria-hidden>
        {Array.from({ length: clamped }).map((_, i) => (
          <Cmp key={i} size={size} className="text-primary-500" data-level-icon={icon} />
        ))}
      </span>
    );
  }

  if (type === "rectangle-full") {
    // One filled bar of total width, with N/5 fraction filled in
    // primary color. Implementation: an outer rectangle with 5
    // segments, the first N filled.
    return (
      <span
        data-level-display="rectangle-full"
        className="inline-flex items-center"
        aria-hidden
        style={{ verticalAlign: "middle" }}
      >
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className="inline-block"
            style={{
              width: size * 1.6,
              height: size,
              background: i < clamped ? "var(--color-primary)" : "transparent",
              border: "1px solid currentColor",
              marginRight: 1,
            }}
          />
        ))}
      </span>
    );
  }

  // circle | square | rectangle → 5 shapes, N filled.
  const shape: "circle" | "square" | "rectangle" =
    type === "circle" || type === "square" || type === "rectangle" ? type : "circle";

  return (
    <span
      data-level-display={shape}
      className="inline-flex items-center text-primary-500"
      aria-hidden
      style={{ verticalAlign: "middle" }}
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <Shape key={i} shape={shape} filled={i < clamped} size={size} />
      ))}
    </span>
  );
}

export default LevelDisplay;
