// T038 — Chikorita template (right solid-color sidebar, inverted text).
//
// Visual signature:
//   - Left main column lists main sections.
//   - Right sidebar is solid primary-color with INVERTED text (white
//     text on primary background).
//   - Top header is split across both columns (left name, right
//     contact).

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

const ChikoritaTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "chikorita";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.sidebar;
  const sidebarWidth = data.metadata.layout.sidebarWidth;

  return (
    <TemplateRoot template={template} className="rs-tpl-chikorita">
      <Header data={data} className="rs-tpl-chikorita__header" />
      <div className="rs-tpl-chikorita__row">
        <main
          className="rs-tpl-chikorita__main"
          data-column="main"
          style={page.fullWidth ? { flexBasis: "100%" } : { flexBasis: `${100 - sidebarWidth}%` }}
        >
          {mainIds.map((id) => (
            <StyledSection key={id} id={id} data={data} title={sectionHeading(id, data)} column="main">
              <SectionRenderer sectionId={id} data={data} />
            </StyledSection>
          ))}
        </main>
        {!page.fullWidth && (
          <aside
            className="rs-tpl-chikorita__sidebar"
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
      </div>
    </TemplateRoot>
  );
};

ChikoritaTemplate.displayName = "ChikoritaTemplate";
export default ChikoritaTemplate;
