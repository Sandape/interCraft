// SectionRenderer — generic section content renderer used by all templates.
//
// Given a section id (e.g. "experience", "skills") and the full
// `data: ResumeDataV2`, it renders the corresponding section's items
// using shared per-type item components. Templates wrap this in their
// own <Section id="..." title="..."> container.
//
// This mirrors reactive-resume's `packages/pdf/src/templates/shared/sections/`
// primitives but emits HTML instead of React-PDF.

import { type ReactNode } from "react";
import * as Lucide from "lucide-react";
import type { ResumeDataV2 } from "../schema/data";
import { phosphorToLucide } from "../schema/icon-crosswalk";
import { Icon, LevelDisplay, Link } from "./shared/primitives";

export interface SectionRendererProps {
  sectionId: string;
  data: ResumeDataV2;
}

const titleFor = (id: string, data: ResumeDataV2): string => {
  if (id === "summary") return data.summary.title || "个人简介";
  const sec = data.sections[id as keyof typeof data.sections];
  if (sec && "title" in sec) {
    const t = (sec as { title?: string }).title;
    if (t) return t;
  }
  // Default per-type titles (zh-CN default for v2).
  const defaults: Record<string, string> = {
    profiles: "社交账号",
    experience: "工作经历",
    education: "教育经历",
    projects: "项目经验",
    skills: "技能",
    languages: "语言能力",
    interests: "兴趣爱好",
    awards: "荣誉奖项",
    certifications: "认证",
    publications: "出版",
    volunteer: "志愿服务",
    references: "推荐人",
  };
  return defaults[id] ?? id;
};

const iconFor = (id: string, data: ResumeDataV2): string => {
  if (id === "summary") return data.summary.icon;
  const sec = data.sections[id as keyof typeof data.sections];
  if (sec && "icon" in sec) {
    return (sec as { icon?: string }).icon ?? "";
  }
  return "";
};

const HIDDEN = (id: string, data: ResumeDataV2): boolean => {
  if (id === "summary") return data.summary.hidden;
  const sec = data.sections[id as keyof typeof data.sections];
  if (sec && "hidden" in sec) return Boolean((sec as { hidden?: boolean }).hidden);
  return false;
};

export const SectionRenderer = ({ sectionId, data }: SectionRendererProps) => {
  if (HIDDEN(sectionId, data)) return null;
  switch (sectionId) {
    case "summary":
      return <SummaryContent data={data} />;
    case "profiles":
      return <ProfilesSection data={data} />;
    case "experience":
      return <ExperienceSection data={data} />;
    case "education":
      return <EducationSection data={data} />;
    case "projects":
      return <ProjectsSection data={data} />;
    case "skills":
      return <SkillsSection data={data} />;
    case "languages":
      return <LanguagesSection data={data} />;
    case "interests":
      return <InterestsSection data={data} />;
    case "awards":
      return <AwardsSection data={data} />;
    case "certifications":
      return <CertificationsSection data={data} />;
    case "publications":
      return <PublicationsSection data={data} />;
    case "volunteer":
      return <VolunteerSection data={data} />;
    case "references":
      return <ReferencesSection data={data} />;
    default:
      return null;
  }
};

export const sectionHeading = (id: string, data: ResumeDataV2) => {
  if (HIDDEN(id, data)) return null;
  const title = titleFor(id, data);
  const icon = iconFor(id, data);
  if (data.metadata.page.hideSectionIcons) {
    return <h2 className="rs-tpl__section-heading" data-heading data-section-heading>{title}</h2>;
  }
  return (
    <h2 className="rs-tpl__section-heading rs-tpl__section-heading--with-icon" data-heading data-section-heading>
      {icon && <Icon name={icon} data-icon="section" data-section-icon />}
      <span>{title}</span>
    </h2>
  );
};

const SummaryContent = ({ data }: { data: ResumeDataV2 }) => (
  <div
    className="rs-tpl__rich rs-tpl__summary"
    dangerouslySetInnerHTML={{ __html: data.summary.content || "" }}
  />
);

const ProfilesSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__profiles">
    {data.sections.profiles.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        {it.icon && <Icon name={it.icon} data-icon="profile" />}
        <span className="rs-tpl__profile-network">{it.network}</span>
        {it.website.url && (
          <>
            <span className="rs-tpl__sep">·</span>
            <Link
              href={it.website.url}
              label={it.website.label || it.username || it.website.url}
            />
          </>
        )}
      </li>
    ))}
  </ul>
);

const ExperienceSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__experience">
    {data.sections.experience.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item rs-tpl__experience-item">
        <div className="rs-tpl__item-head">
          <span className="rs-tpl__item-title">{it.position}</span>
          {it.company && <span className="rs-tpl__item-org"> @ {it.company}</span>}
          {it.period && <span className="rs-tpl__item-period"> · {it.period}</span>}
        </div>
        {it.location && <div className="rs-tpl__item-meta">{it.location}</div>}
        {it.description && (
          <div
            className="rs-tpl__rich rs-tpl__item-desc"
            dangerouslySetInnerHTML={{ __html: it.description }}
          />
        )}
      </li>
    ))}
  </ul>
);

const EducationSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__education">
    {data.sections.education.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        <div className="rs-tpl__item-head">
          <span className="rs-tpl__item-title">{it.school}</span>
          {it.degree && <span className="rs-tpl__item-org"> · {it.degree}</span>}
          {it.period && <span className="rs-tpl__item-period"> · {it.period}</span>}
        </div>
        {it.area && <div className="rs-tpl__item-meta">{it.area}</div>}
        {it.description && (
          <div
            className="rs-tpl__rich rs-tpl__item-desc"
            dangerouslySetInnerHTML={{ __html: it.description }}
          />
        )}
      </li>
    ))}
  </ul>
);

const ProjectsSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__projects">
    {data.sections.projects.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        <div className="rs-tpl__item-head">
          <span className="rs-tpl__item-title">{it.name}</span>
          {it.period && <span className="rs-tpl__item-period"> · {it.period}</span>}
        </div>
        {it.description && (
          <div
            className="rs-tpl__rich rs-tpl__item-desc"
            dangerouslySetInnerHTML={{ __html: it.description }}
          />
        )}
      </li>
    ))}
  </ul>
);

const SkillsSection = ({ data }: { data: ResumeDataV2 }) => {
  // T064 + design-panel E2E (US5): render a LevelDisplay for each skill
  // so the design-panel spec can observe `[data-section-id="skills"]
  // progress` / `[data-level-icon="heart"]` after changing the level
  // type/icon in the Design panel.
  const levelType = data.metadata?.design?.level?.type ?? "hidden";
  const levelIcon = data.metadata?.design?.level?.icon ?? "star";
  return (
    <ul className="rs-tpl__list rs-tpl__skills">
      {data.sections.skills.items.filter((it) => !it.hidden).map((it) => (
        <li key={it.id} data-item-id={it.id} className="rs-tpl__item rs-tpl__skill-item">
          <span className="rs-tpl__skill-name">{it.name}</span>
          <LevelDisplay level={it.level} type={levelType} icon={levelIcon} />
          {it.keywords.length > 0 && (
            <span className="rs-tpl__skill-keywords">
              {it.keywords.join(" · ")}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
};

const LanguagesSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__languages">
    {data.sections.languages.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item rs-tpl__language-item">
        <span className="rs-tpl__language-name">{it.language}</span>
        {it.fluency && <span className="rs-tpl__language-fluency"> · {it.fluency}</span>}
      </li>
    ))}
  </ul>
);

const InterestsSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__interests">
    {data.sections.interests.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item rs-tpl__interest-item">
        {it.icon && <Icon name={it.icon} data-icon="interest" />}
        <span>{it.name}</span>
        {it.keywords.length > 0 && (
          <span className="rs-tpl__interest-keywords">
            {" — "}
            {it.keywords.join(", ")}
          </span>
        )}
      </li>
    ))}
  </ul>
);

const AwardsSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__awards">
    {data.sections.awards.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        <span className="rs-tpl__item-title">{it.title}</span>
        {it.awarder && <span className="rs-tpl__item-org"> · {it.awarder}</span>}
        {it.date && <span className="rs-tpl__item-period"> · {it.date}</span>}
        {it.description && (
          <div
            className="rs-tpl__rich rs-tpl__item-desc"
            dangerouslySetInnerHTML={{ __html: it.description }}
          />
        )}
      </li>
    ))}
  </ul>
);

const CertificationsSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__certifications">
    {data.sections.certifications.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        <span className="rs-tpl__item-title">{it.title}</span>
        {it.issuer && <span className="rs-tpl__item-org"> · {it.issuer}</span>}
        {it.date && <span className="rs-tpl__item-period"> · {it.date}</span>}
      </li>
    ))}
  </ul>
);

const PublicationsSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__publications">
    {data.sections.publications.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        <span className="rs-tpl__item-title">{it.title}</span>
        {it.publisher && <span className="rs-tpl__item-org"> · {it.publisher}</span>}
        {it.date && <span className="rs-tpl__item-period"> · {it.date}</span>}
      </li>
    ))}
  </ul>
);

const VolunteerSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__volunteer">
    {data.sections.volunteer.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        <span className="rs-tpl__item-title">{it.organization}</span>
        {it.period && <span className="rs-tpl__item-period"> · {it.period}</span>}
        {it.description && (
          <div
            className="rs-tpl__rich rs-tpl__item-desc"
            dangerouslySetInnerHTML={{ __html: it.description }}
          />
        )}
      </li>
    ))}
  </ul>
);

const ReferencesSection = ({ data }: { data: ResumeDataV2 }) => (
  <ul className="rs-tpl__list rs-tpl__references">
    {data.sections.references.items.filter((it) => !it.hidden).map((it) => (
      <li key={it.id} data-item-id={it.id} className="rs-tpl__item">
        <span className="rs-tpl__item-title">{it.name}</span>
        {it.position && <span className="rs-tpl__item-org"> · {it.position}</span>}
        {it.description && (
          <div
            className="rs-tpl__rich rs-tpl__item-desc"
            dangerouslySetInnerHTML={{ __html: it.description }}
          />
        )}
      </li>
    ))}
  </ul>
);

// Re-export Lucide for templates that need to render their own icons
// outside of the SectionRenderer (e.g., a contact header in the Onyx template).
export { Lucide };
