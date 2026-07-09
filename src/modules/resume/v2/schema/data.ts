import { z } from "zod";
import type {
  LineHeightPreset,
  MujiThemeId,
  ResumeMarkdownSettings,
  SmartOnePageStatus,
} from "../../renderer/types";

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

export type CustomSectionType = SectionType | "summary";
export type StyleSlot = string;

export interface StyleIntent {
  color?: RgbaColorStr;
  backgroundColor?: RgbaColorStr;
  borderColor?: RgbaColorStr;
  textDecorationColor?: RgbaColorStr;
  opacity?: number;
  fontSize?: number;
  fontWeight?: FontWeight;
  fontStyle?: "normal" | "italic";
  lineHeight?: number;
  letterSpacing?: number;
  textDecoration?: "none" | "underline" | "line-through";
  textDecorationStyle?: "solid" | "dashed" | "dotted";
  textAlign?: "left" | "center" | "right" | "justify";
  textTransform?: "none" | "uppercase" | "lowercase" | "capitalize";
  padding?: number | [number, number, number, number];
  paddingTop?: number;
  paddingRight?: number;
  paddingBottom?: number;
  paddingLeft?: number;
  marginTop?: number;
  marginRight?: number;
  marginBottom?: number;
  marginLeft?: number;
  rowGap?: number;
  columnGap?: number;
  borderStyle?: "solid" | "dashed" | "dotted";
  borderWidth?: number;
  borderRadius?: number;
}

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
  /** Free-form course list (US3). */
  courses: string[];
}

export interface ProjectItem extends ItemBase {
  name: string;
  period: string;
  website: ItemWebsite;
  description: string;
  /** Bullet-style highlights (US3). */
  highlights: string[];
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
  label?: string;
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
  markdown: ResumeMarkdownSettings;
}

export interface ResumeDataV2 {
  picture: PictureConfig;
  basics: Basics;
  summary: Summary;
  sections: Sections;
  customSections: CustomSection[];
  metadata: Metadata;
}

const rgbaRegex =
  /^rgba\(\s*(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*(?:25[0-5]|2[0-4]\d|1?\d?\d)\s*,\s*(?:0|1|0?\.\d+)\s*\)$/;

export const rgbaColorSchema = z.string().regex(rgbaRegex, "Expected rgba(r,g,b,a)");

const fontWeightSchema = z.enum([
  "100",
  "200",
  "300",
  "400",
  "500",
  "600",
  "700",
  "800",
  "900",
]);

const typographyItemSchema = z.object({
  fontFamily: z.string(),
  fontWeights: z.array(fontWeightSchema),
  fontSize: z.number().min(6).max(24),
  lineHeight: z.number().min(0.5).max(4),
});

const itemWebsiteSchema = z.object({
  url: z.string(),
  label: z.string(),
  inlineLink: z.boolean(),
});

const sectionBaseSchema = z.object({
  title: z.string(),
  icon: z.string(),
  columns: z.number().min(1).max(6),
  hidden: z.boolean(),
});

const itemBaseSchema = z.object({
  id: z.string(),
  hidden: z.boolean(),
});

const styleIntentSchema = z
  .object({
    color: rgbaColorSchema.optional(),
    backgroundColor: rgbaColorSchema.optional(),
    borderColor: rgbaColorSchema.optional(),
    textDecorationColor: rgbaColorSchema.optional(),
    opacity: z.number().min(0).max(1).optional(),
    fontSize: z.number().min(6).max(48).optional(),
    fontWeight: fontWeightSchema.optional(),
    fontStyle: z.enum(["normal", "italic"]).optional(),
    lineHeight: z.number().min(0.5).max(4).optional(),
    letterSpacing: z.number().min(-16).max(16).optional(),
    textDecoration: z.enum(["none", "underline", "line-through"]).optional(),
    textDecorationStyle: z.enum(["solid", "dashed", "dotted"]).optional(),
    textAlign: z.enum(["left", "center", "right", "justify"]).optional(),
    textTransform: z.enum(["none", "uppercase", "lowercase", "capitalize"]).optional(),
    padding: z
      .union([
        z.number(),
        z.tuple([z.number(), z.number(), z.number(), z.number()]),
      ])
      .optional(),
    paddingTop: z.number().optional(),
    paddingRight: z.number().optional(),
    paddingBottom: z.number().optional(),
    paddingLeft: z.number().optional(),
    marginTop: z.number().optional(),
    marginRight: z.number().optional(),
    marginBottom: z.number().optional(),
    marginLeft: z.number().optional(),
    rowGap: z.number().optional(),
    columnGap: z.number().optional(),
    borderStyle: z.enum(["solid", "dashed", "dotted"]).optional(),
    borderWidth: z.number().min(0).optional(),
    borderRadius: z.number().min(0).optional(),
  })
  .strict();

const styleRuleSchema = z.object({
  id: z.string(),
  label: z.string().optional(),
  enabled: z.boolean(),
  target: z.union([
    z.object({ scope: z.literal("global") }),
    z.object({ scope: z.literal("sectionType"), sectionType: z.string() }),
    z.object({ scope: z.literal("sectionId"), sectionId: z.string() }),
  ]),
  slots: z.record(z.string(), styleIntentSchema),
});

const mujiThemeIdSchema = z.enum([
  "muji-default-autumn",
  "muji-minimal-color",
  "muji-flat-atmospheric",
] satisfies [MujiThemeId, MujiThemeId, MujiThemeId]);

const lineHeightPresetSchema = z
  .number()
  .int()
  .min(12)
  .max(25)
  .transform((value) => value as LineHeightPreset);

const smartOnePageStatusSchema = z.enum([
  "idle",
  "fit",
  "already-fit",
  "infeasible",
] satisfies [SmartOnePageStatus, SmartOnePageStatus, SmartOnePageStatus, SmartOnePageStatus]);

const markdownPaginationStateSchema = z.enum([
  "idle",
  "measuring",
  "paginated",
  "warning",
  "failed",
]);

const legacyConversionStatusSchema = z.enum([
  "not_needed",
  "pending",
  "converted",
  "warning",
  "failed",
]);

const markdownSettingsSchema = z.object({
  sourceMarkdown: z.string(),
  themeId: mujiThemeIdSchema,
  manualLineHeight: lineHeightPresetSchema,
  smartOnePageEnabled: z.boolean(),
  smartLineHeight: lineHeightPresetSchema.nullable(),
  previousManualLineHeight: lineHeightPresetSchema.nullable(),
  smartStatus: smartOnePageStatusSchema,
  paginationState: markdownPaginationStateSchema,
  pageCount: z.number().int().min(1),
  legacyConversionStatus: legacyConversionStatusSchema,
  legacyConversionWarnings: z.array(z.string()),
});

const sectionTypeSchema = z.enum([
  "profiles",
  "experience",
  "education",
  "projects",
  "skills",
  "languages",
  "interests",
  "awards",
  "certifications",
  "publications",
  "volunteer",
  "references",
]);

export const resumeDataV2Schema = z.object({
  picture: z.object({
    hidden: z.boolean(),
    url: z.string(),
    size: z.number().min(32).max(512),
    rotation: z.number().min(0).max(360),
    aspectRatio: z.number().min(0.5).max(2.5),
    borderRadius: z.number().min(0).max(100),
    borderColor: rgbaColorSchema,
    borderWidth: z.number().min(0),
    shadowColor: rgbaColorSchema,
    shadowWidth: z.number().min(0),
  }),
  basics: z.object({
    name: z.string(),
    headline: z.string(),
    email: z.string(),
    phone: z.string(),
    location: z.string(),
    website: z.object({ url: z.string(), label: z.string() }),
    customFields: z.array(
      z.object({ id: z.string(), icon: z.string(), text: z.string(), link: z.string() }),
    ),
  }),
  summary: sectionBaseSchema.extend({ content: z.string() }),
  sections: z.object({
    profiles: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          icon: z.string(),
          iconColor: rgbaColorSchema,
          network: z.string(),
          username: z.string(),
          website: itemWebsiteSchema,
        }),
      ),
    }),
    experience: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          company: z.string(),
          position: z.string(),
          location: z.string(),
          period: z.string(),
          website: itemWebsiteSchema,
          description: z.string(),
          roles: z.array(
            z.object({
              id: z.string(),
              position: z.string(),
              period: z.string(),
              description: z.string(),
            }),
          ),
        }),
      ),
    }),
    education: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          school: z.string(),
          degree: z.string(),
          area: z.string(),
          grade: z.string(),
          location: z.string(),
          period: z.string(),
          website: itemWebsiteSchema,
          description: z.string(),
          courses: z.array(z.string()),
        }),
      ),
    }),
    projects: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          name: z.string(),
          period: z.string(),
          website: itemWebsiteSchema,
          description: z.string(),
          highlights: z.array(z.string()),
        }),
      ),
    }),
    skills: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          icon: z.string(),
          iconColor: rgbaColorSchema,
          name: z.string(),
          proficiency: z.string(),
          level: z.number().min(0).max(5),
          keywords: z.array(z.string()),
        }),
      ),
    }),
    languages: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          language: z.string(),
          fluency: z.string(),
          level: z.number().min(0).max(5),
        }),
      ),
    }),
    interests: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          icon: z.string(),
          iconColor: rgbaColorSchema,
          name: z.string(),
          keywords: z.array(z.string()),
        }),
      ),
    }),
    awards: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          title: z.string(),
          awarder: z.string(),
          date: z.string(),
          website: itemWebsiteSchema,
          description: z.string(),
        }),
      ),
    }),
    certifications: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          title: z.string(),
          issuer: z.string(),
          date: z.string(),
          website: itemWebsiteSchema,
          description: z.string(),
        }),
      ),
    }),
    publications: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          title: z.string(),
          publisher: z.string(),
          date: z.string(),
          website: itemWebsiteSchema,
          description: z.string(),
        }),
      ),
    }),
    volunteer: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          organization: z.string(),
          location: z.string(),
          period: z.string(),
          website: itemWebsiteSchema,
          description: z.string(),
        }),
      ),
    }),
    references: sectionBaseSchema.extend({
      items: z.array(
        itemBaseSchema.extend({
          name: z.string(),
          position: z.string(),
          website: itemWebsiteSchema,
          phone: z.string(),
          description: z.string(),
        }),
      ),
    }),
  }),
  customSections: z.array(
    sectionBaseSchema.extend({
      id: z.string(),
      type: sectionTypeSchema,
      items: z.array(z.unknown()),
    }),
  ),
  metadata: z.object({
    template: z.string(),
    layout: z.object({
      sidebarWidth: z.number().min(10).max(50),
      pages: z.array(
        z.object({
          fullWidth: z.boolean(),
          main: z.array(z.string()),
          sidebar: z.array(z.string()),
        }),
      ),
    }),
    page: z.object({
      gapX: z.number().min(0).max(200),
      gapY: z.number().min(0).max(200),
      marginX: z.number().min(0).max(200),
      marginY: z.number().min(0).max(200),
      format: z.enum(["a4", "letter", "free-form"]),
      locale: z.string(),
      hideLinkUnderline: z.boolean(),
      hideIcons: z.boolean(),
      hideSectionIcons: z.boolean(),
    }),
    design: z.object({
      level: z.object({ icon: z.string(), type: z.string() }),
      colors: z.object({
        primary: rgbaColorSchema,
        text: rgbaColorSchema,
        background: rgbaColorSchema,
      }),
    }),
    typography: z.object({
      body: typographyItemSchema,
      heading: typographyItemSchema,
    }),
    notes: z.string(),
    styleRules: z.array(styleRuleSchema),
    markdown: markdownSettingsSchema,
  }),
});
