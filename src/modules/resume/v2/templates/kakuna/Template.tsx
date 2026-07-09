// T037 — Kakuna template (centered symmetric).
//
// Visual signature:
//   - Centered header (name, headline, contact horizontally centered).
//   - Body is single-column, centered, with primary-color section
//     headings and a 1px primary border-bottom under each heading.
//   - No sidebar — full width main.
//
// Reactive-resume reference:
//   `D:/Project/reactive-resume/packages/pdf/src/templates/kakuna/KakunaPage.tsx`

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

const KakunaTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "kakuna";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.fullWidth ? [] : page.sidebar;

  return (
    <TemplateRoot template={template} className="rs-tpl-kakuna">
      <Header data={data} className="rs-tpl-kakuna__header" />
      <main className="rs-tpl-kakuna__main">
        {mainIds.map((id) => (
          <StyledSection key={id} id={id} data={data} title={sectionHeading(id, data)} column="main">
            <SectionRenderer sectionId={id} data={data} />
          </StyledSection>
        ))}
        {sidebarIds.length > 0 && (
          <div className="rs-tpl-kakuna__sidebar-block" data-column="sidebar">
            {sidebarIds.map((id) => (
              <StyledSection key={id} id={id} data={data} title={sectionHeading(id, data)} column="sidebar">
                <SectionRenderer sectionId={id} data={data} />
              </StyledSection>
            ))}
          </div>
        )}
      </main>
    </TemplateRoot>
  );
};

KakunaTemplate.displayName = "KakunaTemplate";
export default KakunaTemplate;
