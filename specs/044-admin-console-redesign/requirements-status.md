# REQ-044 Requirement Status

Status date: 2026-07-03

REQ-044 is the active management-console redesign and supersedes REQ-035 and
REQ-039. This file tracks requirement status after the specify phase.

## User Stories

| ID | Requirement | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | PM Opens A Decision Command Center | planned | `spec.md` | First-screen product-led operating view. |
| US2 | PM Investigates Funnel, Retention, And Feature Adoption | planned | `spec.md` | Question-first product analytics workspace. |
| US3 | PM Reviews AI Quality, Cost, And Release Impact | planned | `spec.md` | AI quality, cost, reliability, eval, and version context. |
| US4 | Operations Triage Incidents From Business Impact | planned | `spec.md` | Incident and anomaly workflow starts from user/product impact. |
| US5 | Maintainer Developer Drills From Signal To Root Cause | planned | `spec.md` | Logs and traces are drilldowns from business/quality signals. |
| US6 | Govern Access, Audit, And Export | planned | `spec.md` | Least privilege, audit, reveal, export, and retention controls. |
| US7 | PM Shares A Review Snapshot | planned | `spec.md` | Privacy-safe internal review snapshots. |

## Functional Requirement Groups

| Group | Coverage | Status | Notes |
|---|---|---|---|
| FR-001 - FR-006 | Information architecture and roles | planned | Establishes REQ-044 as the active source of truth. |
| FR-007 - FR-010 | Command center | planned | PM default landing and decision queue. |
| FR-011 - FR-015 | Product analytics | planned | Funnels, cohorts, retention, adoption, and user/account context. |
| FR-016 - FR-020 | AI operations and quality | planned | AI quality, cost, eval, badcase, and version impact. |
| FR-021 - FR-026 | Incidents, badcases, logs, and traces | planned | Impact-first triage and technical drilldown. |
| FR-027 - FR-030 | Metric trust and reporting | planned | Definitions, freshness, quality flags, and snapshots. |
| FR-031 - FR-036 | Governance, privacy, and audit | planned | Least privilege, sensitive reveal, export, audit, and retention. |

## Success Criteria

| ID Range | Status | Notes |
|---|---|---|
| SC-001 - SC-012 | planned | To be validated after implementation tasks and evidence exist. |

## Architecture Change Log

| Date | Change | Reason | Evidence |
|---|---|---|---|
| 2026-07-05 | Admin entry 合并到主 SPA (删 `index.admin.html` + `src/admin/main.tsx` + `adminConsolePathPlugin`) | 用户实测 `/admin` 空白 — 独立 entry 设计让 sidebar 跳转无法命中 admin SPA; 简化部署 | `spec.md` Migration 2026-07-05 区块; `vite.config.{js,ts}` 迁移注释; `docs/evidence/admin-probe/02-command-center.png` |
