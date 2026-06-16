# Feature Specification: Personal Ability Profile

**Feature Branch**: `006-personal-ability-profile`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "帮我规划一下个人能力画像模块需求"

## Clarifications

### Session 2026-06-15

- Q: 管理员权限范围 → A: 管理员只读查看用户能力画像
- Q: 数据导出方式 → A: 仅支持 PDF 报告导出，不与简历编辑器集成
- Q: 多次面试评分的聚合逻辑 → A: 按时间衰减的加权平均（越近的面试权重越高）

## User Scenarios & Testing

### User Story 1 - View Personal Ability Profile Dashboard (Priority: P1)

As a user, I want to see my ability profile as a visual dashboard so that I can understand my skill strengths and gaps at a glance.

The dashboard displays each ability (e.g., "系统设计", "算法", "项目领导力") as a dimension on a radar/spider chart, with my self-assessed level and system-assessed level plotted side by side. Below the chart, a list view shows each ability with its current level, trend direction, and latest assessment date.

**Why this priority**: This is the core value of the module — without the dashboard there is no profile to speak of. All other features (self-assessment, sharing) augment this primary view.

**Independent Test**: Can be tested by navigating to the ability profile page and verifying that the radar chart renders with at least the abilities imported from the system's existing ability taxonomy, and that the view loads within acceptable time.

**Acceptance Scenarios**:

1. **Given** the user has no abilities recorded yet, **When** they navigate to the ability profile page, **Then** they see an empty state with a prompt to self-assess or complete an interview to generate abilities.
2. **Given** the user has self-assessed abilities and completed interviews, **When** they view the profile, **Then** the radar chart shows both self-assessed and system-assessed levels for each ability, with a legend distinguishing the two sources.
3. **Given** the user is viewing the ability list, **When** they click on a specific ability, **Then** they see detail view including assessment history, trend over time, and related interview performance.

---

### User Story 2 - Self-Assess Abilities (Priority: P1)

As a user, I want to rate my own proficiency on each ability so that I can build my profile even before completing interviews.

The user selects an ability from the system's predefined taxonomy and assigns a proficiency level (1–5 scale). They can optionally add notes or evidence (e.g., "3 years of backend development experience"). Self-assessments can be updated at any time, with the system retaining version history.

**Why this priority**: Self-assessment bootstraps the profile for new users who may not have interview data yet, making the module immediately useful.

**Independent Test**: Can be tested by selecting an ability, assigning a level, and verifying the profile dashboard updates to reflect the new self-assessment.

**Acceptance Scenarios**:

1. **Given** the user is editing their ability profile, **When** they select an ability from the taxonomy and set a proficiency level of 4, **Then** the system saves the assessment and immediately reflects it on the dashboard.
2. **Given** the user has an existing self-assessment, **When** they update it from level 3 to level 4, **Then** the system retains the previous assessment as a historical version and shows the updated level on the dashboard.
3. **Given** the user attempts to set a proficiency level, **When** they enter a value outside the 1–5 range, **Then** the system rejects the input and shows an inline validation message.

---

### User Story 3 - View System-Assessed Abilities from Interviews (Priority: P2)

As a user, I want to see abilities that the system has assessed based on my interview performance, so that I can compare my self-perception with objective evaluation.

After each interview session, the system evaluates the user's performance across relevant abilities (e.g., "算法: 3.5/5", "系统设计: 4/5"). These scores appear on the profile dashboard alongside self-assessments. The system assessment is read-only from the user's perspective.

**Why this priority**: This differentiates the profile from a simple self-report — it combines user input with system-generated evaluation, increasing credibility.

**Independent Test**: Can be tested by completing an interview that covers specific abilities, then verifying the profile dashboard displays the new system-assessed scores.

**Acceptance Scenarios**:

1. **Given** the user completes an interview session, **When** the interview is scored, **Then** each ability evaluated in that interview appears (or updates) on the profile with the system-assessed level.
2. **Given** the system has assessed a user on "算法" with score 3.5 in interview A and 4.0 in interview B (where B is more recent), **When** the user views the ability detail, **Then** they see both scores listed chronologically, and the radar chart shows the time-weighted average (more recent interviews weighted higher).
3. **Given** a user has never completed any interview, **When** they view the dashboard, **Then** only self-assessed abilities appear, with system-assessed sections showing an empty or "pending" state.

---

### User Story 4 - Share Ability Profile (Priority: P3)

As a user, I want to share my ability profile with potential employers or recruiters via a read-only link so that I can demonstrate my capabilities without sending a separate document.

The user generates a shareable link from their profile page. The link opens a public read-only view showing the radar chart and ability list. The link can be optionally set to expire after a configurable period or be revoked at any time.

**Why this priority**: Profile sharing extends the value of the module from personal insight to career enablement, but depends on P1 and P2 being in place.

**Independent Test**: Can be tested by generating a share link, opening it in an incognito browser, and verifying the profile is displayed in read-only mode without edit controls.

**Acceptance Scenarios**:

1. **Given** the user has a populated ability profile, **When** they click "Generate Share Link", **Then** the system creates a unique URL and displays it with copy-to-clipboard option.
2. **Given** a share link is active, **When** a non-authenticated user opens the link, **Then** they see the full profile in read-only mode with no edit or assessment actions available.
3. **Given** a user has revoked a share link, **When** someone opens the revoked link, **Then** they see a "profile not found or access revoked" message.

---

### User Story 5 - Track Ability Growth Over Time (Priority: P3)

As a user, I want to see how my abilities have changed over time so that I can track my learning progress and identify which areas have improved.

The ability detail view includes a timeline chart showing level changes for both self-assessments and system assessments across all historical versions. The dashboard summary shows a "trend" indicator (up, down, stable) for each ability.

**Why this priority**: Growth tracking increases user engagement and provides long-term value, but depends on sufficient assessment history (multiple data points) to be meaningful.

**Independent Test**: Can be tested by reviewing an ability that has been assessed at multiple points in time and verifying the timeline renders correctly with trend indicators.

**Acceptance Scenarios**:

1. **Given** an ability has 3+ historical assessment points, **When** the user views its detail, **Then** a timeline chart plots all data points with source labels (self vs system).
2. **Given** an ability's latest assessment is higher than its previous, **When** the user views the dashboard, **Then** the ability card shows a "upward" trend indicator.
3. **Given** an ability has only one assessment point, **When** the user views the detail, **Then** the timeline shows a single data point with a "needs more data" message instead of a trend line.

---

### User Story 6 - Export Ability Profile as PDF (Priority: P3)

As a user, I want to export my ability profile as a PDF report so that I can print it, attach it to job applications, or keep an offline copy.

The PDF includes the radar chart, a table of all abilities with levels and sources, and the profile owner's name and date. The export button is available on the profile dashboard. PDF generation happens server-side and is downloaded directly.

**Why this priority**: PDF export complements the share link feature for offline use cases. Lower than sharing because share links cover most viewing needs with less friction.

**Independent Test**: Can be tested by clicking "Export PDF" and verifying the downloaded file contains the expected chart, ability list, and user information.

**Acceptance Scenarios**:

1. **Given** the user has a populated profile with 5+ abilities, **When** they click "Export PDF", **Then** the system generates a PDF containing the radar chart, ability list with scores, and generation timestamp.
2. **Given** the user's profile is empty, **When** they click "Export PDF", **Then** the system shows a "no data to export" message instead of generating an empty PDF.
3. **Given** a PDF export is in progress, **When** the user navigates away, **Then** the export continues and the download completes (background generation).

---

### User Story 7 - Admin Views User Ability Profile (Priority: P3)

As an admin or interviewer, I want to view a candidate's ability profile so that I can understand their strengths and weaknesses before or after an interview.

The admin can navigate to any user's ability profile from the user management interface. The view is read-only — no self-assessment editing, no share link management. System scores and self-assessments are both visible, with an indicator showing which user the profile belongs to.

**Why this priority**: Enables interviewers to prepare for sessions with prior knowledge of the candidate's capability profile. Lower priority because the initial focus is on the individual user's self-service experience.

**Independent Test**: Can be tested by an admin navigating to another user's profile page and verifying all ability data displays in read-only mode without edit controls.

**Acceptance Scenarios**:

1. **Given** an admin is viewing a candidate's profile, **When** the candidate has self-assessed abilities, **Then** the admin sees both self-assessments and system scores identically to what the candidate sees.
2. **Given** an admin is viewing a candidate's profile, **When** they attempt to edit or delete an assessment, **Then** the UI does not expose any edit controls.
3. **Given** a non-admin user attempts to view another user's profile via URL manipulation, **Then** the system returns a 403 or redirects to their own profile.

### Edge Cases

- What happens when the system's ability taxonomy is updated (e.g., a new ability category is added or deprecated)? Deprecated abilities remain visible in the user's history but are marked as "legacy" and cannot be selected for new self-assessments.
- How does the system handle a user with 50+ assessed abilities? The dashboard paginates or groups abilities by category (e.g., "technical", "leadership", "communication").
- What happens if an interview evaluates an ability that the user has not self-assessed? The ability appears on the dashboard with system score only, with a prompt to add self-assessment.
- How does the system handle profile data when a user deletes their account? All ability profile data is deleted in accordance with the account deletion policy.
- What happens when an admin tries to access a deleted user's profile? The admin sees a "user not found" message, consistent with the user management system's behavior for deleted accounts.

## Requirements

### Functional Requirements

- **FR-001**: System MUST display a visual radar/spider chart of all assessed abilities, with self-assessment and system-assessment plotted separately.
- **FR-002**: System MUST provide an empty-state view when no abilities have been assessed yet, with clear next-step guidance.
- **FR-003**: Users MUST be able to self-assess their proficiency on any ability from the system's ability taxonomy.
- **FR-004**: Self-assessment scale MUST be 1–5 (inclusive integer), where 1 = "beginner" and 5 = "expert", with each level having a defined description.
- **FR-005**: System MUST retain version history for all self-assessment changes.
- **FR-006**: System MUST automatically populate system-assessed ability scores from completed interview sessions.
- **FR-007**: System-assessed scores MUST be read-only from the user's perspective and clearly labeled as system-evaluated.
- **FR-008**: Users MUST be able to generate a unique shareable link for their profile with optional expiration.
- **FR-009**: Share links MUST serve a read-only view without edit or assessment capabilities.
- **FR-010**: Users MUST be able to revoke share links at any time.
- **FR-011**: System MUST display a trend indicator (up/down/stable) for each ability based on historical data.
- **FR-012**: System MUST support at least the ability categories defined in the project's existing ability taxonomy (Phase 2).
- **FR-013**: System MUST allow users to add free-text notes or evidence when self-assessing an ability.
- **FR-014**: Deprecated abilities MUST remain visible in user history but marked as "legacy", and excluded from new self-assessment selection.
- **FR-015**: System MUST group/paginate abilities when the user has more than 20 assessed abilities to maintain readability.
- **FR-016**: System MUST support admin read-only access to any user's ability profile.
- **FR-017**: Admin view MUST NOT expose edit, delete, or share management controls — read-only only.
- **FR-018**: System MUST allow users to export their ability profile as a PDF file containing a radar chart, ability list with scores, generation timestamp, and user identifier.

### Key Entities

- **Ability Profile**: A user's collection of ability assessments, both self-assessed and system-assessed. One profile per user. Contains references to Assessment records.
- **Ability (Skill Category)**: A distinct capability area from the system's taxonomy (e.g., "算法", "系统设计"). Defines the dimensions available for assessment.
- **Assessment**: A single evaluation of a user's proficiency on a specific ability. Has a source (self or system), a level (1–5 scale), optional notes/evidence, and a timestamp. Self-assessments can be updated (with version history); system assessments are append-only.
- **Profile Snapshot**: A point-in-time capture of the profile used for generating share links. Tied to an expiry policy. Can be revoked by the user.
- **Ability Trend**: Computed value showing direction of change (up/down/stable) based on chronological assessment data for a given ability and user.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can view their complete ability dashboard (chart + list) within 3 seconds from navigation, even with 20+ assessed abilities.
- **SC-002**: Self-assessment completion rate > 80% among users who visit the ability profile page (measured as users who assess at least 3 abilities).
- **SC-003**: 90% of users who complete at least one interview session have their ability profile auto-populated with system assessments.
- **SC-004**: Share link generation completes in under 2 seconds, and shared views load within 3 seconds for non-authenticated viewers.
- **SC-005**: At least 60% of users who visit the profile return within 30 days (indicating continued engagement with growth tracking).
- **SC-006**: Profile sharing is used by at least 20% of active users within 3 months of launch.

## Assumptions

- The system's ability taxonomy (from Phase 2) exists and provides the set of abilities users can assess against. This module does not define a new taxonomy but integrates with the existing one.
- Users are authenticated before accessing their own profile. The profile is private by default.
- Interview sessions (Phase 4) produce per-ability scores as part of their evaluation output.
- The 1–5 scale is sufficient for v1; fractional system scores (e.g., 3.5) are allowed from system assessment but self-assessment is integer-only.
- Share links are UUID-based and unguessable; no additional authentication is required for the shared view beyond possession of the link.
- Mobile-responsive layout is expected but a dedicated mobile app is out of scope for v1.
- The module integrates with the existing notification system for alerts (e.g., "new system assessment available").
- Multiple system assessments for the same ability are aggregated using time-weighted averaging, where more recent interviews carry higher weight. The exact decay function (e.g., linear or exponential) is defined during implementation.
