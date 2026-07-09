// T036 — Azurill template (left sidebar 35% + right main).
//
// Visual signature:
//   - Top header is full-width with name + headline + horizontal contact
//     row.
//   - Below header: a 2-column flex layout (left sidebar ~35%, right main
//     ~65%) where each column lists its own sections.
//   - When `fullWidth=true`, the sidebar is hidden and main takes 100%.
//
// Reactive-resume reference:
//   `D:/Project/reactive-resume/packages/pdf/src/templates/azurill/AzurillPage.tsx`

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

const AzurillTemplate: FC<TemplateProps> & { displayName: string } = ({ data }) => {
  const template: TemplateId = "azurill";
  const page = data.metadata.layout.pages[0];
  const mainIds = page.main;
  const sidebarIds = page.sidebar;
  const fullWidth = page.fullWidth;
  const sidebarWidth = data.metadata.layout.sidebarWidth;

  return (
    <TemplateRoot template={template} className="rs-tpl-azurill">
      <Header data={data} className="rs-tpl-azurill__header" />
      <div
        className="rs-tpl-azurill__row"
        style={fullWidth ? undefined : { ["--rs-sidebar-width" as string]: `${sidebarWidth}%` }}
      >
        {!fullWidth && (
          <aside
            className="rs-tpl-azurill__sidebar"
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
          className="rs-tpl-azurill__main"
          data-column="main"
          style={fullWidth ? { flexBasis: "100%" } : undefined}
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

AzurillTemplate.displayName = "AzurillTemplate";
export default AzurillTemplate;
