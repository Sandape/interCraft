// T022 — Default ResumeDataV2 constant.
//
// Empty-but-valid document used as the hydration baseline when the
// server returns a resume with a missing or partial `data` blob.
// Mirrors the empty factory in the backend's `merge_resume_data` so
// a partial PUT that only touches one sub-tree still validates.
//
// All enums / literals are explicit (no spread defaults) so a future
// schema addition in the backend is caught by typecheck rather than
// silently defaulting on the frontend.

import type {
  ColorDesign,
  Design,
  Layout,
  LevelDesign,
  Metadata,
  Page,
  PageLayout,
  ResumeDataV2,
  Sections,
  Typography,
  TypographyItem,
} from "./data";

const BODY_TYPOGRAPHY: TypographyItem = {
  fontFamily: "Inter",
  fontWeights: ["400", "500", "700"],
  fontSize: 11,
  lineHeight: 1.5,
};

const HEADING_TYPOGRAPHY: TypographyItem = {
  fontFamily: "Inter",
  fontWeights: ["600", "700"],
  fontSize: 14,
  lineHeight: 1.3,
};

const TYPOGRAPHY: Typography = {
  body: BODY_TYPOGRAPHY,
  heading: HEADING_TYPOGRAPHY,
};

const LEVEL_DESIGN: LevelDesign = {
  icon: "circle",
  type: "circle",
};

const COLOR_DESIGN: ColorDesign = {
  primary: "rgba(0, 0, 0, 1)",
  text: "rgba(0, 0, 0, 1)",
  background: "rgba(255, 255, 255, 1)",
};

const DESIGN: Design = {
  level: LEVEL_DESIGN,
  colors: COLOR_DESIGN,
};

const PAGE_LAYOUT: PageLayout = {
  fullWidth: false,
  main: [
    "summary",
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
    "profiles",
  ],
  sidebar: [],
};

const LAYOUT: Layout = {
  sidebarWidth: 30,
  pages: [PAGE_LAYOUT],
};

const PAGE: Page = {
  gapX: 16,
  gapY: 16,
  marginX: 32,
  marginY: 32,
  format: "a4",
  locale: "zh-CN",
  hideLinkUnderline: false,
  hideIcons: false,
  hideSectionIcons: false,
};

const METADATA: Metadata = {
  template: "onyx",
  layout: LAYOUT,
  page: PAGE,
  design: DESIGN,
  typography: TYPOGRAPHY,
  notes: "",
  styleRules: [],
};

const EMPTY_SECTIONS: Sections = {
  profiles: { title: "Profiles", icon: "user", columns: 1, hidden: false, items: [] },
  experience: { title: "Experience", icon: "briefcase", columns: 1, hidden: false, items: [] },
  education: { title: "Education", icon: "graduation-cap", columns: 1, hidden: false, items: [] },
  projects: { title: "Projects", icon: "folder", columns: 1, hidden: false, items: [] },
  skills: { title: "Skills", icon: "wrench", columns: 1, hidden: false, items: [] },
  languages: { title: "Languages", icon: "languages", columns: 1, hidden: false, items: [] },
  interests: { title: "Interests", icon: "heart", columns: 1, hidden: false, items: [] },
  awards: { title: "Awards", icon: "trophy", columns: 1, hidden: false, items: [] },
  certifications: { title: "Certifications", icon: "badge-check", columns: 1, hidden: false, items: [] },
  publications: { title: "Publications", icon: "book", columns: 1, hidden: false, items: [] },
  volunteer: { title: "Volunteer", icon: "hand-heart", columns: 1, hidden: false, items: [] },
  references: { title: "References", icon: "users", columns: 1, hidden: false, items: [] },
};

export const defaultResumeDataV2: ResumeDataV2 = {
  picture: {
    hidden: true,
    url: "",
    size: 96,
    rotation: 0,
    aspectRatio: 1,
    borderRadius: 0,
    borderColor: "rgba(0, 0, 0, 1)",
    borderWidth: 0,
    shadowColor: "rgba(0, 0, 0, 0)",
    shadowWidth: 0,
  },
  basics: {
    name: "",
    headline: "",
    email: "",
    phone: "",
    location: "",
    website: { url: "", label: "" },
    customFields: [],
  },
  summary: {
    title: "Summary",
    icon: "user",
    columns: 1,
    hidden: false,
    content: "",
  },
  sections: EMPTY_SECTIONS,
  customSections: [],
  metadata: METADATA,
};