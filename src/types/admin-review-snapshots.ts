/**
 * Admin Console Review Snapshots + Metric Trust types — REQ-044 US7.
 *
 * Mirrors backend/app/modules/admin_console/review_snapshots/schemas.py.
 *
 * The DataStatus + WorkspaceId + VisibilityMode unions are imported
 * from US6 admin-governance types — DO NOT redeclare (FR-028 + SC-011
 * keep the 5-state + 8-workspace surfaces unified).
 */

import type {
  DataStatus,
  VisibilityMode,
  WorkspaceId,
} from './admin-governance'

// --- FR-027 — MetricDefinition 10 fields ---

export interface MetricDefinition10Field {
  metric_id: string
  name: string
  /** FR-027 #1 */
  definition: string
  /** FR-027 #2 */
  owner: string
  /** FR-027 #3 */
  source: string
  /** FR-027 #4 */
  numerator: string
  /** FR-027 #5 */
  denominator: string
  /** FR-027 #6 */
  unit: string
  /** FR-027 #7 */
  period: string
  /** FR-027 #8 */
  freshness: string
  /** FR-027 #9 */
  completeness: string
  /** FR-027 #10 — reuses US6 DataStatus 5-state Literal */
  quality_flags: DataStatus
}

// --- FR-029 / FR-030 — frozen / current / delta / evidence ---

export interface FrozenValue {
  metric_id: string
  value: number
  unit: string
  captured_at: string
  data_status: DataStatus
}

export interface CurrentValue {
  metric_id: string
  value: number
  unit: string
  captured_at: string
  data_status: DataStatus
}

export interface ComparisonDelta {
  metric_id: string
  delta_pct: number
  period: string
}

export interface EvidenceLink {
  label: string
  kind: 'incident' | 'trace' | 'ai_task' | 'badcase' | 'export'
  target_id: string
}

// --- FR-029 — Review snapshot request/response ---

export type ReviewSnapshotFormat = 'json' | 'markdown'

export interface ReviewSnapshotRequest {
  workspace: WorkspaceId
  filters: Record<string, unknown>
  comparison_period: string
  annotations: string
  format: ReviewSnapshotFormat
}

export interface ReviewSnapshotResponse {
  snapshot_id: string
  workspace: WorkspaceId
  generated_at: string
  generated_by: string
  filters: Record<string, unknown>
  frozen_values: FrozenValue[]
  comparison_deltas: ComparisonDelta[]
  metric_definitions: MetricDefinition10Field[]
  freshness_warnings: string[]
  quality_flags: Record<string, DataStatus>
  annotations: string
  evidence_links: EvidenceLink[]
  current_values: CurrentValue[]
  cohort_definition_changed: boolean
  cohort_change_warning: string | null
  late_arriving_warnings: string[]
  download_url: string
  expires_at: string
  data_status: DataStatus
  visibility_mode: VisibilityMode
  comparison_period: string
}

export interface ReviewSnapshotListResponse {
  snapshots: ReviewSnapshotResponse[]
  total: number
  data_status: DataStatus
}

// --- AC-27.4 sentinel ---

export const NOT_PROVIDED = '(not provided)' as const