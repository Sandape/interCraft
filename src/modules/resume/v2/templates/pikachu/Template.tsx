// T041 — Pikachu template (colored header card + left sidebar).
//
// Visual signature:
//   - Top of page: solid primary-color rounded card with name +
//     headline + contact (text inverted, white-on-primary).
//   - Below the card: 2-column flex (left sidebar ~35%, right main
//     ~65%).

import { type FC } from "react";
import type { ResumeDataV2 } from "../../schema/data";
import type { TemplateId } from "../../schema/templates";
import { TemplateRoot } from "../shared/TemplateRoot";
import { Header } from "../shared/Header";
import { StyledSection } from "../shared/StyledSection";
import { sectionHeading, SectionRenderer } from "../SectionRenderer";
import "./template.css";

export interface TemplateProps {
  data: ResumeDataV2;
}

const PikachuTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "pikachu";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.sidebar;
  const sidebarWidth = data.metadata.layout.sidebarWidth;

  return (
    <TemplateRoot template={template} className="rs-tpl-pikachu">
      <Header data={data} inverted className="rs-tpl-pikachu__header" />
      <div className="rs-tpl-pikachu__row">
        {!page.fullWidth && (
          <aside
            className="rs-tpl-pikachu__sidebar"
            data-column="sidebar"
            style={{ flexBasis: `${sidebarWidth}%` }}
          >
            {sidebarIds.map((id) => (
              <StyledSection key={id} id={id} data={data} title={sectionHeading(id, data)} column="sidebar">
                <SectionRenderer sectionId={id} data={data} />
              </StyledSection>
            ))}
          </aside>
        )}
        <main
          className="rs-tpl-pikachu__main"
          data-column="main"
          style={page.fullWidth ? { flexBasis: "100%" } : { flexBasis: `${100 - sidebarWidth}%` }}
        >
          {mainIds.map((id) => (
            <StyledSection key={id} id={id} data={data} title={sectionHeading(id, data)} column="main">
              <SectionRenderer sectionId={id} data={data} />
            </StyledSection>
          ))}
        </main>
      </div>
    </TemplateRoot>
  );
};

PikachuTemplate.displayName = "PikachuTemplate";
export default PikachuTemplate;
