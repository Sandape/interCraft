# Feature Specification: InterCraft Management Console Redesign

**Feature Branch**: `[044-admin-console-redesign]`

**Created**: 2026-07-03

**Status**: Draft

**Input**: User description: "调研一下行业内的管理后台通常都有哪些设计，为 interCraft 的管理后台整理一份 spec。后台面向产品、运营、维护开发者，需要数据大屏、日志中心等基础能力。之前的管理后台不行，把以前的需求标记为失效，重新进行设计。"

## Supersession

REQ-044 supersedes `specs/035-admin-dashboard-mvp` and `specs/039-log-center-full`.
Those earlier admin-console and log-center requirements are no longer
implementation sources. They remain historical evidence only.

REQ-033 remains valid as a telemetry and PM-dashboard baseline where its metric
definitions are useful, but it does not define the new management-console
information architecture or user experience.

## Research Basis And Design Positioning

Industry references suggest four stable patterns:

- Product analytics tools organize work around recurring product questions:
  dashboards, funnels, cohorts, retention, feature adoption, experiments, and
  trusted metric definitions.
- Observability tools are useful when logs, metrics, traces, incidents, and
  releases can be correlated from one investigation path.
- Error triage tools group issues by impact, affected users, release context,
  first/last seen time, status, owners, comments, and regression state.
- Internal admin platforms emphasize least-privilege roles, audit logs, scoped
  exports, sensitive-action review, and retention controls.

InterCraft should therefore treat the management console as an operational
intelligence product, not as a generic chart gallery or developer log viewer.
The first screen should help a PM decide what changed, what matters, and what
action to take. Developer debugging should be one drilldown path behind business
or quality signals, not the center of gravity.

## Product Thesis

The management console is the internal operating system for InterCraft. It
answers three questions:

1. What is happening in the product and user journey?
2. Why is it happening across AI quality, cost, reliability, and workflow state?
3. What should the team review, fix, tune, or monitor next?

The PM is the primary audience. Operations and maintainer developers are
secondary audiences who need enough detail to investigate and act without
turning the PM console into a raw observability tool.

## Scope Boundaries

### In Scope

- A redesigned management-console information architecture with role-aware
  workspaces for PM, operations, and maintainer developers.
- A product-led command center that highlights product health, funnel movement,
  retention, feature adoption, AI quality, AI cost, system health, incidents,
  and data freshness.
- A question-first product analytics workspace covering funnels, cohorts,
  retention, feature adoption, user journey paths, experiments or release
  comparisons, and metric definitions.
- An AI operations and quality workspace covering AI task volume, success,
  failure, latency, token/cost estimates, model/prompt/rubric/version context,
  eval results, badcases, and user-facing quality outcomes.
- A logs and trace workspace that starts from a business event, user/account,
  badcase, incident, agent run, or trace id and correlates logs, traces, node
  execution, LLM calls, tool calls, and release context.
- An incident and review workflow for product anomalies, AI quality issues,
  system incidents, and privacy/audit review items.
- Privacy-safe user and account lookup for support and operations, with
  sensitive content hidden by default.
- Metric trust controls: definitions, owner, source, freshness, completeness,
  quality flags, and confidence labels.
- Internal reports and review snapshots that preserve selected filters, metric
  definitions, freshness warnings, annotations, and privacy-safe evidence.
- Role-based access, audit logs, sensitive-action reason capture, export
  controls, and retention policy requirements.

### Out Of Scope

- Reusing the previous 035 admin-dashboard information architecture as the
  target UX.
- Reusing the previous 039 log-center-first layout as the target UX.
- Building a general-purpose BI editor, SQL workbench, or arbitrary chart
  builder in the first release.
- Building a full replacement for Datadog, Grafana, Elastic, Sentry, Mixpanel,
  Amplitude, PostHog, or Retool.
- Self-service role administration, billing administration, prompt/rubric
  editing, model-provider credential editing, or destructive user-data mutation
  in the first release.
- Unrestricted browsing or export of raw resumes, job descriptions, interview
  answers, raw prompts, raw model outputs, secrets, or free-form sensitive text.
- Public customer-facing reporting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PM Opens A Decision Command Center (Priority: P1)

As a PM, I want the first screen to show the most important product, AI-quality,
cost, and system-health changes, so that I can decide what needs attention
without opening several disconnected dashboards.

**Why this priority**: The console exists primarily to improve product operation
and system tuning decisions. If the landing view is just a chart wall or a log
list, the PM still depends on developers for interpretation.

**Independent Test**: Seed a day of product, AI, incident, and data-freshness
signals, open the console as a PM, and verify the landing view presents a
prioritized decision queue with supporting metrics and links to drilldowns.

**Acceptance Scenarios**:

1. **Given** current and comparison-period data exist, **When** a PM opens the
   console, **Then** the landing view shows product health, funnel movement,
   AI quality, AI cost, system health, incidents, and data freshness in a
   prioritized order.
2. **Given** a metric changed significantly, **When** the PM reads the signal,
   **Then** the console states what changed, the affected segment, the
   comparison baseline, the confidence level, and the recommended next review.
3. **Given** a signal is based on incomplete or stale data, **When** it appears
   in the command center, **Then** it is clearly marked as incomplete or stale
   and is not presented as a confirmed product fact.
4. **Given** no significant changes are detected, **When** the PM opens the
   console, **Then** the console shows a quiet steady-state view with freshness
   and recent review history instead of manufacturing alerts.

---

### User Story 2 - PM Investigates Funnel, Retention, And Feature Adoption (Priority: P1)

As a PM, I want a product analytics workspace organized by questions, segments,
and user journey stages, so that I can understand where users activate, drop
off, return, and adopt important features.

**Why this priority**: Product and operations decisions require behavioral
context, not just aggregate usage counts.

**Independent Test**: Seed product events across resume, interview, error-book,
and feedback flows, then verify a PM can answer funnel drop-off, retention,
cohort, and feature-adoption questions without developer tools.

**Acceptance Scenarios**:

1. **Given** product events exist for a selected period, **When** the PM opens
   the product analytics workspace, **Then** the workspace offers approved
   questions for activation, funnel drop-off, retention, feature adoption, and
   user journey paths.
2. **Given** the PM selects a funnel, **When** each step has event data, **Then**
   the console shows counts, step conversion, entry conversion, drop-off,
   time-to-convert where available, and comparison-period movement.
3. **Given** cohorts or segments are available, **When** the PM applies a
   segment, **Then** all relevant charts and tables use the same segment
   definition and show the cohort population and last computation time.
4. **Given** a feature has low adoption but high downstream success among users
   who discover it, **When** the PM reviews feature adoption, **Then** the
   console separates discovery, usage frequency, repeat usage, and downstream
   outcome instead of collapsing them into one score.

---

### User Story 3 - PM Reviews AI Quality, Cost, And Release Impact (Priority: P1)

As a PM, I want to see AI task quality, reliability, cost, and version impact in
one workspace, so that product tuning decisions can account for both user value
and operating cost.

**Why this priority**: InterCraft is AI-heavy. PM decisions need to connect
resume/interview outcomes with prompts, models, evals, failures, and cost.

**Independent Test**: Seed AI task records, eval results, badcases, prompt/model
versions, and cost estimates, then verify the workspace shows quality and cost
tradeoffs by feature area and version.

**Acceptance Scenarios**:

1. **Given** AI tasks ran in the selected period, **When** the PM opens AI
   operations, **Then** the console shows task volume, success rate, failure
   categories, user-visible outcome metrics, latency bands, token usage, and
   estimated cost.
2. **Given** a prompt, model, rubric, or release version changed, **When** the
   PM filters by version, **Then** the console shows quality, cost, latency,
   error, and user-outcome deltas against the comparison baseline.
3. **Given** eval runs and badcases are linked to product behavior, **When** the
   PM opens a quality issue, **Then** the console shows eval verdicts, affected
   feature area, affected user journey step, owner, status, and recommended
   review action.
4. **Given** cost increases while quality does not improve, **When** the PM
   reviews AI operations, **Then** the console flags the tradeoff and links to
   the relevant model, prompt, feature area, and affected cohort.

---

### User Story 4 - Operations Triage Incidents From Business Impact (Priority: P1)

As an operations user, I want incidents and anomalies to be grouped by business
impact, severity, owner, status, and affected journeys, so that response work
starts from user impact rather than raw error volume.

**Why this priority**: Operations needs fast triage and escalation without
forcing every issue through developer-only trace tools.

**Independent Test**: Seed product anomalies, AI failures, and system incidents,
then verify operations can filter, assign, update status, and inspect impact
without exposing sensitive payloads.

**Acceptance Scenarios**:

1. **Given** multiple anomalies exist, **When** operations opens the incident
   workspace, **Then** incidents are grouped by severity, status, affected
   feature area, affected user journey, owner, first seen, last seen, and trend.
2. **Given** an incident affects a funnel step, **When** operations opens it,
   **Then** the console shows affected counts, affected cohorts, related AI
   tasks, related releases, related logs/traces, and recent comments.
3. **Given** an incident is assigned or resolved, **When** status changes, **Then**
   the console records actor, timestamp, reason, status, owner, and linked
   evidence.
4. **Given** an anomaly is low confidence, **When** it appears in the queue,
   **Then** the console labels it as a candidate and separates it from confirmed
   incidents.

---

### User Story 5 - Maintainer Developer Drills From Signal To Root Cause (Priority: P2)

As a maintainer developer, I want to start from a product signal, incident,
badcase, user/account, or trace id and drill into correlated logs and traces, so
that I can locate root cause without manually stitching systems together.

**Why this priority**: The console should still make debugging efficient, but
debugging is a drilldown from product or quality context rather than the
primary UX.

**Independent Test**: Seed a failed agent task linked to a user journey, logs,
trace spans, node execution, LLM call, tool call, eval case, and incident, then
verify the developer can move from signal to root cause through linked views.

**Acceptance Scenarios**:

1. **Given** a developer opens a signal with linked technical evidence, **When**
   they drill down, **Then** the console shows correlated logs, traces, spans,
   agent runs, node executions, tool calls, LLM calls, eval results, badcases,
   release context, and privacy status.
2. **Given** a log record is opened, **When** structured fields are available,
   **Then** the developer can filter for field value, filter out field value,
   add the field to the table, and open related traces or incidents.
3. **Given** an LLM or node payload contains sensitive text, **When** the
   developer lacks approved visibility, **Then** the console shows metadata,
   redacted summaries, field shape, and error category without raw content.
4. **Given** a developer has approved debug visibility, **When** they reveal a
   masked raw view, **Then** the console requires a reason and records an audit
   event before showing the masked content.

---

### User Story 6 - Govern Access, Audit, And Export (Priority: P1)

As the system owner, I want role-based access, audit logs, export controls, and
retention rules to be visible and enforceable, so that the console can be used
internally without leaking sensitive career data.

**Why this priority**: Internal tools are powerful. Without governance, the
console becomes a privacy and operational risk.

**Independent Test**: Test PM, operations, maintainer developer, reviewer, and
unauthorized users against the same seeded data and verify permissions, audit
events, export restrictions, and retention behavior.

**Acceptance Scenarios**:

1. **Given** different internal roles exist, **When** each role opens the
   console, **Then** the visible workspaces, fields, actions, and export options
   match the least-privilege policy for that role.
2. **Given** a sensitive action is performed, **When** it completes or fails,
   **Then** the console records actor, time, target, action, reason where
   required, result, and visibility mode.
3. **Given** an export is generated, **When** the export contains dashboard,
   incident, log, or trace evidence, **Then** it includes only approved fields,
   selected filters, freshness state, redaction state, and audit metadata.
4. **Given** data exceeds its retention window, **When** a user attempts to view
   it, **Then** the console shows that the data is unavailable due to retention
   and does not serve stale cached sensitive content.

---

### User Story 7 - PM Shares A Review Snapshot (Priority: P3)

As a PM, I want to generate a review snapshot with metrics, commentary, and
evidence links, so that weekly product and quality reviews use the same trusted
source of truth.

**Why this priority**: Reporting is important, but it should follow the core
decision and investigation workflows.

**Independent Test**: Select a period and segment, add annotations, generate a
snapshot, and verify the report matches visible data and preserves warnings and
privacy constraints.

**Acceptance Scenarios**:

1. **Given** a PM has selected a period, segment, and workspace, **When** they
   generate a snapshot, **Then** the snapshot includes selected filters, metric
   definitions, values, comparison deltas, freshness, quality flags, and
   annotations.
2. **Given** a snapshot references incidents or logs, **When** it is generated,
   **Then** the snapshot links to evidence without embedding raw sensitive
   payloads.
3. **Given** a metric later changes due to late-arriving data, **When** the
   snapshot is viewed, **Then** the console distinguishes frozen snapshot values
   from current live values.

### Edge Cases

- A metric is zero because no users performed the event, not because telemetry
  is missing.
- A dashboard section is fresh while another section is stale.
- A comparison period includes incomplete conversion windows.
- A cohort definition changes after a report snapshot was created.
- A release, prompt, or model version is missing from older records.
- Multiple incidents share one technical root cause but affect different user
  journeys.
- One product anomaly is caused by delayed ingestion rather than product
  behavior.
- Logs or traces exist without product event correlation.
- Product events exist without trace coverage because a legacy path bypassed
  centralized instrumentation.
- A sensitive reveal request is denied after the user has already opened the
  surrounding trace.
- An export is requested for a period containing expired sensitive payloads.
- A PM needs product impact but not developer-only payloads for the same issue.

## Requirements *(mandatory)*

### Functional Requirements

**Information Architecture And Roles**

- **FR-001**: System MUST define the new management console as the sole active
  admin-console requirement source and mark previous 035 and 039 admin/log
  requirements as superseded.
- **FR-002**: System MUST provide role-aware workspaces for PM, operations,
  maintainer developer, reviewer, and system owner users.
- **FR-003**: System MUST make the PM decision command center the default
  landing view for authorized PM and owner users.
- **FR-004**: System MUST keep developer log and trace views reachable through
  drilldowns and navigation, but MUST NOT make raw logs the default experience
  for PM users.
- **FR-005**: System MUST provide stable top-level workspaces for Command
  Center, Product Analytics, AI Operations, Incidents & Badcases, Logs &
  Traces, Users & Accounts, Reports, and Governance.
- **FR-006**: System MUST support saved views for recurring internal review
  questions, including selected filters, owner, description, and trust status.

**Command Center**

- **FR-007**: System MUST show a prioritized decision queue containing product,
  AI-quality, AI-cost, system-health, incident, and data-quality signals.
- **FR-008**: Each decision signal MUST include what changed, affected segment,
  comparison baseline, severity, confidence, owner or suggested owner, freshness
  state, and next review link.
- **FR-009**: System MUST distinguish confirmed facts, sampled observations,
  inferred risks, and low-confidence candidates.
- **FR-010**: System MUST support quiet steady-state presentation when no
  significant changes are detected.

**Product Analytics**

- **FR-011**: System MUST provide question-first product analytics templates for
  activation, funnel drop-off, retention, feature adoption, user journey paths,
  release comparison, and experiment comparison where data exists.
- **FR-012**: System MUST show funnel count, step conversion, entry conversion,
  drop-off, comparison-period movement, and time-to-convert where available.
- **FR-013**: System MUST support reusable cohorts or segments with definition,
  population, owner, last computation time, and applicable workspaces.
- **FR-014**: System MUST show feature adoption as discovery, first use, repeat
  use, frequency, and downstream outcome where data exists.
- **FR-015**: System MUST provide user/account lookup for authorized users with
  privacy-safe profile, journey, support, incident, and quality context.

**AI Operations And Quality**

- **FR-016**: System MUST show AI task volume, success rate, failure categories,
  user-visible outcome metrics, latency bands, token usage, and estimated cost.
- **FR-017**: System MUST support segmentation by feature area, model,
  prompt/rubric/version context, release, environment, and cohort where fields
  are available.
- **FR-018**: System MUST link AI quality metrics to eval results, badcases,
  incidents, affected journey steps, and review owners.
- **FR-019**: System MUST flag cost increases that do not correspond to improved
  quality, reliability, or user outcomes.
- **FR-020**: System MUST show eval and badcase status without requiring PM
  users to open developer-only logs.

**Incidents, Badcases, Logs, And Traces**

- **FR-021**: System MUST provide an incident workspace grouped by severity,
  status, owner, affected feature area, affected journey, first seen, last seen,
  and trend.
- **FR-022**: System MUST allow incidents and badcases to link product metrics,
  user/account impact, AI tasks, eval cases, logs, traces, releases, comments,
  and evidence.
- **FR-023**: System MUST provide a logs and trace workspace with search,
  filters, field inspection, saved views, and correlation from logs to traces,
  incidents, badcases, releases, and product events.
- **FR-024**: System MUST support drilldown from product signal to correlated
  technical evidence when correlation identifiers exist.
- **FR-025**: System MUST show explicit coverage gaps when product events or AI
  flows lack trace/log correlation.
- **FR-026**: System MUST provide safe technical detail for agent runs, node
  executions, tool calls, LLM calls, retries, errors, and version context.

**Metric Trust And Reporting**

- **FR-027**: Every displayed metric MUST expose definition, owner, source,
  numerator, denominator where applicable, unit, selected period, freshness,
  completeness, and quality flags.
- **FR-028**: System MUST distinguish valid zero, missing data, partial data,
  stale data, and failed calculation.
- **FR-029**: System MUST provide review snapshots that preserve selected
  filters, values, comparison deltas, definitions, freshness, quality flags,
  annotations, and privacy-safe evidence links.
- **FR-030**: System MUST distinguish frozen snapshot values from current live
  values when late-arriving data changes current metrics.

**Governance, Privacy, And Audit**

- **FR-031**: System MUST enforce least-privilege access by workspace, field,
  action, export type, and visibility mode.
- **FR-032**: System MUST hide raw resumes, job descriptions, interview answers,
  raw prompts, raw model outputs, free-form sensitive text, secrets, tokens,
  passwords, and credentials by default.
- **FR-033**: System MUST require reason capture and audit logging before any
  approved masked raw or raw-like technical payload reveal.
- **FR-034**: System MUST audit admin access, saved-view changes, incident
  changes, badcase changes, sensitive reveals, exports, snapshot generation,
  and governance setting changes.
- **FR-035**: System MUST enforce export controls so exported reports contain
  only approved fields, redaction state, freshness state, selected filters, and
  audit metadata.
- **FR-036**: System MUST enforce retention windows and prevent expired
  sensitive payloads from being served from live or cached views.

### Key Entities

- **Console Role**: Internal role defining visible workspaces, fields, actions,
  exports, and visibility modes.
- **Decision Signal**: Prioritized item in the command center; includes change,
  severity, confidence, owner, affected segment, source metrics, and next link.
- **Metric Definition**: Plain-language definition, owner, numerator,
  denominator, unit, source, freshness target, and privacy class.
- **Metric Snapshot**: Period-bound metric value with dimensions, freshness,
  completeness, comparison baseline, and quality flags.
- **Cohort Segment**: Reusable user/account group with definition, population,
  owner, computation time, and applicable workspaces.
- **Funnel Definition**: Ordered journey steps with conversion, drop-off,
  time-to-convert, segment, and comparison semantics.
- **Feature Adoption Summary**: Discovery, first use, repeat use, frequency,
  and downstream outcome summary for one feature or feature group.
- **AI Quality Signal**: AI task quality, cost, latency, reliability, version,
  eval, badcase, and user-outcome context.
- **Incident**: Operational or product-impacting issue with severity, status,
  owner, affected journeys, linked evidence, comments, and resolution.
- **Badcase**: Human-reviewable AI or product quality case linked to evidence,
  privacy state, classification, owner, and resolution.
- **Log Event**: Structured or semi-structured operational event with time,
  source, severity, fields, correlation ids, and privacy class.
- **Trace**: Correlated execution chain linking business event, agent run, node,
  tool, LLM call, eval, logs, and release context where available.
- **Admin Audit Event**: Tamper-evident record of admin access, action, target,
  reason, visibility mode, result, and timestamp.
- **Review Snapshot**: Frozen product/quality/system report with filters,
  annotations, metric values, evidence links, freshness, and privacy state.
- **Governance Policy**: Access, reveal, export, and retention rules for the
  console and its evidence surfaces.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PM can identify the top three product, AI-quality, cost, or
  system-health issues for a selected period within 5 minutes from the command
  center without opening developer-only logs.
- **SC-002**: 100% of command-center decision signals show change, affected
  segment, comparison baseline, severity, confidence, freshness, and next
  review link.
- **SC-003**: A PM can answer activation drop-off, retention, feature adoption,
  and AI quality/cost questions from approved workspaces in one review session.
- **SC-004**: 100% of displayed metrics expose definition, owner, source,
  selected period, freshness, completeness, and quality flags.
- **SC-005**: Product analytics validation covers at least one funnel, one
  cohort/segment, one retention view, one feature-adoption view, and one
  release or version comparison.
- **SC-006**: AI operations validation covers at least one successful task, one
  failed task, one high-cost segment, one version comparison, one eval link,
  and one badcase link.
- **SC-007**: A seeded product anomaly can be drilled down to related incident,
  logs, trace, AI task, eval, badcase, and release context in under 3 minutes
  when correlation ids exist.
- **SC-008**: 100% of unauthorized attempts to access restricted workspaces,
  fields, sensitive reveals, or exports are denied before protected data is
  shown.
- **SC-009**: 100% of sensitive reveals, exports, incident updates, badcase
  updates, and governance changes create audit events with actor, target,
  action, time, result, and reason where required.
- **SC-010**: Privacy validation finds zero raw resumes, job descriptions,
  interview answers, raw prompts, raw model outputs, secrets, credentials, or
  unapproved free-form sensitive text in PM views and exported snapshots.
- **SC-011**: Data-quality validation distinguishes valid zero, missing data,
  partial data, stale data, and failed calculation without misleading success
  states.
- **SC-012**: Review snapshots generated from the console preserve visible
  filters, metric definitions, values, comparison deltas, freshness warnings,
  quality flags, annotations, and privacy-safe evidence links.

## Assumptions

- PM is the primary audience; operations and maintainer developers are important
  secondary audiences with different navigation and permission needs.
- The console may reuse existing telemetry, eval, badcase, audit, and
  observability data where those sources are trustworthy, but the REQ-044
  information architecture replaces the previous 035 and 039 UX direction.
- Existing user authentication can identify internal roles, while detailed role
  administration may be handled outside the first release.
- The first release favors curated, approved product questions over arbitrary BI
  exploration.
- Metric freshness and completeness are more important than pretending every
  number is real time.
- Cost values are estimates unless explicitly reconciled with a billing source.
- Developer debugging views are allowed, but sensitive payload visibility is
  governed by role, reason, audit, redaction, and retention policy.
- Reports are internal review artifacts, not public customer-facing documents.

## Migration 2026-07-05 — Admin entry consolidated into main SPA

**Scope**: build/dev infrastructure only. FR / SC / US / IA 全部未变, 仅
"独立 HTML entry → 主 SPA 子路由"。

**Before** (REQ-044 实施期):
- `index.html` (主 app) + `index.admin.html` (admin) 两个独立 entry
- `vite.config` 多入口 build (rollupOptions.input.admin) + dev 模式
  `adminConsolePathPlugin` 中间件把 `/admin-console/*` 强制 fallback 到
  `index.admin.html`
- `src/admin/main.tsx` 在 `#admin-root` 单独挂 admin router
- vite dev: 访问 `/admin-console/*` 直接 serve `index.admin.html` (其内嵌
  的 `<script src="/src/admin/main.tsx">` 启动 admin SPA)
- vite build: rollup 产出 `dist/index.html` + `dist/index.admin.html` 两份

**After** (本次迁移):
- `index.admin.html` 删除
- `src/admin/main.tsx` 删除 (其 css imports 移到 `src/admin/routes.tsx` 顶部)
- `vite.config`:
  - `appType`: `'custom'` → default `'spa'`
  - `build.rollupOptions.input`: 仅 `main` (admin entry 删除)
  - `adminConsolePathPlugin` 整体删除 (含 4 个 helpers:
    `requestUrl` / `requestPathname` / `acceptsHtml` / `shouldServeAdminConsole`
    / `shouldServeProductApp` / `serveHtmlEntry`)
- `src/App.tsx` 在受保护 `<Routes>` 下挂
  `<Route path="/admin-console/*" element={<AdminAppRoutes />} />`
  (lazy import + AdminAuthGuard 已内含在 `AdminAppRoutes`)
- vite dev: 访问 `/admin-console/*` 走默认 SPA fallback → `index.html`,
  React Router 接管
- vite build: rollup 仅产 `dist/index.html` (admin bundle inline 进主 chunk)

**Why**:
1. 用户实测访问 `/admin` 返回空白 — 主因 `App.tsx` 未挂 admin 路由, 而
   `index.admin.html` + admin SPA 又是独立产物 (用户访问 `/admin` 根本不会
   触发 `adminConsolePathPlugin`)。两个独立 entry 在 dev 模式下需要用户
   显式打开 `index.admin.html` 才能看到 admin UI, 这与"在主 app 内点击
   sidebar 跳转" 的预期不符
2. 独立 entry 还会让 bundle 重复打包 admin 依赖 (尽管 REQ-044 注释说
   "never bloats user app", 实际 vite 默认 chunk 划分下仍有显著重复)
3. 简化部署: 单 HTML 单入口, 减少运维心智

**Rollback guardrails** (回滚前必须读完本段):
- 回滚需要恢复 4 个文件 + 1 个 plugin:
  - `index.admin.html` (指向 `/src/admin/main.tsx`)
  - `src/admin/main.tsx` (含 `'./styles/admin.css'` + `'./styles/ai-operations.css'`
    imports)
  - `vite.config.{js,ts}` 的 `adminConsolePathPlugin` (4 helpers) + `appType: 'custom'`
    + `build.rollupOptions.input.admin`
- 回滚**不会**自动恢复 `src/App.tsx` 的 `<Route path="/admin-console/*" />`,
  需要同时从 `src/App.tsx` 删除该 `<Route>` (否则 admin SPA + 主 SPA 都会
  抢同一个 URL 段, 路由冲突)

**Evidence**:
- `docs/evidence/admin-probe/02-command-center.png` (复验截图, 显示
  AdminShell + CommandCenter 真实渲染)
- `vite.config.js` 第 1-15 行迁移注释
- `vite.config.ts` 第 1-23 行迁移注释
