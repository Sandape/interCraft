// Header — shared "top of page" renderer used by all templates.
// Templates wrap this in their own structural styles (banner, card, etc.).
//
// The header always shows: name + headline + contact list.
// Templates pass a className to style the wrapper (e.g. "rs-tpl--pikachu-header-card").

import { type ReactNode } from "react";
import type { ResumeDataV2 } from "../../schema/data";
import { Image } from "./primitives";
import { phosphorToLucide } from "../../schema/icon-crosswalk";
import { Lucide } from "../SectionRenderer";

export interface HeaderProps {
  data: ResumeDataV2;
  className?: string;
  /** When true, render text in the inverse color (for colored card headers). */
  inverted?: boolean;
  children?: ReactNode;
}

const contactItem = (iconName: string, content: ReactNode, href?: string) => {
  const IconCmp = (Lucide as unknown as Record<string, React.ComponentType<{ size?: number }>>)[
    toPascal(phosphorToLucide(iconName))
  ] ?? Lucide.Circle;
  const inner = (
    <>
      <IconCmp size={12} />
      {content}
    </>
  );
  if (href) {
    return (
      <a
        href={href}
        target={href.startsWith("http") ? "_blank" : undefined}
        rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
        className="rs-tpl__contact-item"
      >
        {inner}
      </a>
    );
  }
  return (
    <span className="rs-tpl__contact-item">
      {inner}
    </span>
  );
};

const toPascal = (s: string) =>
  s.split(/[-_\s]+/).map((p) => (p ? p[0].toUpperCase() + p.slice(1) : "")).join("");

export const Header = ({ data, className, inverted, children }: HeaderProps) => {
  const { basics, picture } = data;
  const hasPicture = !picture.hidden && Boolean(picture.url);

  return (
    <header
      className={[
        "rs-tpl__header",
        inverted ? "rs-tpl__header--inverted" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      data-header
      data-section-id="basics"
      data-section="basics"
    >
      {hasPicture && (
        <div className="rs-tpl__picture-wrap">
          <Image
            src={picture.url}
            alt={basics.name}
            className="rs-tpl__picture"
          />
        </div>
      )}
      <div className="rs-tpl__header-text">
        <h1 className="rs-tpl__name">{basics.name}</h1>
        {basics.headline && <div className="rs-tpl__headline">{basics.headline}</div>}
        <div className="rs-tpl__contact-list" data-contact-list>
          {basics.email && contactItem("mail", basics.email, `mailto:${basics.email}`)}
          {basics.phone && contactItem("phone", basics.phone, `tel:${basics.phone}`)}
          {basics.location && contactItem("map-pin", basics.location)}
          {basics.website.url &&
            contactItem("globe", basics.website.label || basics.website.url, basics.website.url)}
          {basics.customFields.map((f) => (
            <span key={f.id} className="rs-tpl__contact-item">
              {f.icon && <IconFor name={f.icon} size={12} />}
              {f.text}
            </span>
          ))}
        </div>
        {children}
      </div>
    </header>
  );
};

// Lightweight icon helper (avoids pulling the full Icon primitive in here).
const IconFor = ({ name, size }: { name: string; size: number }) => {
  const pascal = toPascal(phosphorToLucide(name));
  const Cmp = (Lucide as unknown as Record<string, React.ComponentType<{ size?: number }>>)[pascal]
    ?? Lucide.Circle;
  return <Cmp size={size} />;
};
