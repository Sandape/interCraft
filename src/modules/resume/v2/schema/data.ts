// T022 — ResumeDataV2 TypeScript interface.
//
// Mirrors `backend/app/modules/resumes_v2/schemas.py:ResumeDataV2Pydantic`.
// Drift between this file and the backend Pydantic model is a
// contract bug per spec contracts/02-resume-data-schema.md §0.
//
// We use `interface` (not `type`) for exportable types so consumers
// can extend / merge them, and so they appear in IDE intellisense as
// structural shapes. Enums use string literal unions to mirror the
// backend `Literal[...]` types.

export type TemplateId =
  | "onyx"
  | "azurill"
  | "kakuna"
  | "chikorita"
  | "ditgar"
  | "bronzor"
  | "pikachu"
  | "lapras"
  | "scizor"
  | "rhyhorn";

export type SectionType =
  | "profiles"
  | "experience"
  | "education"
  | "projects"
  | "skills"
  | "languages"
  | "interests"
  | "awards"
  | "certifications"
  | "publications"
  | "volunteer"
  | "references";

export type FontWeight =
  | "100"
  | "200"
  | "300"
  | "400"
  | "500"
  | "600"
  | "700"
  | "800"
  | "900";

export type LevelType =
  | "hidden"
  | "circle"
  | "square"
  | "rectangle"
  | "rectangle-full"
  | "progress-bar"
  | "icon";

export type PageFormat = "a4" | "letter" | "free-form";

/** rgba(r,g,b,a) string. Frontend never splits this — it forwards verbatim to CSS. */
export type RgbaColorStr = string;

export interface PictureConfig {
  hidden: boolean;
  url: string;
  /** 32..512 */
  size: number;
  /** 0..360 */
  rotation: number;
  /** 0.5..2.5 */
  aspectRatio: number;
  /** 0..100 */
  borderRadius: number;
  borderColor: RgbaColorStr;
  /** >=0 */
  borderWidth: number;
  shadowColor: RgbaColorStr;
  /** >=0 */
  shadowWidth: number;
}

export interface Website {
  url: string;
  label: string;
}

export interface ItemWebsite {
  url: string;
  label: string;
  inlineLink: boolean;
}

export interface CustomField {
  id: string;
  /** Icon name (lucide-style icon key). 1..64 chars. */
  icon: string;
  text: string;
  link: string;
}

export interface Basics {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  website: Website;
  customFields: CustomField[];
}

export interface Summary {
  title: string;
  icon: string;
  /** 1..6 */
  columns: number;
  hidden: boolean;
  content: string;
}

interface ItemBase {
  id: string;
  hidden: boolean;
}

export interface ProfileItem extends ItemBase {
  icon: string;
  iconColor: RgbaColorStr;
  network: string;
  username: string;
  website: ItemWebsite;
}

export interface RoleItem {
  id: string;
  position: string;
  period: string;
  description: string;
}

export interface ExperienceItem extends ItemBase {
  company: string;
  position: string;
  location: string;
  period: string;
  website: ItemWebsite;
  description: string;
  roles: RoleItem[];
}

export interface EducationItem extends ItemBase {
  school: string;
  degree: string;
  area: string;
  grade: string;
  location: string;
  period: string;
  website: ItemWebsite;
  description: string;
}

export interface ProjectItem extends ItemBase {
  name: string;
  period: string;
  website: ItemWebsite;
  description: string;
}

export interface SkillItem extends ItemBase {
  icon: string;
  iconColor: RgbaColorStr;
  name: string;
  proficiency: string;
  /** 0..5 */
  level: number;
  keywords: string[];
}

export interface LanguageItem extends ItemBase {
  language: string;
  fluency: string;
  /** 0..5 */
  level: number;
}

export interface InterestItem extends ItemBase {
  icon: string;
  iconColor: RgbaColorStr;
  name: string;
  keywords: string[];
}

export interface AwardItem extends ItemBase {
  title: string;
  awarder: string;
  date: string;
  website: ItemWebsite;
  description: string;
}

export interface CertificationItem extends ItemBase {
  title: string;
  issuer: string;
  date: string;
  website: ItemWebsite;
  description: string;
}

export interface PublicationItem extends ItemBase {
  title: string;
  publisher: string;
  date: string;
  website: ItemWebsite;
  description: string;
}

export interface VolunteerItem extends ItemBase {
  organization: string;
  location: string;
  period: string;
  website: ItemWebsite;
  description: string;
}

export interface ReferenceItem extends ItemBase {
  name: string;
  position: string;
  website: ItemWebsite;
  phone: string;
  description: string;
}

interface SectionBase {
  title: string;
  icon: string;
  /** 1..6 */
  columns: number;
  hidden: boolean;
}

export interface ProfilesSection extends SectionBase {
  items: ProfileItem[];
}

export interface ExperienceSection extends SectionBase {
  items: ExperienceItem[];
}

export interface EducationSection extends SectionBase {
  items: EducationItem[];
}

export interface ProjectsSection extends SectionBase {
  items: ProjectItem[];
}

export interface SkillsSection extends SectionBase {
  items: SkillItem[];
}

export interface LanguagesSection extends SectionBase {
  items: LanguageItem[];
}

export interface InterestsSection extends SectionBase {
  items: InterestItem[];
}

export interface AwardsSection extends SectionBase {
  items: AwardItem[];
}

export interface CertificationsSection extends SectionBase {
  items: CertificationItem[];
}

export interface PublicationsSection extends SectionBase {
  items: PublicationItem[];
}

export interface VolunteerSection extends SectionBase {
  items: VolunteerItem[];
}

export interface ReferencesSection extends SectionBase {
  items: ReferenceItem[];
}

export interface Sections {
  profiles: ProfilesSection;
  experience: ExperienceSection;
  education: EducationSection;
  projects: ProjectsSection;
  skills: SkillsSection;
  languages: LanguagesSection;
  interests: InterestsSection;
  awards: AwardsSection;
  certifications: CertificationsSection;
  publications: PublicationsSection;
  volunteer: VolunteerSection;
  references: ReferencesSection;
}

export interface CustomSection extends SectionBase {
  id: string;
  type: SectionType;
  /** Free-form per the backend — typed as unknown to avoid coupling. */
  items: unknown[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Style rules + metadata
// ─────────────────────────────────────────────────────────────────────────────

export interface TypographyItem {
  fontFamily: string;
  fontWeights: FontWeight[];
  /** 6..24 */
  fontSize: number;
  /** 0.5..4 */
  lineHeight: number;
}

export interface Typography {
  body: TypographyItem;
  heading: TypographyItem;
}

export interface PageLayout {
  fullWidth: boolean;
  main: string[];
  sidebar: string[];
}

export interface Layout {
  /** 10..50 */
  sidebarWidth: number;
  pages: PageLayout[];
}

export interface Page {
  /** 0..200 */
  gapX: number;
  /** 0..200 */
  gapY: number;
  /** 0..200 */
  marginX: number;
  /** 0..200 */
  marginY: number;
  format: PageFormat;
  /** ^[a-z]{2}(-[A-Z]{2})?$ */
  locale: string;
  hideLinkUnderline: boolean;
  hideIcons: boolean;
  hideSectionIcons: boolean;
}

export interface LevelDesign {
  icon: string;
  type: LevelType;
}

export interface ColorDesign {
  primary: RgbaColorStr;
  text: RgbaColorStr;
  background: RgbaColorStr;
}

export interface Design {
  level: LevelDesign;
  colors: ColorDesign;
}

export interface StyleRule {
  id: string;
  label: string;
  enabled: boolean;
  /** discriminated union — narrowed by `target.scope`. */
  target:
    | { scope: "global" }
    | { scope: "sectionType"; sectionType: SectionType }
    | { scope: "sectionId"; sectionId: string };
  slots: Record<string, unknown>;
}

export interface Metadata {
  template: TemplateId;
  layout: Layout;
  page: Page;
  design: Design;
  typography: Typography;
  notes: string;
  styleRules: StyleRule[];
}

export interface ResumeDataV2 {
  picture: PictureConfig;
  basics: Basics;
  summary: Summary;
  sections: Sections;
  customSections: CustomSection[];
  metadata: Metadata;
}