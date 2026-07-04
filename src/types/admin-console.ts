/**
 * Admin Console / Log Center types — REQ-039 B2 + REQ-044 IA shell.
 *
 * Mirrors backend/app/modules/admin_console/schemas.py.
 *
 * REQ-044 WorkspaceId + ConsoleRole are **trust-but-verify** front-end
 * unions. The actual RBAC enforcement lives in the backend; see the
 * CROSS-TEAM-DEBT tag in the REQ-044 IA AC matrix (Phase 2 US6 will
 * sync backend Pydantic Literal definitions with these string
 * literals).
 */

// --- REQ-044 IA: 8 stable top-level workspaces ---------------------------

export type WorkspaceId =
  | 'command-center'
  | 'product-analytics'
  | 'ai-operations'
  | 'incidents-badcases'
  | 'logs-and-traces'
  | 'users-accounts'
  | 'reports'
  | 'governance'
  // reserved — internal "show all" sentinel, never a real route
  | 'all'

// 5 角色 + reserved unknown — see FR-002 / AC-2.2
export type ConsoleRole =
  | 'pm'
  | 'operations'
  | 'maintainer'
  | 'reviewer'
  | 'owner'
  // reserved — unknown role → fallback to pm
  | 'unknown'

// --- REQ-044 FR-006 saved views ------------------------------------------

// 5 console roles (FR-002 / AC-2.5) can appear in shared_with.
// Mirrors backend app/modules/admin_console/saved_views/schemas.py:
// SharedWithRole Literal.
export type SharedWithRole = 'pm' | 'operations' | 'maintainer' | 'reviewer' | 'owner'

// Mirrors backend SavedViewTrustStatus Literal — verified / pending / deprecated.
export type SavedViewTrustStatusStrict =
  | 'verified'
  | 'pending'
  | 'deprecated'

// SavedViewTrustStatus now accepts BOTH the legacy 3-state ('trusted' /
// 'provisional' / 'unverified' — used by the US1 IA shell) AND the
// strict 3-state ('verified' / 'pending' / 'deprecated' — used by
// the CROSS real backend). The repository layer normalises
// strict→legacy for callers that haven't migrated yet.
export type SavedViewTrustStatus =
  | 'trusted'
  | 'provisional'
  | 'unverified'
  | 'verified'
  | 'pending'
  | 'deprecated'

export interface SavedView {
  id?: string
  name: string
  filters: Record<string, string>
  owner: string
  description: string
  trustStatus: SavedViewTrustStatus
  // CROSS FR-006 extension: cross-workspace shared_with (12 fields).
  workspace_id?: string
  owner_user_id?: string
  created_at?: string
  updated_at?: string
  shared_with?: SharedWithRole[]
  version?: number
  warnings?: string[]
}

// Detail response envelope — wraps a single view with role-aware
// warnings (EC-1 deleted cohort, EC-2 permission revoked).
export interface SavedViewDetailResponse {
  view: SavedView
  permission_revoked: boolean
  warnings: string[]
}

// Create response envelope — POST returns the new view + the
// audit_event_id (FR-034 AC-6.7).
export interface SavedViewCreateResponse {
  view: SavedView
  audit_event_id: string
}

// Legacy create / update input shapes — kept for backward compat with
// the US1 IA shell. The CROSS repository normalises them into the
// strict backend Pydantic body shape.
export interface CreateSavedViewInput {
  name: string
  filters: Record<string, string>
  owner: string
  description: string
  trustStatus: SavedViewTrustStatus
}

export interface UpdateSavedViewInput {
  name?: string
  filters?: Record<string, string>
  description?: string
  trustStatus?: SavedViewTrustStatus
}

// Backend request bodies — wire-format names match the Pydantic
// schemas in backend/app/modules/admin_console/saved_views/schemas.py.
export interface SavedViewCreateRequest {
  name: string
  workspace_id: string
  filters: Record<string, string>
  description: string
  shared_with: SharedWithRole[]
  trust_status: 'verified' | 'pending' | 'deprecated'
}

export interface SavedViewUpdateRequest {
  name?: string
  filters?: Record<string, string>
  description?: string
  shared_with?: SharedWithRole[]
  trust_status?: 'verified' | 'pending' | 'deprecated'
  version?: number
}

export interface SavedViewListResponse {
  views: SavedView[]
  total: number
  workspace_id?: string
  role_view?: SharedWithRole
  warnings?: string[]
}

// Cross-team contract lock (memory feedback_cross_team_contract_l031):
// widening the SharedWithRole union here MUST be synced with the
// backend SharedWithRole Literal in
// app/modules/admin_console/saved_views/schemas.py.

export type NormalizedStatus = 'success' | 'failed' | 'pending' | 'running'
export type NormalizedTaskType =
  | 'interview'
  | 'resume_optimize'
  | 'ability_diagnose'
  | 'error_coach'
  | 'general_coach'
  | 'unknown'

export interface AdminTrace {
  id: string
  task_id: string | null
  task_type: string
  prompt_version: string
  model: string
  status: string
  error_message: string | null
  replay_of: string | null
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
}

export interface AdminTraceListResponse {
  traces: AdminTrace[]
  total: number
}

export interface AdminTraceNode {
  node_id: string
  name: string
  status: string
  parent: string | null
  started_at: string | null
  ended_at: string | null
  has_input: boolean
  has_output: boolean
}

export interface AdminTraceNodesResponse {
  trace_id: string
  nodes: AdminTraceNode[]
}

export interface AdminTaskTag {
  tag: string
  created_at: string
}

export interface AdminTaskTagListResponse {
  tags: AdminTaskTag[]
}

export interface AdminTaskTagCreateRequest {
  tag: string
}

export interface AdminReplayResponse {
  new_trace_id: string
  replay_of: string
  prompt_version: string
  model: string
  status: string
  created_at: string
}

export type AdminDiffFieldOp = 'add' | 'del' | 'mod'
export type AdminDiffSide = 'left' | 'right' | 'both'

export interface AdminDiffFieldEntry {
  path: string
  op: AdminDiffFieldOp
  left?: unknown
  right?: unknown
}

export interface AdminDiffNodeEntry {
  node_name: string
  side: AdminDiffSide
  status_left: string | null
  status_right: string | null
  fields: AdminDiffFieldEntry[]
}

export interface AdminDiffResponse {
  left_trace_id: string
  right_trace_id: string
  task_type: string
  nodes: AdminDiffNodeEntry[]
  node_count: number
}

export interface AdminDiffRequest {
  left_trace_id: string
  right_trace_id: string
}

export interface AdminFilters {
  task_type: string
  status: string
  search: string
  since: string
}

export interface CallerCapabilities {
  is_admin: boolean
  capabilities: string[]
}

export type AdminPresetTag =
  | 'needs-fix'
  | 'intermittent-flake'
  | 'customer-escalation'
  | 'p1-incident'
  | 'monitoring'

export const ADMIN_PRESET_TAGS: AdminPresetTag[] = [
  'needs-fix',
  'intermittent-flake',
  'customer-escalation',
  'p1-incident',
  'monitoring',
]

export const ADMIN_TAG_COLORS: Record<AdminPresetTag, string> = {
  'needs-fix': '#dc2626',
  'intermittent-flake': '#f59e0b',
  'customer-escalation': '#7c3aed',
  'p1-incident': '#be123c',
  monitoring: '#0891b2',
}
