// TemplateRoot — wraps each template's body with the structural
// `data-template` attribute + the `.rs-tpl-root` class so the editor can
// scope styles and the gallery can detect which template is rendered.
//
// Every template exports its component wrapped in <TemplateRoot> so
// the dispatcher and the snapshot test only need to look for one
// `data-template="<id>"` attribute on the root.

import { type ReactNode, type CSSProperties } from "react";
import type { TemplateId } from "../../schema/templates";

export interface TemplateRootProps {
  template: TemplateId;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
}

export const TemplateRoot = ({ template, className, style, children }: TemplateRootProps) => {
  return (
    <div
      data-template={template}
      data-template-id={template}
      data-rs-tpl
      data-section-id="basics"
      data-testid="preview-content"
      className={["rs-tpl-root", `rs-tpl--${template}`, className]
        .filter(Boolean)
        .join(" ")}
      style={style}
    >
      {children}
    </div>
  );
};
