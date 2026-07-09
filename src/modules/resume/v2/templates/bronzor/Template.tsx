// T040 — Bronzor template (row-style sections).
//
// Visual signature:
//   - Section title on the LEFT, items listed on the RIGHT (2-col flex
//     within each section).
//   - Top header with name + headline + contact.
//   - Horizontal divider between sections (2px primary line).
//   - No sidebar.

import { type FC } from "react";
import type { ResumeDataV2 } from "../../schema/data";
import type { TemplateId } from "../../schema/templates";
import { TemplateRoot } from "../shared/TemplateRoot";
import { Header } from "../shared/Header";
import { sectionHeading, SectionRenderer } from "../SectionRenderer";
import "./template.css";

export interface TemplateProps {
  data: ResumeDataV2;
}

const BronzorTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "bronzor";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.fullWidth ? [] : page.sidebar;

  return (
    <TemplateRoot template={template} className="rs-tpl-bronzor">
      <Header data={data} className="rs-tpl-bronzor__header" />
      <main className="rs-tpl-bronzor__main">
        {mainIds.map((id) => (
          <div
            key={id}
            className="rs-tpl-bronzor__row"
            data-section-id={id}
            data-section={id}
          >
            <div className="rs-tpl-bronzor__row-title" data-heading>
              {sectionHeading(id, data)}
            </div>
            <div className="rs-tpl-bronzor__row-body">
              <SectionRenderer sectionId={id} data={data} />
            </div>
          </div>
        ))}
        {sidebarIds.length > 0 && (
          <div className="rs-tpl-bronzor__sidebar-block">
            {sidebarIds.map((id) => (
              <div
                key={id}
                className="rs-tpl-bronzor__row"
                data-section-id={id}
                data-section={id}
              >
                <div className="rs-tpl-bronzor__row-title" data-heading>
                  {sectionHeading(id, data)}
                </div>
                <div className="rs-tpl-bronzor__row-body">
                  <SectionRenderer sectionId={id} data={data} />
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </TemplateRoot>
  );
};

BronzorTemplate.displayName = "BronzorTemplate";
export default BronzorTemplate;
