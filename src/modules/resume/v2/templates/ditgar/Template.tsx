// T039 — Ditgar template (left tint sidebar + 2px item line).
//
// Visual signature:
//   - Left sidebar with tinted (semi-transparent) primary background.
//   - Main column items have a 2px solid primary left border (item
//     "spine" line).
//   - Top header with name + contact list.

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

const DitgarTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "ditgar";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.sidebar;
  const sidebarWidth = data.metadata.layout.sidebarWidth;

  return (
    <TemplateRoot template={template} className="rs-tpl-ditgar">
      <Header data={data} className="rs-tpl-ditgar__header" />
      <div className="rs-tpl-ditgar__row">
        {!page.fullWidth && (
          <aside
            className="rs-tpl-ditgar__sidebar"
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
          className="rs-tpl-ditgar__main"
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

DitgarTemplate.displayName = "DitgarTemplate";
export default DitgarTemplate;
