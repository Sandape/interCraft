// T032 — Shared template primitives (HTML, not React-PDF).
//
// These mirror the API surface of reactive-resume's
// `packages/pdf/src/templates/shared/primitives.tsx` so templates can be
// authored once and re-targeted. The only difference is the underlying
// renderer: here we emit React DOM (HTML), not React-PDF <View>.
//
// The `<LevelDisplay>` is implemented in T064 (US5) and is stubbed here
// to `null` for now. All primitives read colors + typography from CSS
// variables defined in `template.css`, which is driven by
// `metadata.design` and `metadata.typography` via inline `:root` styles
// (written by the `<PreviewPane>` in US3, T053).

import { type ReactNode, type CSSProperties } from "react";
import * as Lucide from "lucide-react";
import { phosphorToLucide } from "../../schema/icon-crosswalk";

export interface SectionProps {
  id: string;
  title?: ReactNode;
  /** 1..6 — number of grid columns. We ignore for the v1 (US2) and let
   *  each template decide its own grid behaviour. */
  columns?: number;
  hidden?: boolean;
  /** Column the section lives in (US4 / layout-dnd E2E: lets tests find
   *  a moved section with `[data-section-id="x"][data-column="sidebar"]`
   *  on a single element after a drag). Optional — older call sites omit
   *  it and get no `data-column` attribute. */
  column?: "main" | "sidebar";
  children?: ReactNode;
  /** Optional BEM-style class names layered on top of the base. */
  className?: string;
  /** Inline style override (style rules apply this per slot). */
  style?: CSSProperties;
}

export const Section = ({
  id,
  title,
  hidden,
  column,
  children,
  className,
  style,
}: SectionProps) => {
  if (hidden) return null;
  return (
    <section
      data-section-id={id}
      data-section={id}
      data-column={column}
      className={["rs-tpl__section", `rs-tpl__section--${id}`, className]
        .filter(Boolean)
        .join(" ")}
      style={style}
    >
      {title != null && title !== "" && (
        typeof title === "string" ? (
          <h2 className="rs-tpl__section-heading" data-heading data-section-heading>
            {title}
          </h2>
        ) : (
          // Caller provided a pre-rendered <h2>/<div> — embed as-is.
          <div className="rs-tpl__section-heading-wrap" data-heading data-section-heading>
            {title}
          </div>
        )
      )}
      <div className="rs-tpl__section-body">{children}</div>
    </section>
  );
};

export interface HeadingProps {
  level?: 1 | 2 | 3 | 4 | 5 | 6;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export const Heading = ({ level = 2, children, className, style }: HeadingProps) => {
  const Tag = `h${level}` as const;
  return (
    <Tag
      className={["rs-tpl__heading", `rs-tpl__heading--h${level}`, className]
        .filter(Boolean)
        .join(" ")}
      style={style}
    >
      {children}
    </Tag>
  );
};

export interface TextProps {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  as?: "p" | "span" | "div";
}

export const Text = ({ children, className, style, as = "p" }: TextProps) => {
  const Tag = as;
  return (
    <Tag
      className={["rs-tpl__text", className].filter(Boolean).join(" ")}
      style={style}
    >
      {children}
    </Tag>
  );
};

export interface LinkProps {
  href: string;
  label?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export const Link = ({ href, label, className, style }: LinkProps) => {
  if (!href) return <>{label}</>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={["rs-tpl__link", className].filter(Boolean).join(" ")}
      style={style}
    >
      {label ?? href}
    </a>
  );
};

export interface IconProps {
  /** Lucide icon name. Falls back to Circle when unknown. */
  name?: string;
  className?: string;
  size?: number;
  style?: CSSProperties;
  "data-icon"?: string;
  /** T074 (page-panel E2E) — section heading icons need a
   *  `data-section-icon` attribute so the `hideSectionIcons` toggle
   *  is observable (count goes from 0 to >0). Optional. */
  "data-section-icon"?: boolean;
}

/**
 * Dynamic lucide-react icon renderer. Uses phosphorToLucide() to map
 * Phosphor names (used in the data model) to lucide-react names.
 */
export const Icon = ({
  name,
  className,
  size,
  style,
  "data-icon": dataIconAttr,
  "data-section-icon": dataSectionIcon,
}: IconProps) => {
  const lucideName = phosphorToLucide(name);
  // lucide-react exports icons as PascalCase — convert kebab-case.
  const pascal = toPascalCase(lucideName);
  const Cmp = (Lucide as unknown as Record<string, React.ComponentType<{ size?: number; className?: string; style?: CSSProperties }>>)[pascal]
    ?? Lucide.Circle;
  const iconSize =
    size ??
    (() => {
      const v = parseInt(getCssVar("--rs-icon-size") ?? "12", 10);
      return Number.isFinite(v) ? v : 12;
    })();
  return (
    <Cmp
      size={iconSize}
      className={["rs-tpl__icon", className].filter(Boolean).join(" ")}
      style={style}
      data-icon={dataIconAttr ?? lucideName}
      data-section-icon={dataSectionIcon ? "" : undefined}
    />
  );
};

export interface ImageProps {
  src: string;
  alt?: string;
  className?: string;
  style?: CSSProperties;
}

export const Image = ({ src, alt, className, style }: ImageProps) => {
  if (!src) return null;
  return (
    <img
      src={src}
      alt={alt ?? ""}
      className={["rs-tpl__image", className].filter(Boolean).join(" ")}
      style={style}
    />
  );
};

export interface ContactItemProps {
  icon?: string;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  href?: string;
}

export const ContactItem = ({
  icon,
  children,
  className,
  style,
  href,
}: ContactItemProps) => {
  const content = (
    <>
      {icon && <Icon name={icon} data-icon="contact" />}
      {children && <span className="rs-tpl__contact-text">{children}</span>}
    </>
  );
  if (href) {
    return (
      <a
        href={href}
        className={["rs-tpl__contact-item", className].filter(Boolean).join(" ")}
        style={style}
        target={href.startsWith("http") ? "_blank" : undefined}
        rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
      >
        {content}
      </a>
    );
  }
  return (
    <span
      className={["rs-tpl__contact-item", className].filter(Boolean).join(" ")}
      style={style}
    >
      {content}
    </span>
  );
};

export interface CustomFieldItemProps {
  icon?: string;
  text?: string;
  link?: string;
  className?: string;
  style?: CSSProperties;
}

export const CustomFieldItem = ({
  icon,
  text,
  link,
  className,
  style,
}: CustomFieldItemProps) => {
  if (!text) return null;
  const inner = (
    <>
      {icon && <Icon name={icon} data-icon="custom-field" />}
      <span className="rs-tpl__custom-field-text">{text}</span>
    </>
  );
  if (link) {
    return (
      <a
        href={link}
        className={["rs-tpl__custom-field", className].filter(Boolean).join(" ")}
        style={style}
        target="_blank"
        rel="noopener noreferrer"
      >
        {inner}
      </a>
    );
  }
  return (
    <span
      className={["rs-tpl__custom-field", className].filter(Boolean).join(" ")}
      style={style}
    >
      {inner}
    </span>
  );
};

// ── T064 — LevelDisplay (US5) ─────────────────────────────────────────────
// Re-export the real implementation. Kept here so existing template code
// that imports `LevelDisplay` from primitives continues to work.
export { LevelDisplay } from "./LevelDisplay";

// ── helpers ───────────────────────────────────────────────────────────────

function toPascalCase(name: string): string {
  return name
    .split(/[-_\s]+/)
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : ""))
    .join("");
}

function getCssVar(name: string): string | null {
  if (typeof document === "undefined") return null;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name);
  return v ? v.trim() : null;
}
