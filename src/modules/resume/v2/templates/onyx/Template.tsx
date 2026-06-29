// T024 — Onyx template (v2 MVP).
//
// Clean single-column resume. The Onyx template is the v2 MVP default
// (`DEFAULT_TEMPLATE_ID = "onyx"` in schema/templates.ts) and the only
// template that renders a real layout in the 032 v2 MVP. All other
// 9 templates fall back to Onyx in `templates/index.ts` so the Gallery
// picker can show 10 thumbnails.
//
// We use plain HTML + inline styles (no CSS file) so the template is
// trivially snapshot-testable under jsdom and can be inlined into the
// export pipeline's HTML payload without a runtime CSS-loader round-trip.

import type { TemplateProps } from "../index";
import type {
  Basics,
  ExperienceItem,
  EducationItem,
  ProjectItem,
  SkillItem,
  LanguageItem,
  ProfileItem,
} from "../../schema/data";

const ROOT_STYLE: React.CSSProperties = {
  fontFamily: "Inter, system-ui, -apple-system, sans-serif",
  color: "#111",
  background: "#fff",
  maxWidth: 820,
  margin: "0 auto",
  padding: "32px 40px",
  lineHeight: 1.5,
  fontSize: 13,
};

const NAME_STYLE: React.CSSProperties = {
  fontSize: 26,
  fontWeight: 700,
  margin: 0,
  letterSpacing: -0.3,
};

const HEADLINE_STYLE: React.CSSProperties = {
  fontSize: 14,
  color: "#555",
  margin: "2px 0 0",
};

const CONTACT_ROW_STYLE: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "4px 14px",
  marginTop: 12,
  fontSize: 12,
  color: "#444",
};

const SUMMARY_STYLE: React.CSSProperties = {
  marginTop: 20,
  paddingTop: 16,
  borderTop: "1px solid #e5e5e5",
};

const SECTION_TITLE_STYLE: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: 1,
  color: "#222",
  margin: "20px 0 8px",
};

const ITEM_TITLE_STYLE: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  margin: 0,
};

const ITEM_META_STYLE: React.CSSProperties = {
  fontSize: 12,
  color: "#666",
  margin: "2px 0 4px",
};

const ITEM_DESC_STYLE: React.CSSProperties = {
  fontSize: 12,
  color: "#333",
  whiteSpace: "pre-wrap",
  margin: "4px 0 0",
};

function ContactRow({ basics }: { basics: Basics }): JSX.Element | null {
  const parts: string[] = [];
  if (basics.email) parts.push(basics.email);
  if (basics.phone) parts.push(basics.phone);
  if (basics.location) parts.push(basics.location);
  if (basics.website?.url) parts.push(basics.website.url);
  for (const f of basics.customFields ?? []) {
    if (f.text) parts.push(f.text);
  }
  if (parts.length === 0) return null;
  return (
    <div style={CONTACT_ROW_STYLE} data-testid="onyx-contact">
      {parts.map((p, i) => (
        <span key={i}>{p}</span>
      ))}
    </div>
  );
}

function SummaryBlock({ content, title }: { content: string; title: string }): JSX.Element | null {
  if (!content) return null;
  return (
    <section style={SUMMARY_STYLE} data-testid="onyx-summary">
      <h2 style={SECTION_TITLE_STYLE}>{title || "Summary"}</h2>
      <p style={{ margin: 0, fontSize: 12 }}>{content}</p>
    </section>
  );
}

function ExperienceBlock({
  items,
  title,
}: {
  items: ExperienceItem[];
  title: string;
}): JSX.Element | null {
  if (!items || items.length === 0) return null;
  return (
    <section data-testid="onyx-experience">
      <h2 style={SECTION_TITLE_STYLE}>{title || "Experience"}</h2>
      {items.map((it) => (
        <div key={it.id} style={{ marginBottom: 12 }}>
          <p style={ITEM_TITLE_STYLE}>{it.position || it.company}</p>
          <p style={ITEM_META_STYLE}>
            {[it.company, it.location, it.period].filter(Boolean).join(" · ")}
          </p>
          {it.description ? <p style={ITEM_DESC_STYLE}>{it.description}</p> : null}
          {it.roles && it.roles.length > 0 ? (
            <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
              {it.roles.map((r) => (
                <li key={r.id} style={{ fontSize: 12 }}>
                  <strong>{r.position}</strong>
                  {r.period ? ` · ${r.period}` : ""}
                  {r.description ? ` — ${r.description}` : ""}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ))}
    </section>
  );
}

function EducationBlock({
  items,
  title,
}: {
  items: EducationItem[];
  title: string;
}): JSX.Element | null {
  if (!items || items.length === 0) return null;
  return (
    <section data-testid="onyx-education">
      <h2 style={SECTION_TITLE_STYLE}>{title || "Education"}</h2>
      {items.map((it) => (
        <div key={it.id} style={{ marginBottom: 12 }}>
          <p style={ITEM_TITLE_STYLE}>{it.school}</p>
          <p style={ITEM_META_STYLE}>
            {[it.degree, it.area, it.period, it.location].filter(Boolean).join(" · ")}
          </p>
          {it.description ? <p style={ITEM_DESC_STYLE}>{it.description}</p> : null}
        </div>
      ))}
    </section>
  );
}

function ProjectsBlock({
  items,
  title,
}: {
  items: ProjectItem[];
  title: string;
}): JSX.Element | null {
  if (!items || items.length === 0) return null;
  return (
    <section data-testid="onyx-projects">
      <h2 style={SECTION_TITLE_STYLE}>{title || "Projects"}</h2>
      {items.map((it) => (
        <div key={it.id} style={{ marginBottom: 12 }}>
          <p style={ITEM_TITLE_STYLE}>{it.name}</p>
          {it.period ? <p style={ITEM_META_STYLE}>{it.period}</p> : null}
          {it.description ? <p style={ITEM_DESC_STYLE}>{it.description}</p> : null}
        </div>
      ))}
    </section>
  );
}

function SkillsBlock({
  items,
  title,
}: {
  items: SkillItem[];
  title: string;
}): JSX.Element | null {
  if (!items || items.length === 0) return null;
  return (
    <section data-testid="onyx-skills">
      <h2 style={SECTION_TITLE_STYLE}>{title || "Skills"}</h2>
      <p style={{ margin: 0, fontSize: 12 }}>
        {items
          .map((s) => s.name)
          .filter(Boolean)
          .join(" · ")}
      </p>
    </section>
  );
}

function LanguagesBlock({
  items,
  title,
}: {
  items: LanguageItem[];
  title: string;
}): JSX.Element | null {
  if (!items || items.length === 0) return null;
  return (
    <section data-testid="onyx-languages">
      <h2 style={SECTION_TITLE_STYLE}>{title || "Languages"}</h2>
      <p style={{ margin: 0, fontSize: 12 }}>
        {items
          .map((l) => `${l.language}${l.fluency ? ` (${l.fluency})` : ""}`)
          .filter(Boolean)
          .join(" · ")}
      </p>
    </section>
  );
}

function ProfilesBlock({
  items,
  title,
}: {
  items: ProfileItem[];
  title: string;
}): JSX.Element | null {
  if (!items || items.length === 0) return null;
  return (
    <section data-testid="onyx-profiles">
      <h2 style={SECTION_TITLE_STYLE}>{title || "Profiles"}</h2>
      <p style={{ margin: 0, fontSize: 12 }}>
        {items
          .map((p) => `${p.network || p.username}`)
          .filter(Boolean)
          .join(" · ")}
      </p>
    </section>
  );
}

function OnyxTemplate({ data }: TemplateProps): JSX.Element {
  const { basics, summary, sections } = data;
  return (
    <div style={ROOT_STYLE} data-template="onyx" data-testid="onyx-template">
      <header>
        <h1 style={NAME_STYLE}>{basics.name || "Your Name"}</h1>
        {basics.headline ? <p style={HEADLINE_STYLE}>{basics.headline}</p> : null}
        <ContactRow basics={basics} />
      </header>
      <SummaryBlock content={summary?.content ?? ""} title={summary?.title ?? "Summary"} />
      <ExperienceBlock
        items={sections.experience?.items ?? []}
        title={sections.experience?.title ?? "Experience"}
      />
      <EducationBlock
        items={sections.education?.items ?? []}
        title={sections.education?.title ?? "Education"}
      />
      <ProjectsBlock
        items={sections.projects?.items ?? []}
        title={sections.projects?.title ?? "Projects"}
      />
      <SkillsBlock
        items={sections.skills?.items ?? []}
        title={sections.skills?.title ?? "Skills"}
      />
      <LanguagesBlock
        items={sections.languages?.items ?? []}
        title={sections.languages?.title ?? "Languages"}
      />
      <ProfilesBlock
        items={sections.profiles?.items ?? []}
        title={sections.profiles?.title ?? "Profiles"}
      />
    </div>
  );
}

export default OnyxTemplate;