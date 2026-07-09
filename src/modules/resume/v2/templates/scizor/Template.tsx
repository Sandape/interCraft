// T043 — Scizor template (letterhead editorial).
//
// Visual signature:
//   - Top: full-width primary-color band (letterhead) with name in
//     large uppercase letters.
//   - Body: single column, no sidebar.
//   - Section headings: uppercase, primary color, heavy weight, with
//     letter spacing.
//   - Heavy typography (heavier body weight).

import { type FC } from "react";
import type { ResumeDataV2 } from "../../schema/data";
import type { TemplateId } from "../../schema/templates";
import { TemplateRoot } from "../shared/TemplateRoot";
import { sectionHeading, SectionRenderer } from "../SectionRenderer";
import "./template.css";

export interface TemplateProps {
  data: ResumeDataV2;
}

const ScizorTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "scizor";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.fullWidth ? [] : page.sidebar;

  return (
    <TemplateRoot template={template} className="rs-tpl-scizor">
      <header className="rs-tpl-scizor__letterhead" data-header>
        <h1 className="rs-tpl-scizor__name">{data.basics.name}</h1>
        {data.basics.headline && (
          <div className="rs-tpl-scizor__headline">{data.basics.headline}</div>
        )}
        <div className="rs-tpl-scizor__contact-list" data-contact-list>
          {data.basics.email && <span>{data.basics.email}</span>}
          {data.basics.phone && <span>· {data.basics.phone}</span>}
          {data.basics.location && <span>· {data.basics.location}</span>}
          {data.basics.website.url && (
            <span>· {data.basics.website.label || data.basics.website.url}</span>
          )}
        </div>
      </header>
      <main className="rs-tpl-scizor__main">
        {mainIds.map((id) => (
          <div
            key={id}
            className="rs-tpl-scizor__section"
            data-section-id={id}
            data-section={id}
          >
            <h2 className="rs-tpl-scizor__heading" data-heading>
              {sectionHeading(id, data)}
            </h2>
            <SectionRenderer sectionId={id} data={data} />
          </div>
        ))}
        {sidebarIds.length > 0 && (
          <div className="rs-tpl-scizor__sidebar-block">
            {sidebarIds.map((id) => (
              <div
                key={id}
                className="rs-tpl-scizor__section"
                data-section-id={id}
                data-section={id}
              >
                <h2 className="rs-tpl-scizor__heading" data-heading>
                  {sectionHeading(id, data)}
                </h2>
                <SectionRenderer sectionId={id} data={data} />
              </div>
            ))}
          </div>
        )}
      </main>
    </TemplateRoot>
  );
};

ScizorTemplate.displayName = "ScizorTemplate";
export default ScizorTemplate;
