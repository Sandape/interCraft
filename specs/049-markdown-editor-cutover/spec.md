# Feature Specification: Markdown Editor Cutover and Pagination (REQ-049)

**Feature Branch**: `[049-markdown-editor-cutover]`

**Created**: 2026-07-07

**Status**: Done

**Input**: User description: "REQ-049: 1) thoroughly retire the old resume editor and fully move to the REQ-047 Markdown rendering route; 2) optimize the Markdown resume editor because a) `::: left` and `::: right` rendering is not polished enough and many icons are positioned incorrectly; b) long content does not paginate."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Markdown-Only Resume Editing (Priority: P1)

Resume authors use one clear editor for all resume work: the Markdown-first editor introduced by REQ-047. They no longer encounter the old structured/form editor, old resume-editing panels, or old visual controls that can conflict with Markdown rendering.

**Why this priority**: This is the product direction decision for v2 resume editing. The rest of REQ-049 assumes Markdown is the only editing model.

**Independent Test**: Open every user-facing resume creation and editing entry point, including existing resume entries, empty-state create actions, duplicate/open flows, and direct editor links. Each path must land on the Markdown editor and must not expose the legacy structured editor.

**Acceptance Scenarios**:

1. **Given** a user creates a new resume, **When** the editor opens, **Then** the user sees the Markdown source editor, Markdown preview, REQ-047 theme controls, line spacing, smart one-page, and export controls only.
2. **Given** a user opens an existing resume that already has Markdown source, **When** the editor loads, **Then** the Markdown source and current render settings are restored.
3. **Given** a user opens an older resume that has content but no Markdown source, **When** the editor loads, **Then** the user can continue editing through a Markdown document that preserves the visible resume text instead of returning to the legacy editor.
4. **Given** a user tries to reach the old editor through an old bookmark or stale in-app link, **When** the destination resolves, **Then** the user is redirected or guided to the Markdown editor without data loss.
5. **Given** the Markdown editor is open, **When** the user scans the page, **Then** no old structured-section editing surface, old template gallery, old dock, or old JSON-template controls are visible as editing options.

---

### User Story 2 - Polished `left/right` Contact Rendering (Priority: P1)

Resume authors can use Muji-compatible `::: left` and `::: right` contact blocks with icons, links, and short labels, and the rendered resume looks aligned and professional across the three REQ-047 themes.

**Why this priority**: Contact blocks appear near the top of most resumes. Misaligned icons make the entire editor feel unreliable even when the Markdown source is correct.

**Independent Test**: Render a format-lab resume that contains `::: left`, `::: right`, plain icon rows, icon-prefixed links, email/phone/location icons, multi-line wrapping, and empty optional rows. Verify visual alignment in all three themes and in PDF export.

**Acceptance Scenarios**:

1. **Given** a `::: left` block contains multiple `icon:*` rows, **When** the preview renders, **Then** each icon aligns with the first line of its associated text and does not float above, below, or away from the label.
2. **Given** a `::: right` block contains icon-prefixed links, **When** the preview renders, **Then** the icon, clickable text, and link wrapping remain in one coherent row or wrapped row group.
3. **Given** both left and right contact blocks are present, **When** the preview renders, **Then** the two columns align as a balanced header/contact area and remain readable at common resume widths.
4. **Given** contact text wraps to a second line, **When** the preview renders, **Then** the wrapped line aligns with the text column instead of starting underneath the icon.
5. **Given** contact blocks render under each of the three REQ-047 themes, **When** the user switches themes, **Then** icon size, color, baseline, and spacing remain visually consistent with that theme.
6. **Given** the user exports PDF, **When** the contact block appears in the exported document, **Then** icon alignment matches the live preview.

---

### User Story 3 - Multi-Page Markdown Resume Rendering (Priority: P1)

Resume authors can write resumes longer than one page and see a paginated preview instead of one overflowing page. The exported PDF contains every page shown in the preview.

**Why this priority**: Without pagination, long resumes hide content, overflow the page, or make PDF export unreliable.

**Independent Test**: Paste a long Markdown resume with headings, contact blocks, paragraphs, nested lists, tables, and repeated experience sections. Verify that the preview creates multiple pages, preserves all content, and exports the same page count.

**Acceptance Scenarios**:

1. **Given** Markdown content exceeds one page, **When** the preview renders, **Then** the content continues onto page 2 and additional pages as needed.
2. **Given** content is paginated, **When** the user scrolls the preview, **Then** clear page boundaries are visible and page order is obvious.
3. **Given** a section heading is close to the bottom of a page, **When** pagination runs, **Then** the heading is not stranded without its first related content line unless there is no better page break.
4. **Given** a table spans more vertical space than remains on the current page, **When** pagination runs, **Then** the table remains readable and no rows are hidden.
5. **Given** smart one-page is enabled but content cannot safely fit one page, **When** pagination runs, **Then** the editor reports that one-page fit is infeasible and still shows all pages.
6. **Given** the user exports PDF, **When** export completes, **Then** the PDF includes every preview page in the same order.

---

### User Story 4 - Safe Retirement of Legacy Resume Data (Priority: P2)

Users with older resumes keep access to their resume content while the product removes old editing surfaces.

**Why this priority**: The cutover must be decisive, but it must not create user-visible data loss or trap older resumes in an inaccessible format.

**Independent Test**: Open representative older resumes with non-empty basics, summary, experience, education, projects, skills, and custom sections. Verify that all user-visible text appears in the Markdown editor or in a clear migration fallback path.

**Acceptance Scenarios**:

1. **Given** an older resume contains structured content, **When** the user opens it after the cutover, **Then** all non-empty user-visible text is available in Markdown editing or a clearly labelled conversion preview.
2. **Given** conversion cannot preserve a field perfectly, **When** the editor opens, **Then** the user sees a clear warning and the original content remains recoverable.
3. **Given** a resume has already been converted to Markdown, **When** the user opens it again, **Then** the editor does not repeat conversion or duplicate content.

### Edge Cases

- An old resume contains no Markdown source and only partially filled structured fields.
- An old resume contains custom sections whose labels do not map cleanly to standard Markdown headings.
- A user opens an old bookmarked editor URL after the legacy editor has been removed.
- A `::: left/right` block contains unknown icon names.
- A contact row contains a very long email, URL, or unbroken identifier.
- A contact block contains a mixture of plain text rows and icon-prefixed links.
- Markdown content creates more than two pages.
- A page break falls near a heading, table, list, or contact container.
- Smart one-page conflicts with multi-page content.
- PDF export is requested while pagination is recalculating.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST make the Markdown editor the only user-facing resume editing experience.
- **FR-002**: The system MUST remove or disable all user-facing entry points to the legacy structured resume editor.
- **FR-003**: The system MUST ensure stale links or bookmarks to legacy resume editing guide users to the Markdown editor without data loss.
- **FR-004**: The system MUST preserve existing Markdown resume source and render settings when opening a resume.
- **FR-005**: The system MUST provide a safe path for older resumes without Markdown source so users can continue editing visible resume content through the Markdown route.
- **FR-006**: The system MUST make the cutover visible in product behavior without exposing internal labels such as "REQ-047" or "v3" to normal users.
- **FR-007**: The system MUST not allow old structured-section editing controls, old template controls, or old resume-editing dock actions to appear as active editing controls after cutover.
- **FR-008**: The system MUST keep PDF and Markdown export available after the legacy editor is retired.
- **FR-009**: The system MUST keep the three REQ-047 themes, line spacing control, and smart one-page control available in the Markdown editor after cutover.
- **FR-010**: The system MUST render `::: left` and `::: right` contact blocks as aligned resume contact/header regions.
- **FR-011**: The system MUST align each icon with its associated text label or link in contact rows.
- **FR-012**: The system MUST keep wrapped contact text aligned with the text column rather than underneath the icon.
- **FR-013**: The system MUST render icon-prefixed links as a single coherent link row or wrapped row group.
- **FR-014**: The system MUST handle unknown icon names with a predictable fallback that does not break contact-row alignment.
- **FR-015**: The system MUST preserve contact block readability across all three REQ-047 themes.
- **FR-016**: The system MUST ensure PDF export matches live preview alignment for `::: left/right` contact blocks.
- **FR-017**: The system MUST paginate Markdown resumes when rendered content exceeds one page.
- **FR-018**: The system MUST show clear page boundaries in the preview for multi-page resumes.
- **FR-019**: The system MUST preserve all rendered content across page breaks; content must not be clipped or hidden because it overflows a page.
- **FR-020**: The system MUST avoid stranding section headings at the bottom of a page when related content can reasonably move with the heading.
- **FR-021**: The system MUST keep tables, lists, contact blocks, and headings readable when they appear near page boundaries.
- **FR-022**: The system MUST ensure PDF export includes every preview page in the same order.
- **FR-023**: The system MUST ensure smart one-page falls back to multi-page rendering when one-page fit is infeasible.
- **FR-024**: The system MUST keep pagination behavior consistent when users switch themes or line spacing.
- **FR-025**: The system MUST expose enough user-visible feedback for pagination, smart one-page, and export states that users can tell whether all content is included.

### Key Entities *(include if feature involves data)*

- **Markdown Resume Document**: The editable source text and render settings used by the Markdown editor.
- **Legacy Resume Content**: Older resume content created before the Markdown-only cutover; must remain accessible through a safe Markdown route.
- **Contact Container**: A rendered `::: left` or `::: right` block containing text rows, icons, and links.
- **Paginated Resume Preview**: The ordered set of rendered pages shown in the editor and used as the export reference.
- **Page Break Decision**: A user-visible split point between preview pages, with special care for headings, tables, lists, and contact blocks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of resume creation and editing entry points tested in acceptance open the Markdown editor and no active legacy editing controls are visible.
- **SC-002**: 100% of representative older resumes in the migration test set open without losing non-empty user-visible text.
- **SC-003**: In the contact-block visual test set, icon-to-text vertical alignment differs by no more than 3 screenshot pixels per row in all three themes and in PDF export.
- **SC-004**: A long Markdown resume test fixture containing at least 3 pages of content renders all content across pages with no clipped text.
- **SC-005**: PDF export page count matches preview page count for the multi-page acceptance fixture.
- **SC-006**: Smart one-page reports infeasible for long multi-page fixtures and still displays all pages.
- **SC-007**: Users can complete the primary edit-preview-export workflow after the cutover without encountering a legacy editor screen.

## Assumptions

- REQ-047 is the accepted Markdown-first foundation for InterCraft v2 resume editing.
- The old editor refers to the legacy structured/form resume editing experience and its associated visual controls, not to the resume list or general resume center navigation.
- Existing public or historical resume viewing can remain available if it does not expose legacy editing controls.
- Older resumes should be preserved through best-effort Markdown conversion or a clear recovery path; silent deletion of existing content is out of scope.
- This feature does not add new themes or new Markdown syntax beyond the contact-block and pagination improvements described here.
- This feature does not add AI rewriting, template marketplace, local image upload, or resume sharing.
