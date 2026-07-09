# Feature Specification: Resume Editor v3 for InterCraft v2

**Feature Branch**: `047-resume-editor-v3`  
**Created**: 2026-07-06  
**Status**: Draft - clarified for planning  
**Scope Version**: InterCraft v2 product development; all earlier REQ directories are sealed v1 historical/baseline material unless explicitly reopened by this spec.

## Input

User request: create the InterCraft v2 version of the v3 resume editor requirements after hands-on competitor research in Muji CV. Current v3 scope is limited to:

1. Markdown resume rendering
2. 3 resume rendering themes
3. Line spacing adjustment
4. Smart one-page
5. Export to PDF or Markdown

Competitor evidence: `docs/evidence/v3-editor-research/muji-2026-07-06/RESEARCH.md`.

## Clarifications

### Session 2026-07-06

- Q: Should v3 support Muji-style custom resume containers and icon tokens, or use InterCraft-specific syntax? → A: Fully replicate Muji's scoped functionality and rendering effects.
- Q: Which three Muji themes are in scope for the first version? → A: 默认（秋风同款）, 极简色, and 平面大气主题.
- Q: How should smart one-page interact with manual line spacing? → A: While enabled, smart one-page temporarily overrides manual line spacing; when disabled, the previous manual line spacing is restored.
- Q: What exact line spacing range should InterCraft expose? → A: Replicate Muji's integer presets from 12 through 25.
- Q: What Markdown image sources should the first version support? → A: Support external URL images rendered from Markdown; do not include local upload or crop tools in this scope.

## Goals

- Provide a Markdown-first resume editor where the source text and rendered resume stay understandable and predictable.
- Ship exactly three Muji-compatible resume rendering themes that preserve the same Markdown content while changing visual presentation: 默认（秋风同款）, 极简色, and 平面大气主题.
- Let users manually adjust line spacing and understand how it affects the rendered resume.
- Offer a smart one-page mode that automatically fits a resume onto one page when feasible.
- Export the current resume as PDF and Markdown with clear, reliable outcomes.
- In the first scoped version, replicate Muji CV's observed functionality and rendering effects for Markdown dialect, the three selected themes, line spacing, smart one-page, and PDF/MD export behavior.

## Non-Goals

- Structured form editing for every resume section.
- AI rewrite, AI scoring, or job-description matching.
- Template marketplace, sharing/public links, variants, version history, analytics, or migration from historical resume data.
- Local image upload, image editing, or image cropping beyond rendering Markdown external URL image syntax.
- Reopening or reclassifying sealed v1 requirements.

## User Scenarios & Testing

### User Story 1 - Markdown Resume Rendering (Priority: P1)

As a resume author, I want to write my resume in Markdown and see a faithful resume preview, so that I can control content quickly without fighting a complex form.

**Why this priority**: Markdown rendering is the core of this scoped editor. Themes, line spacing, smart one-page, and export all depend on a stable render model.

**Independent Test**: Paste a representative Markdown resume containing headings, contact info, paragraphs, bold, italic, links, inline code tags, lists, tables, and images; verify the preview renders each supported syntax according to the documented rules.

**Acceptance Scenarios**:

1. **Given** Markdown contains one H1, **When** the preview renders, **Then** H1 is treated as the resume title.
2. **Given** Markdown contains H2 headings, **When** the preview renders, **Then** each H2 becomes a major resume section.
3. **Given** Markdown contains H3 headings under an H2, **When** the preview renders, **Then** each H3 becomes a section item title.
4. **Given** Markdown contains bold, italic, bold-italic, strikethrough, links, and inline code, **When** the preview renders, **Then** each inline format is visually distinct and remains readable in export.
5. **Given** Markdown contains unordered, ordered, and nested lists, **When** the preview renders, **Then** list hierarchy is visible and does not overflow the page width.
6. **Given** Markdown contains a table, **When** the preview renders, **Then** the table becomes a resume-appropriate column layout rather than a visually heavy code-document table.
7. **Given** Markdown contains external URL image syntax, **When** the preview renders, **Then** the image renders in the resume preview when the URL is reachable.
8. **Given** Markdown contains unsupported syntax, **When** the preview renders, **Then** the editor preserves the source and shows a predictable fallback rather than silently deleting content.

---

### User Story 2 - Three Resume Themes (Priority: P1)

As a resume author, I want to switch among three polished rendering themes, so that I can choose a style appropriate for different roles without rewriting content.

**Why this priority**: Theme switching is the main visual customization in the scoped v3 editor.

**Independent Test**: Apply each of the three themes to the same Markdown resume and verify the source Markdown remains unchanged while title, section headings, typography, spacing, and accents update.

**Acceptance Scenarios**:

1. **Given** a resume has Markdown content, **When** the user applies 默认（秋风同款）, **Then** the preview matches the observed Muji dark-header and centered-section-label rendering pattern.
2. **Given** the same resume, **When** the user applies 极简色, **Then** the preview matches the observed Muji minimal line-based rendering pattern.
3. **Given** the same resume, **When** the user applies 平面大气主题, **Then** the preview matches the observed Muji accent-band rendering pattern.
4. **Given** the user switches themes repeatedly, **When** they inspect the Markdown source, **Then** the source content is unchanged.
5. **Given** a theme is active, **When** the user exports PDF, **Then** the exported PDF matches that active theme.

---

### User Story 3 - Line Spacing Adjustment (Priority: P1)

As a resume author, I want to adjust line spacing, so that I can balance readability and page fit without manually rewriting content.

**Why this priority**: Resume layout is sensitive to vertical space, especially for one-page resumes.

**Independent Test**: Change line spacing through the available control and compare preview before and after for paragraphs, lists, tables, and headings.

**Acceptance Scenarios**:

1. **Given** a resume is open, **When** the user opens the line spacing control, **Then** it exposes integer presets from 12 through 25.
2. **Given** a resume is open, **When** the user changes line spacing, **Then** the preview updates immediately.
3. **Given** the line spacing value changes, **When** the user inspects body text, lists, and tables, **Then** those elements visibly compress or expand.
4. **Given** a theme defines its own section heading decoration, **When** line spacing changes, **Then** section headings remain visually coherent even if their exact line-height is theme-defined.
5. **Given** the user reloads the resume, **When** the editor opens again, **Then** the chosen line spacing is restored.

---

### User Story 4 - Smart One-Page (Priority: P1)

As a resume author, I want a smart one-page mode, so that the editor can automatically fit a resume onto one page when the content is close to fitting.

**Why this priority**: One-page resumes are common and difficult to tune manually. The feature must be predictable because it may override manual layout choices.

**Independent Test**: Toggle smart one-page on and off for resumes that already fit, nearly fit, and clearly exceed one page; verify the mode chooses safe spacing/layout changes and reports when one page is not feasible.

**Acceptance Scenarios**:

1. **Given** smart one-page is off, **When** the user turns it on, **Then** the editor marks the mode as active.
2. **Given** the resume can fit one page through safe spacing adjustments, **When** smart one-page runs, **Then** the preview becomes one page without hiding content.
3. **Given** the resume already fits one page, **When** smart one-page runs, **Then** it may choose a more readable one-page layout rather than only compressing content.
4. **Given** the resume cannot reasonably fit one page, **When** smart one-page runs, **Then** the editor keeps all content and shows that one-page fitting is not achievable.
5. **Given** the user turns smart one-page off, **When** the preview updates, **Then** the manual line spacing value that was active before smart one-page is restored.

---

### User Story 5 - PDF and Markdown Export (Priority: P1)

As a resume author, I want to export the resume as PDF or Markdown, so that I can submit a polished document or keep a portable source file.

**Why this priority**: Export is the final delivery point of the editor.

**Independent Test**: Export the same resume as PDF and Markdown under each theme and line spacing state; verify PDF matches preview and Markdown preserves source content.

**Acceptance Scenarios**:

1. **Given** a resume is open, **When** the user chooses PDF export, **Then** a valid PDF is produced using the current theme, line spacing, and smart one-page state.
2. **Given** PDF export is running, **When** generation takes more than a brief moment, **Then** the user sees progress or a clear pending state.
3. **Given** PDF export fails, **When** the failure occurs, **Then** the user sees a specific recovery message and source content remains safe.
4. **Given** the user chooses Markdown export, **When** export completes, **Then** the downloaded Markdown preserves supported source syntax.
5. **Given** the exported Markdown is imported or pasted back into the editor, **When** it renders, **Then** supported content has no meaningful loss.

## Functional Requirements

### Markdown Rendering

- **FR-001**: System MUST provide a Markdown source editor and live resume preview for the same resume.
- **FR-002**: System MUST document and support the initial Markdown syntax set: H1, H2, H3, paragraphs, bold, italic, bold-italic, strikethrough, links, inline code, blockquote, horizontal rule, unordered list, ordered list, nested list, task-list syntax rendered literally, table, external URL image, and Muji-compatible resume extensions including `::: left/right`, `icon:*`, and icon-prefixed links.
- **FR-003**: System MUST map H1 to the resume title.
- **FR-004**: System MUST map H2 to major resume sections.
- **FR-005**: System MUST map H3 to item/subsection titles inside the current major section.
- **FR-006**: System MUST render inline code as a compact tag-style element suitable for skills or keywords.
- **FR-007**: System MUST render tables as resume-friendly column layouts that remain readable in preview and PDF.
- **FR-008**: System MUST preserve unsupported Markdown syntax as source text or a predictable fallback without deleting source content.
- **FR-009**: System MUST keep Markdown source and rendered preview synchronized within one second after edits settle.

### Themes

- **FR-010**: System MUST ship exactly three v3 resume rendering themes in this scope: 默认（秋风同款）, 极简色, and 平面大气主题.
- **FR-011**: System MUST match the observed Muji rendering effects for these three themes: dark-header/centered-section-label, minimal line-based, and accent-band.
- **FR-012**: System MUST allow switching themes without mutating Markdown source content.
- **FR-013**: System MUST persist the selected theme per resume.
- **FR-014**: System MUST ensure each theme renders the same supported Markdown syntax consistently enough that no supported content disappears.

### Line Spacing

- **FR-015**: System MUST provide a visible line spacing control.
- **FR-016**: System MUST persist line spacing per resume when smart one-page is off.
- **FR-017**: System MUST apply line spacing changes to body text, lists, and tables.
- **FR-018**: System MUST keep theme-defined section heading decoration readable when line spacing changes.
- **FR-019**: System MUST expose Muji-compatible integer line spacing presets from 12 through 25.

### Smart One-Page

- **FR-020**: System MUST provide a smart one-page toggle.
- **FR-021**: System MUST indicate whether smart one-page is active.
- **FR-022**: System MUST fit content to one page only by changing layout parameters, never by hiding or deleting content.
- **FR-023**: System MUST report when one-page fitting is not feasible.
- **FR-024**: System MUST let smart one-page temporarily override manual line spacing while enabled and restore the previous manual line spacing when disabled.

### Export

- **FR-025**: System MUST export the current resume to PDF.
- **FR-026**: System MUST export the current resume to Markdown.
- **FR-027**: System MUST ensure PDF export visually matches the current live preview for supported Markdown, active theme, line spacing, smart one-page state, tables, links, and images.
- **FR-028**: System MUST preserve source Markdown in Markdown export.
- **FR-029**: System MUST show export progress, success, and failure states.

## Requirement Points Awaiting Product Confirmation

| ID | Question | Default Recommendation |
|---|---|---|
| C-001 | Should v3 support Muji-style custom resume containers and icon tokens, or use InterCraft-specific syntax? | Answered: fully replicate Muji's scoped functionality and rendering effects. |
| C-002 | Should GitHub task-list syntax render real checkboxes or remain literal text? | Answered by Muji replication goal: render task-list syntax literally, matching observed Muji behavior. |
| C-003 | Should strikethrough be part of final resume rendering? | Answered by Muji replication goal: support strikethrough, matching observed Muji behavior. |
| C-004 | What exact line spacing range should InterCraft expose? | Answered: replicate Muji's integer presets from 12 through 25. |
| C-005 | When smart one-page is enabled, should manual line spacing be disabled, overwritten, or temporarily overridden? | Answered: temporarily override while preserving and restoring the user's manual value. |
| C-006 | What are the final names of the three shipped themes? | Answered: 默认（秋风同款）, 极简色, and 平面大气主题. |
| C-007 | Should Markdown image syntax be allowed from external URLs, uploads only, or both? | Answered: support external URL images from Markdown; local upload and cropping are out of scope. |

## Edge Cases

- Multiple H1 headings in one resume.
- H2 appears before H1.
- H3 appears before any H2.
- Very long URLs or unbroken words.
- Tables with too many columns for page width.
- Nested lists deeper than two levels.
- Broken external image URLs or external images that fail during PDF export.
- Markdown image syntax that points to local files or unsupported schemes.
- Smart one-page conflicts with a manually selected large line spacing; smart mode temporarily overrides the value and restores it when disabled.
- Export requested while preview is still updating.
- Markdown contains unsupported raw HTML, unsafe links, or unsafe image URLs.

## Success Criteria

- **SC-001**: A representative Markdown resume renders with all supported syntax in preview without losing content.
- **SC-002**: The same Markdown resume can switch among all three themes with unchanged source text.
- **SC-003**: Line spacing changes visibly affect body/list/table density and persist when smart one-page is off.
- **SC-004**: Smart one-page can fit a near-one-page resume without hiding content and clearly reports infeasible cases.
- **SC-005**: PDF export matches preview for the active theme and settings within a documented visual tolerance.
- **SC-006**: Markdown export preserves the source syntax for all supported features.

## Assumptions

- v3 is a scoped v2 feature, not a continuation of broad v1/v2 resume feature work.
- Existing v1 requirements remain historical unless this spec explicitly reintroduces a requirement.
- User-facing copy must not expose internal labels like "v3" unless in admin/developer documentation.
- PDF export fidelity is a release gate for this feature.
