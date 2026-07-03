/**
 * Admin Console / Log Center types — REQ-039 B2.
 *
 * Mirrors backend/app/modules/admin_console/schemas.py.
 */

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
