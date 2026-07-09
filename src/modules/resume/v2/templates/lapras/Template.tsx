// T042 — Lapras template (rounded header card + floating section titles).
//
// Visual signature:
//   - Top: rounded primary-color header card (like Pikachu but lighter).
//   - Section headings "float" on the section top border — they appear
//     on top of a 1px primary line that runs across the page width.
//   - 2-column layout (left sidebar ~35%, right main ~65%).

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

const LaprasTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "lapras";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.sidebar;
  const sidebarWidth = data.metadata.layout.sidebarWidth;

  return (
    <TemplateRoot template={template} className="rs-tpl-lapras">
      <Header data={data} inverted className="rs-tpl-lapras__header" />
      <div className="rs-tpl-lapras__row">
        {!page.fullWidth && (
          <aside
            className="rs-tpl-lapras__sidebar"
            data-column="sidebar"
            style={{ flexBasis: `${sidebarWidth}%` }}
          >
            {sidebarIds.map((id) => (
              <div
                key={id}
                className="rs-tpl-lapras__section"
                data-section-id={id}
                data-section={id}
              >
                <div className="rs-tpl-lapras__float" data-heading>
                  {sectionHeading(id, data)}
                </div>
                <div className="rs-tpl-lapras__body">
                  <SectionRenderer sectionId={id} data={data} />
                </div>
              </div>
            ))}
          </aside>
        )}
        <main
          className="rs-tpl-lapras__main"
          data-column="main"
          style={page.fullWidth ? { flexBasis: "100%" } : { flexBasis: `${100 - sidebarWidth}%` }}
        >
          {mainIds.map((id) => (
            <div
              key={id}
              className="rs-tpl-lapras__section"
              data-section-id={id}
              data-section={id}
            >
              <div className="rs-tpl-lapras__float" data-heading>
                {sectionHeading(id, data)}
              </div>
              <div className="rs-tpl-lapras__body">
                <SectionRenderer sectionId={id} data={data} />
              </div>
            </div>
          ))}
        </main>
      </div>
    </TemplateRoot>
  );
};

LaprasTemplate.displayName = "LaprasTemplate";
export default LaprasTemplate;
