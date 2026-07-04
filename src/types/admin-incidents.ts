/**
 * Admin Console Incidents & Badcases types — REQ-044 US4.
 *
 * Mirrors backend/app/modules/admin_console/incidents/schemas.py.
 *
 * [CROSS-TEAM-DEBT] Real incident persistence lands in Phase 2 batch 4
 * + governance US6 audit. Until then the seed-driven schema is the
 * source of truth; types MUST stay in lockstep with the backend
 * Pydantic models.
 */

// --- FR-021: Incident enums ------------------------------------------------

export type IncidentSeverity = 'P0' | 'P1' | 'P2' | 'P3'

export type IncidentStatus =
  | 'open'
  | 'investigating'
  | 'resolved'
  | 'postmortem'

export type IncidentTrend = 'rising' | 'stable' | 'declining'

// --- FR-022: Evidence link enum (8 types) ----------------------------------

export type EvidenceLinkType =
  | 'product_metric'
  | 'user_impact'
  | 'ai_task'
  | 'eval_case'
  | 'log'
  | 'trace'
  | 'release'
  | 'comment'

export type EvidencePrivacyClass = 'public' | 'internal' | 'restricted'

// --- FR-021: Audit trail ---------------------------------------------------

export interface AuditTrailEntry {
  actor: string
  timestamp: string
  reason: string
  beforeState: Record<string, unknown>
  afterState: Record<string, unknown>
  action: string
}

// --- FR-021: Incident ------------------------------------------------------

export interface Incident {
  id: string
  title: string
  severity: IncidentSeverity
  status: IncidentStatus
  owner: string
  affectedFeatureArea: string
  affectedJourneyStep: string
  firstSeenAt: string
  lastSeenAt: string
  trend: IncidentTrend
  candidate: boolean
  commonRootCause: string | null
  linkedIncidentIds: string[]
  ingestionDelayed: boolean
  freshnessAt: string
  affectedCount: number
  description: string
  auditTrail: AuditTrailEntry[]
}

export interface IncidentListResponse {
  incidents: Incident[]
  total: number
  confirmedCount: number
  candidateCount: number
  freshnessAt: string
}

// --- FR-022: Evidence link + list envelope ---------------------------------

export interface EvidenceLink {
  type: EvidenceLinkType
  referenceId: string
  label: string
  href: string
  privacyClass: EvidencePrivacyClass
  summary: string | null
}

export interface EvidenceLinkListResponse {
  incidentId: string
  evidenceLinks: EvidenceLink[]
  total: number
  coverage: Record<string, number>
}

// --- FR-022: Comments ------------------------------------------------------

export interface Comment {
  id: string
  incidentId: string
  actor: string
  body: string
  reason: string | null
  createdAt: string
}

export interface CommentListResponse {
  incidentId: string
  comments: Comment[]
  total: number
}

export interface CommentCreateRequest {
  body: string
  reason?: string | null
}

// --- EC-4: Status change + audit trail -------------------------------------

export type IncidentStatusValue = IncidentStatus

export interface StatusChangeRequest {
  newStatus: IncidentStatusValue
  newOwner?: string | null
  reason: string
}

export interface AuditTrail {
  incidentId: string
  entries: AuditTrailEntry[]
  total: number
}

// --- FR-023: Badcase enums + entity ----------------------------------------

export type BadcaseStatus = 'open' | 'reviewing' | 'closed' | 'escalated'

export type BadcasePrivacyClass = 'public' | 'internal' | 'restricted'

export interface Badcase {
  id: string
  evalVerdict: string
  affectedFeatureArea: string
  affectedUserId: string
  privacyClass: BadcasePrivacyClass
  classification: string
  owner: string
  status: BadcaseStatus
  resolution: string
  firstSeenAt: string
  incidentId: string | null
  freshnessAt: string
  description: string
  auditTrail: AuditTrailEntry[]
}

export interface BadcaseListResponse {
  badcases: Badcase[]
  total: number
  openCount: number
  escalatedCount: number
  freshnessAt: string
}

export interface BadcaseEscalateResponse {
  badcaseId: string
  incidentId: string
  escalatedAt: string
  escalatedBy: string
}

// --- AC-21.4: Filter bar state --------------------------------------------

export interface IncidentFilters {
  severity: IncidentSeverity | 'all'
  status: IncidentStatus | 'all'
  owner: string | 'all'
  featureArea: string | 'all'
  journey: string | 'all'
  dateRange: '24h' | '7d' | '30d' | 'all'
  trend: IncidentTrend | 'all'
}
