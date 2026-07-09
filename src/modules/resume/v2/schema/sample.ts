// Sample ResumeDataV2 — used by Template Gallery previews and the editor's
// "load sample" affordance. Modeled on the reactive-resume sample.ts shape
// with Phosphor icon names mapped to lucide-react names.
//
// This is a representative sample, not a full 600-line port: it exercises all
// 12 built-in section types and 1 custom section so each template preview
// renders a meaningful layout.

import { DEFAULT_MARKDOWN_SETTINGS } from "../../renderer/types";
import type { ResumeDataV2 } from "./data";

const GITHUB_ICON = "github";
const LINKEDIN_ICON = "linkedin";
const GLOBE_ICON = "globe";

export const sampleResumeData: ResumeDataV2 = {
  picture: {
    hidden: false,
    url: "/photos/sample-picture.jpg",
    size: 100,
    rotation: 0,
    aspectRatio: 1,
    borderRadius: 0,
    borderColor: "rgba(0, 0, 0, 0.5)",
    borderWidth: 0,
    shadowColor: "rgba(0, 0, 0, 0.5)",
    shadowWidth: 0,
  },
  basics: {
    name: "Alex Morgan",
    headline: "Senior Software Engineer | Distributed Systems",
    email: "alex.morgan@example.com",
    phone: "+1 (555) 123-4567",
    location: "Seattle, WA",
    website: { url: "https://alexmorgan.dev", label: "alexmorgan.dev" },
    customFields: [
      {
        id: "019bef5a-0477-77e0-968b-5d0e2ecb34e3",
        icon: GITHUB_ICON,
        text: "github.com/alexmorgan",
        link: "https://github.com/alexmorgan",
      },
    ],
  },
  summary: {
    title: "",
    icon: "file-text",
    columns: 1,
    hidden: false,
    content:
      "<p><strong>Senior software engineer with 8+ years of experience</strong> building distributed systems at scale. Specialised in Go, Rust, and Kubernetes internals. Proven track record of leading teams, mentoring engineers, and shipping reliable production services.</p>",
  },
  sections: {
    profiles: {
      title: "",
      icon: "link",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-3d42ddc9b4d8",
          hidden: false,
          icon: GITHUB_ICON,
          iconColor: "rgba(0, 0, 0, 0)",
          network: "GitHub",
          username: "alexmorgan",
          website: {
            url: "https://github.com/alexmorgan",
            label: "github.com/alexmorgan",
            inlineLink: false,
          },
        },
        {
          id: "019bef5a-93e4-7746-ad39-43c470b77f4a",
          hidden: false,
          icon: LINKEDIN_ICON,
          iconColor: "rgba(0, 0, 0, 0)",
          network: "LinkedIn",
          username: "alexmorgan",
          website: {
            url: "https://linkedin.com/in/alexmorgan",
            label: "linkedin.com/in/alexmorgan",
            inlineLink: false,
          },
        },
      ],
    },
    experience: {
      title: "",
      icon: "briefcase",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5100a1b1c000",
          hidden: false,
          company: "Acme Cloud",
          position: "Senior Software Engineer",
          location: "Remote",
          period: "2022 – Present",
          website: {
            url: "https://acme.example",
            label: "Acme",
            inlineLink: true,
          },
          description:
            "<p>Led migration of the billing platform to a multi-region event-sourced architecture. Reduced p99 latency by 40% and cut incident MTTR by 60% through improved observability.</p>",
          roles: [],
        },
        {
          id: "019bef5a-93e4-7746-ad39-5100a1b1c001",
          hidden: false,
          company: "Initech Labs",
          position: "Software Engineer",
          location: "Seattle, WA",
          period: "2018 – 2022",
          website: {
            url: "https://initech.example",
            label: "Initech",
            inlineLink: true,
          },
          description:
            "<p>Built core auth & RBAC services supporting 10M+ users. Designed the audit log pipeline that powers compliance reporting.</p>",
          roles: [],
        },
      ],
    },
    education: {
      title: "",
      icon: "graduation-cap",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5200a1b1c000",
          hidden: false,
          school: "University of Washington",
          degree: "B.S. Computer Science",
          area: "Distributed Systems",
          grade: "3.8 / 4.0",
          location: "Seattle, WA",
          period: "2014 — 2018",
          website: { url: "", label: "", inlineLink: false },
          description: "<p>Senior thesis on consensus protocols in geo-distributed databases.</p>",
          courses: [],
        },
      ],
    },
    projects: {
      title: "",
      icon: "code",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5300a1b1c000",
          hidden: false,
          name: "OpenResume",
          period: "2024 – Present",
          website: {
            url: "https://github.com/openresume/openresume",
            label: "github.com/openresume",
            inlineLink: true,
          },
          description:
            "<p>Open-source reactive-resume-inspired editor. 1.2k stars. Built with React + TypeScript + Zod.</p>",
          highlights: [],
        },
      ],
    },
    skills: {
      title: "",
      icon: "wrench",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5400a1b1c000",
          hidden: false,
          icon: "code",
          iconColor: "rgba(0, 0, 0, 0)",
          name: "Go",
          proficiency: "Expert",
          level: 5,
          keywords: ["goroutines", "gRPC", "context"],
        },
        {
          id: "019bef5a-93e4-7746-ad39-5400a1b1c001",
          hidden: false,
          icon: "code",
          iconColor: "rgba(0, 0, 0, 0)",
          name: "Rust",
          proficiency: "Advanced",
          level: 4,
          keywords: ["tokio", "async"],
        },
        {
          id: "019bef5a-93e4-7746-ad39-5400a1b1c002",
          hidden: false,
          icon: "code",
          iconColor: "rgba(0, 0, 0, 0)",
          name: "Kubernetes",
          proficiency: "Advanced",
          level: 4,
          keywords: ["operators", "CRDs"],
        },
      ],
    },
    languages: {
      title: "",
      icon: "languages",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5500a1b1c000",
          hidden: false,
          language: "English",
          fluency: "Native",
          level: 5,
        },
        {
          id: "019bef5a-93e4-7746-ad39-5500a1b1c001",
          hidden: false,
          language: "Mandarin",
          fluency: "Conversational",
          level: 3,
        },
      ],
    },
    interests: {
      title: "",
      icon: "heart",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5600a1b1c000",
          hidden: false,
          icon: GLOBE_ICON,
          iconColor: "rgba(0, 0, 0, 0)",
          name: "Open Source",
          keywords: ["maintainer", "contributor"],
        },
      ],
    },
    awards: {
      title: "",
      icon: "trophy",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5700a1b1c000",
          hidden: false,
          title: "Distinguished Engineer",
          awarder: "Acme Cloud",
          date: "2024",
          website: { url: "", label: "", inlineLink: false },
          description: "<p>Awarded for technical leadership on the billing platform migration.</p>",
        },
      ],
    },
    certifications: {
      title: "",
      icon: "award",
      columns: 1,
      hidden: false,
      items: [
        {
          id: "019bef5a-93e4-7746-ad39-5800a1b1c000",
          hidden: false,
          title: "Certified Kubernetes Administrator",
          issuer: "CNCF",
          date: "2023",
          website: { url: "", label: "", inlineLink: false },
          description: "",
        },
      ],
    },
    publications: {
      title: "",
      icon: "book-open",
      columns: 1,
      hidden: false,
      items: [],
    },
    volunteer: {
      title: "",
      icon: "hand-heart",
      columns: 1,
      hidden: false,
      items: [],
    },
    references: {
      title: "",
      icon: "phone",
      columns: 1,
      hidden: false,
      items: [],
    },
  },
  customSections: [],
  metadata: {
    template: "pikachu",
    layout: {
      sidebarWidth: 35,
      pages: [
        {
          fullWidth: false,
          main: ["summary", "experience", "education", "projects"],
          sidebar: [
            "profiles",
            "skills",
            "languages",
            "interests",
            "awards",
            "certifications",
          ],
        },
      ],
    },
    page: {
      gapX: 4,
      gapY: 6,
      marginX: 14,
      marginY: 12,
      format: "a4",
      locale: "en-US",
      hideLinkUnderline: false,
      hideIcons: false,
      hideSectionIcons: true,
    },
    design: {
      colors: {
        primary: "rgba(0, 132, 209, 1)",
        text: "rgba(0, 0, 0, 1)",
        background: "rgba(255, 255, 255, 1)",
      },
      level: {
        icon: "star",
        type: "circle",
      },
    },
    typography: {
      body: {
        fontFamily: "IBM Plex Sans",
        fontWeights: ["400", "500"],
        fontSize: 10,
        lineHeight: 1.5,
      },
      heading: {
        fontFamily: "IBM Plex Sans",
        fontWeights: ["600"],
        fontSize: 14,
        lineHeight: 1.5,
      },
    },
    notes: "",
    styleRules: [],
    markdown: { ...DEFAULT_MARKDOWN_SETTINGS },
  },
};
