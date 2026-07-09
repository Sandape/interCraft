// T044 — Rhyhorn template (pipe-separated contact line).
//
// Visual signature:
//   - Top header with name + headline + a single-line contact list
//     where items are separated by ` | ` (pipe).
//   - Body: single column, no sidebar.
//   - Section headings: small + underlined with primary color.

import { type FC } from "react";
import type { ResumeDataV2 } from "../../schema/data";
import type { TemplateId } from "../../schema/templates";
import { TemplateRoot } from "../shared/TemplateRoot";
import { sectionHeading, SectionRenderer } from "../SectionRenderer";
import "./template.css";

export interface TemplateProps {
  data: ResumeDataV2;
}

const RhyhornTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "rhyhorn";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.fullWidth ? [] : page.sidebar;

  return (
    <TemplateRoot template={template} className="rs-tpl-rhyhorn">
      <header className="rs-tpl-rhyhorn__header" data-header>
        <h1 className="rs-tpl-rhyhorn__name">{data.basics.name}</h1>
        {data.basics.headline && (
          <div className="rs-tpl-rhyhorn__headline">{data.basics.headline}</div>
        )}
        <div className="rs-tpl-rhyhorn__contact-line" data-contact-list>
          {[
            data.basics.email,
            data.basics.phone,
            data.basics.location,
            data.basics.website.label || data.basics.website.url,
            ...data.basics.customFields.map((f) => f.text),
          ]
            .filter(Boolean)
            .join(" | ")}
        </div>
      </header>
      <main className="rs-tpl-rhyhorn__main">
        {mainIds.map((id) => (
          <div
            key={id}
            className="rs-tpl-rhyhorn__section"
            data-section-id={id}
            data-section={id}
          >
            <h2 className="rs-tpl-rhyhorn__heading" data-heading>
              {sectionHeading(id, data)}
            </h2>
            <SectionRenderer sectionId={id} data={data} />
          </div>
        ))}
        {sidebarIds.length > 0 && (
          <div className="rs-tpl-rhyhorn__sidebar-block">
            {sidebarIds.map((id) => (
              <div
                key={id}
                className="rs-tpl-rhyhorn__section"
                data-section-id={id}
                data-section={id}
              >
                <h2 className="rs-tpl-rhyhorn__heading" data-heading>
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

RhyhornTemplate.displayName = "RhyhornTemplate";
export default RhyhornTemplate;
