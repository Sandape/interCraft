/**
 * Admin Console Governance / Audit / Export / Retention types — REQ-044 US6.
 *
 * Mirrors backend/app/modules/admin_console/governance/schemas.py.
 *
 * REQ-044 US6 Frontend unions — trust-but-verify front-end unions.
 * The actual RBAC enforcement lives in the backend; see the
 * CROSS-TEAM-DEBT tag in the REQ-044 US6 AC matrix (Phase 2 batch 5
 * will sync backend Pydantic Literal definitions with these string
 * literals).
 */

// --- FR-031 Workspace + Role + Capability ---

export type WorkspaceId =
  | 'command-center'
  | 'product-analytics'
  | 'ai-operations'
  | 'incidents-badcases'
  | 'logs-and-traces'
  | 'users-accounts'
  | 'reports'
  | 'governance'
  | 'all' // reserved

export type ConsoleRole =
  | 'pm'
  | 'operations'
  | 'maintainer'
  | 'reviewer'
  | 'owner'
  | 'unknown' // reserved fallback

export type CapabilityToken =
  | 'READ'
  | 'WRITE'
  | 'CHANGE'
  | 'EXPORT'
  | 'REVEAL'
  | 'AUDIT'

export interface AccessMatrixEntry {
  role: ConsoleRole
  workspace: WorkspaceId
  capability: CapabilityToken
  allowed: boolean
}

export interface AccessMatrixResponse {
  entries: AccessMatrixEntry[]
  total: number
  role_count: number
  workspace_count: number
  capability_count: number
  freshness_at: string
  data_status: DataStatus
  updated_at: string
}

// --- FR-031 (field-level) + FR-028 ---

export type VisibilityMode = 'hidden' | 'masked' | 'full'

export type DataStatus =
  | 'valid_zero'
  | 'missing'
  | 'partial'
  | 'stale'
  | 'failed'

// --- FR-032 UserPrivacySafe — NO raw_* fields ---

export interface UserPrivacySafe {
  user_id: string
  display_name?: string | null
  email?: string | null
  role?: string | null
  journey_summary?: string | null
  support_incident_count: number
  quality_issue_count: number
  data_status: DataStatus
  visibility_mode: VisibilityMode
  fetched_at: string
}

// --- FR-033 Sensitive reveal request ---

export type SensitiveTargetType =
  | 'user_resume'
  | 'user_interview'
  | 'ai_prompt'
  | 'ai_model_output'
  | 'incident_payload'

export interface RevealRequestCreate {
  target_type: SensitiveTargetType
  target_id: string
  reason: string // >= 20 chars enforced server-side (FR-033)
}

export interface RevealRequest {
  request_id: string
  actor: string
  target_type: SensitiveTargetType
  target_id: string
  reason: string
  visibility_mode: VisibilityMode
  result: 'approved' | 'denied'
  audit_event_id: string
  requested_at: string
}

export interface RevealRequestListResponse {
  requests: RevealRequest[]
  total: number
  data_status: DataStatus
}

// --- FR-034 Audit event taxonomy (11 actions) ---

export type AuditAction =
  // US1 baseline (4)
  | 'replay_triggered'
  | 'diff_computed'
  | 'tag_added'
  | 'tag_removed'
  // US4 (4)
  | 'incident_status_changed'
  | 'incident_comment_added'
  | 'badcase_status_changed'
  | 'badcase_escalated'
  // US6 (3)
  | 'sensitive_reveal'
  | 'export'
  | 'review_snapshot'

export type AuditResult = 'approved' | 'denied' | 'executed' | 'failed'

export type AuditTargetKind =
  // US1
  | 'trace'
  | 'task'
  | 'diff'
  // US4
  | 'incident'
  | 'badcase'
  // US6
  | 'user_resume'
  | 'user_interview'
  | 'ai_prompt'
  | 'ai_model_output'
  | 'incident_payload'
  | 'export'
  | 'snapshot'
  | 'governance'

export interface AuditEvent {
  event_id: string
  actor: string
  timestamp: string
  target_kind: AuditTargetKind
  target_id?: string | null
  action: AuditAction
  reason?: string | null
  result: AuditResult
  visibility_mode: VisibilityMode
}

export interface AuditEventListResponse {
  events: AuditEvent[]
  total: number
  data_status: DataStatus
}

// --- FR-035 Export ---

export type ExportFormat = 'json' | 'csv' | 'markdown'

export interface ExportRequestCreate {
  workspace: WorkspaceId
  filters: Record<string, unknown>
  format: ExportFormat
}

export interface ExportResponse {
  export_id: string
  download_url: string
  expires_at: string
  fields_included: string[]
  fields_redacted: string[]
  freshness_warnings: string[]
  audit_metadata: Record<string, unknown>
  format: ExportFormat
  workspace: WorkspaceId
  created_at: string
}

// --- FR-036 Retention policy ---

export type RetentionAction = 'block' | 'warn' | 'redact'

export interface RetentionPolicy {
  workspace_field: WorkspaceId
  retention_days: number
  action: RetentionAction
  last_reconciled_at: string
  updated_at: string
  updated_by: string
}

export interface RetentionPolicyResponse {
  policies: RetentionPolicy[]
  total: number
  data_status: DataStatus
}

export interface RetentionPolicyUpdate {
  workspace_field: WorkspaceId
  retention_days: number
  action: RetentionAction
}

// --- Quality flags (FR-028 + SC-011) ---

export type QualityFlag =
  | 'valid_zero'
  | 'missing'
  | 'partial'
  | 'stale'
  | 'failed'
