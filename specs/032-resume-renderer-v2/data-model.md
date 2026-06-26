# Data Model — Resume Renderer v2

**Feature**: 032-resume-renderer-v2
**Status**: Phase 1 design
**Source of truth**: This document is the canonical model for the v2 spec. Frontend
(Zod) and backend (Pydantic) schemas MUST derive from here.

---

## 1. Entity overview

```
ResumeV2 (1) ──── (1:1) ── ResumeStatisticsV2
   │
   └── (1:1) ── ResumeAnalysisV2
   │
   └── (1:N, embedded jsonb) ── CustomSection
   │
   └── (1:N, embedded jsonb) ── ExperienceItem / EducationItem / ... (typed sections)
```

All resume content lives inside `resumes_v2.data` (jsonb). Statistics and
analysis live in their own tables for write-heavy counter access.

| Table | Purpose | Approx rows / resume |
|---|---|---|
| `resumes_v2` | Authoring + content | 1 |
| `resume_statistics_v2` | Public view/download counters | 1 |
| `resume_analysis_v2` | AI analysis snapshot | 0 or 1 |

---

## 2. `resumes_v2` (DB row)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID (v7) | No | — | PK; client uses for GET/PUT |
| `user_id` | UUID | No | — | FK → `users.id`; cascade on delete |
| `name` | VARCHAR(64) | No | — | Display title in resume list |
| `slug` | VARCHAR(64) | No | — | URL-friendly; UNIQUE per user_id |
| `tags` | TEXT[] | No | `{}` | Free-form filter labels |
| `is_public` | BOOLEAN | No | `false` | Public access switch |
| `is_locked` | BOOLEAN | No | `false` | Owner's permanent read-only flag |
| `password_hash` | TEXT | Yes | NULL | bcrypt; only when `is_public` |
| `data` | JSONB | No | — | `ResumeDataV2` (see §3) |
| `version` | INT | No | `0` | Optimistic concurrency counter |
| `created_at` | TIMESTAMPTZ | No | `now()` | — |
| `updated_at` | TIMESTAMPTZ | No | `now()` | Auto-bump on every PUT |

**Derived fields (API responses only, NOT DB columns)**:

| Field | Source | Used in |
|---|---|---|
| `password_set` | `password_hash IS NOT NULL` | REST API response (`contracts/01-rest-api.md` §1.3, §2.3), SSE event `resume.public-changed` (`contracts/03-sse-events.md` §2.3) |

The DB stores only `password_hash` (bcrypt, nullable). API responses compute `password_set: boolean` to avoid leaking the hash to clients.

**Indexes**:
- `resumes_v2_user_updated_idx (user_id, updated_at DESC)` — list query
- `resumes_v2_user_slug_uq (user_id, slug) UNIQUE` — slug conflict detection
- `resumes_v2_public_idx (user_id, slug) WHERE is_public` — public lookup

**RLS**: `user_id` filter on every read; public lookup uses service-role bypass.

---

## 3. `ResumeDataV2` (jsonb payload)

This is the schema stored in `resumes_v2.data`. Mirrors reactive-resume v5
(`packages/schema/src/resume/data.ts`) with two surgical changes:

1. Drop `cover-letter` from `sectionTypeSchema` (eGGG does not implement cover letters).
2. Drop `customSectionItemSchema` union with cover-letter (cascade from above).

### 3.1 Top-level shape

```ts
interface ResumeDataV2 {
  picture: PictureConfig
  basics: Basics
  summary: Summary                       // singleton, NOT inside sections
  sections: {
    profiles:      ProfilesSection
    experience:    ExperienceSection
    education:     EducationSection
    projects:      ProjectsSection
    skills:        SkillsSection
    languages:     LanguagesSection
    interests:     InterestsSection
    awards:        AwardsSection
    certifications:CertificationsSection
    publications:  PublicationsSection
    volunteer:     VolunteerSection
    references:    ReferencesSection
  }
  customSections: CustomSection[]         // user-defined additions
  metadata: Metadata
}
```

### 3.2 Singletons

```ts
interface PictureConfig {
  hidden: boolean
  url: string                             // local upload path
  size: number                            // 32..512 (pt)
  rotation: number                        // 0..360 (deg)
  aspectRatio: number                     // 0.5..2.5
  borderRadius: number                    // 0..100 (pt)
  borderColor: string                     // rgba(r,g,b,a)
  borderWidth: number                     // >= 0 (pt)
  shadowColor: string
  shadowWidth: number
}

interface Basics {
  name: string
  headline: string
  email: string
  phone: string
  location: string
  website: Website                        // { url, label }
  customFields: CustomField[]             // free-form key/value pairs
}

interface Summary {
  title: string
  icon: IconName                          // lucide-react name (see §6)
  columns: number                         // 1..6
  hidden: boolean
  content: string                         // Tiptap HTML
}

interface CustomField {
  id: string                              // UUID
  icon: IconName
  text: string
  link: string                            // optional URL
}
```

### 3.3 Section base + 12 typed sections

```ts
interface SectionBase {
  title: string
  icon: IconName
  columns: number                         // 1..6
  hidden: boolean
  items: ItemBase[]                       // extended per type below
}

interface ItemBase {
  id: string                              // UUID
  hidden: boolean
}

// Each typed section is `SectionBase & { items: <TypedItem>[] }`
```

| Section | Item fields (beyond base) |
|---|---|
| `profiles` | `network`, `username`, `website: ItemWebsite`, `icon`, `iconColor` |
| `experience` | `company`, `position`, `location`, `period`, `website: ItemWebsite`, `description: html`, `roles: Role[]` |
| `education` | `school`, `degree`, `area`, `grade`, `location`, `period`, `website: ItemWebsite`, `description: html` |
| `projects` | `name`, `period`, `website: ItemWebsite`, `description: html` |
| `skills` | `name`, `proficiency` (text), `level` (0..5), `keywords[]`, `icon`, `iconColor` |
| `languages` | `language`, `fluency`, `level` (0..5) |
| `interests` | `name`, `keywords[]`, `icon`, `iconColor` |
| `awards` | `title`, `awarder`, `date`, `website: ItemWebsite`, `description: html` |
| `certifications` | `title`, `issuer`, `date`, `website: ItemWebsite`, `description: html` |
| `publications` | `title`, `publisher`, `date`, `website: ItemWebsite`, `description: html` |
| `volunteer` | `organization`, `location`, `period`, `website: ItemWebsite`, `description: html` |
| `references` | `name`, `position`, `website: ItemWebsite`, `phone`, `description: html` |

```ts
interface Role {                          // inside experience item
  id: string                              // UUID
  position: string
  period: string
  description: string                     // HTML
}

interface ItemWebsite {                   // richer than Basics.website
  url: string
  label: string
  inlineLink: boolean                     // render on title vs. as separate link
}
```

### 3.4 Custom sections

```ts
interface CustomSection {
  id: string                              // UUID
  type: SectionType                       // one of the 13 (summary excluded from custom)
  title: string
  icon: IconName
  columns: number                         // 1..6
  hidden: boolean
  items: CustomSectionItem[]              // discriminated union by .type
}
```

Custom sections reuse the same item schemas as built-in sections. The schema is
a union (not strictObject) so an item can match the schema of its chosen type.

### 3.5 Metadata

```ts
interface Metadata {
  template: TemplateId                    // one of 10 enum
  layout: Layout
  page: Page
  design: Design
  typography: Typography
  notes: string                           // Tiptap HTML; private to owner
  styleRules: StyleRule[]                 // custom style intent overrides
}

interface Layout {
  sidebarWidth: number                    // 10..50 (%)
  pages: PageLayout[]
}

interface PageLayout {
  fullWidth: boolean                      // collapse sidebar into main
  main: string[]                          // section ids
  sidebar: string[]                       // section ids
}

interface Page {
  gapX: number                            // pt
  gapY: number                            // pt
  marginX: number                         // pt
  marginY: number                         // pt
  format: "a4" | "letter" | "free-form"
  locale: string                          // BCP-47
  hideLinkUnderline: boolean
  hideIcons: boolean
  hideSectionIcons: boolean               // default true
}

interface Design {
  colors: {
    primary: string                       // rgba
    text: string
    background: string
  }
  level: {
    icon: IconName
    type: "hidden" | "circle" | "square" | "rectangle" | "rectangle-full" | "progress-bar" | "icon"
  }
}

interface Typography {
  body: TypographyItem
  heading: TypographyItem
}

interface TypographyItem {
  fontFamily: string                      // e.g. "IBM Plex Serif"
  fontWeights: FontWeight[]               // ["400", "500", ...]
  fontSize: number                        // 6..24 (pt)
  lineHeight: number                      // 0.5..4
}

type FontWeight = "100" | "200" | ... | "900"
```

### 3.6 Style rules

```ts
interface StyleRule {
  id: string
  label: string                           // human-readable, optional
  enabled: boolean
  target:
    | { scope: "global" }
    | { scope: "sectionType", sectionType: SectionType }
    | { scope: "sectionId", sectionId: string }
  slots: StyleRuleSlots                   // partial map of StyleSlot → StyleIntent
}

interface StyleRuleSlots {                // all optional; at least 1 must be set
  section?: StyleIntent
  heading?: StyleIntent
  item?: StyleIntent
  text?: StyleIntent
  secondaryText?: StyleIntent
  link?: StyleIntent
  icon?: StyleIntent
  level?: StyleIntent
  richParagraph?: StyleIntent
  richList?: StyleIntent
  richListItemRow?: StyleIntent
  richListItemContent?: StyleIntent
  richLink?: StyleIntent
  richBold?: StyleIntent
  richMark?: StyleIntent
}

interface StyleIntent {                   // flat CSS-like props
  color?: string
  backgroundColor?: string
  borderColor?: string
  textDecorationColor?: string
  opacity?: number                        // 0..1
  fontSize?: number                       // 6..48
  fontWeight?: FontWeight
  fontStyle?: "normal" | "italic"
  lineHeight?: number                     // 0.5..4
  letterSpacing?: number                  // -16..16
  textDecoration?: "none" | "underline" | "line-through"
  textDecorationStyle?: "solid" | "dashed" | "dotted"
  textAlign?: "left" | "center" | "right" | "justify"
  textTransform?: "none" | "uppercase" | "lowercase" | "capitalize"
  padding?: number | [number, number, number, number]
  paddingTop?: number
  paddingRight?: number
  paddingBottom?: number
  paddingLeft?: number
  marginTop?: number
  marginRight?: number
  marginBottom?: number
  marginLeft?: number
  rowGap?: number
  columnGap?: number
  borderStyle?: "solid" | "dashed" | "dotted"
  borderWidth?: number
  borderRadius?: number
}
```

### 3.7 Resolution algorithm (style rules)

```ts
function resolveStyleIntentForSlot(
  data: ResumeDataV2,
  slot: StyleSlot,
  sectionId: string,
  sectionType?: SectionType
): StyleIntent {
  const matching = data.metadata.styleRules
    .filter(r => r.enabled && r.slots[slot])
    .filter(r => {
      if (r.target.scope === 'global') return true
      if (r.target.scope === 'sectionType') return r.target.sectionType === sectionType
      if (r.target.scope === 'sectionId') return r.target.sectionId === sectionId
      return false
    })

  const specificity = { global: 0, sectionType: 1, sectionId: 2 }
  matching.sort((a, b) => specificity[a.target.scope] - specificity[b.target.scope])

  return Object.assign({}, ...matching.map(r => r.slots[slot]))
}
```

Verbatim from reactive-resume v5 (`packages/schema/src/resume/style-rules.ts:42-64`).

---

## 4. `resume_statistics_v2`

| Column | Type | Default | Notes |
|---|---|---|---|
| `resume_id` | UUID PK | — | FK → `resumes_v2.id` ON DELETE CASCADE |
| `views` | INT | 0 | Public non-owner accesses |
| `downloads` | INT | 0 | Public PDF downloads |
| `last_viewed_at` | TIMESTAMPTZ | NULL | |
| `last_downloaded_at` | TIMESTAMPTZ | NULL | |

Updated atomically: `UPDATE ... SET views = views + 1, last_viewed_at = now() WHERE resume_id = :id`.

---

## 5. `resume_analysis_v2`

| Column | Type | Default | Notes |
|---|---|---|---|
| `resume_id` | UUID PK | — | FK → `resumes_v2.id` ON DELETE CASCADE |
| `analysis` | JSONB | — | Shape per §5.1 |
| `status` | VARCHAR(16) | `'success'` | `'success'` \| `'failed'` |
| `failure_reason` | TEXT | NULL | Free-form failure context |
| `updated_at` | TIMESTAMPTZ | `now()` | Bumped on every re-analyze |

### 5.1 Analysis JSON shape

```ts
interface AnalysisResult {
  overallScore: number                    // 0..100
  dimensions: Array<{
    name: DimensionName
    score: number                          // 0..10
  }>                                      // exactly 10 entries
  strengths: Array<{ text: string }>      // 3..5
  suggestions: Array<{
    impact: "high" | "medium" | "low"
    text: string
    why: string
    exampleRewrite: string                 // optional, may be empty
  }>                                      // 3..5
}

type DimensionName =
  | "contentCompleteness"
  | "quantification"
  | "keywordDensity"
  | "industryFit"
  | "expressionClarity"
  | "formatCompliance"
  | "lengthFit"
  | "skillRelevance"
  | "experienceContinuity"
  | "overallImpact"
```

---

## 6. Icon vocabulary

`IconName` is a string. Frontend uses **lucide-react**; the spec's "1500+ Phosphor"
claim is honored via a name crosswalk.

| Lucide icons in scope | Examples |
|---|---|
| Section icons | `briefcase`, `graduation-cap`, `code`, `wrench`, `languages`, `heart`, `trophy`, `award`, `book-open`, `hand-heart`, `phone`, `user`, `mail`, `map-pin` |
| Profile icons | `github`, `linkedin`, `twitter`, `instagram`, `globe`, `link` |
| Level icons | `star`, `circle`, `square`, `heart`, `trophy`, `crown` |
| Misc UI | `image`, `file-text`, `palette`, `type`, `layout`, `settings` |

A runtime crosswalk `phosphorToLucide()` is provided for import compatibility.
Unknown names fall back to `Circle`.

---

## 7. Template ID enum

```ts
type TemplateId =
  | "onyx"       // minimal text
  | "azurill"    // left sidebar (35%)
  | "kakuna"     // centered header
  | "chikorita"  // right tinted sidebar
  | "ditgar"     // left tint sidebar + 2px item line
  | "bronzor"    // row-style sections
  | "pikachu"    // colored header card
  | "lapras"     // rounded card + floating titles
  | "scizor"     // letterhead + uppercase heading
  | "rhyhorn"    // pipe-separated contact line
```

These 10 are the spec shortlist (US2). Each has a React component + CSS file in
`src/modules/resume/v2/templates/<id>/`.

---

## 8. Validation rules

### 8.1 Field constraints (Zod-equivalent on backend)

| Field | Constraint | Enforced at |
|---|---|---|
| `name` | 1..64 chars | API input + DB column |
| `slug` | `^[a-z0-9-]+$`, 1..64 chars, unique per user | API input (regex + DB unique index) |
| `tag` element | 1..32 chars | API input |
| `password` | 6..64 chars (set via Set Password UI) | API input |
| `summary.content` | ≤ 50,000 chars | Editor + API input |
| `section.items` per section | ≤ 100 items | API input |
| `fontSize` | 6..24 (metadata.typography), 6..48 (style intent) | Schema |
| `lineHeight` | 0.5..4 | Schema |
| `sidebarWidth` | 10..50 (%) | Schema |
| `level` | 0..5 | Schema |

### 8.2 Cross-field rules

- `password_hash` MUST be NULL when `is_public = false` (CHECK constraint).
- `metadata.template` MUST be one of the 10 TemplateId enum values.
- Custom section `items[*]` MUST match the schema for the section's `type`.

### 8.3 Write-path rejections

- Resume with `data_format_version = "v1"` (legacy block) MUST be rejected by any
  v2 endpoint with HTTP 400 + `LEGACY_FORMAT` error code (per FR-012).
- PUT with `If-Match` header missing OR not an integer MUST be rejected (400).
- Resume with `is_locked = true` MUST be rejected on PUT (HTTP 423 Locked).

---

## 9. State transitions

### 9.1 Resume lifecycle

```
            create                update (PUT)
[none] ───────────────► [draft] ◄──────────────┐
                          │                     │
              public on   │    lock on          │
                          ▼                     │
                       [public] ─── lock on ────┤
                          │                     │
              public off  ▼                     │
                       [draft] ─────────────────┘
                          │
                  delete (soft)
                          ▼
                      [deleted]
```

### 9.2 Version counter

```
version=0  ──client PUT v0──►  server: WHERE version=0 → match → version=1
            ──client PUT v0──►  server: WHERE version=0 → no row → 409
                                                  ↓
                                  response: { latest_version: 2, latest_data }
```

---

## 10. Default resume data

`backend/app/modules/resumes_v2/defaults.py` exports `defaultResumeDataV2()`
which returns a `ResumeDataV2` shaped identically to reactive-resume's
`defaultResumeData` (170 lines, ported verbatim). All section icons are
mapped from Phosphor to lucide-react via the crosswalk.

`frontend/src/modules/resume/v2/sample.ts` mirrors this for the editor's
"load sample" affordance.

---

## 11. Relationships summary

| Parent | Child | Cardinality | Cascade on parent delete |
|---|---|---|---|
| users | resumes_v2 | 1:N | CASCADE (resumes + statistics + analysis) |
| resumes_v2 | resume_statistics_v2 | 1:1 | CASCADE |
| resumes_v2 | resume_analysis_v2 | 1:1 | CASCADE |
| resumes_v2.data | customSections | 1:N (embedded) | n/a (jsonb) |
| resumes_v2.data.sections | items | 1:N (embedded) | n/a (jsonb) |
| resumes_v2 | resumes_v2 (duplicate) | 1:N (logical, by user) | None (independent) |

---

## 12. Migration plan

`backend/alembic/versions/0022_032_resumes_v2.py` creates:

1. Three tables with the columns above.
2. Indexes + UNIQUE constraints.
3. CHECK constraint `password_hash IS NULL OR is_public = true`.
4. Trigger `bump_updated_at` on `resumes_v2` BEFORE UPDATE.
5. RLS policy `resumes_v2_user_isolation` for authenticated reads.

No data backfill required (new tables only).