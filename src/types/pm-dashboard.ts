/** PM Dashboard V1 type barrel — REQ-033 US1-US4 + US7.

Mirror of the backend `pm_dashboard` module response envelopes. Every
panel returns a `PanelResponse` with metric id + dimensions + freshness +
quality flags so PM can distinguish current facts from stale or missing
data (FR-009).
*/

export type Environment = 'local' | 'ci' | 'staging' | 'production'
export type ReleaseStage = 'development' | 'release_candidate' | 'production' | 'unknown'

export interface DashboardFilter {
  date_range_start: string // ISO 8601
  date_range_end: string
  environment?: Environment
  release_stage?: ReleaseStage
  app_version?: string
  prompt_fingerprint?: string
  rubric_version?: string
  model?: string
  experiment_id?: string
  graph?: string
  node?: string
}

export interface PanelQualityFlags {
  missing_version_fields?: string[]
  sampled_data?: boolean
  delayed_ingestion?: boolean
  partial_data?: boolean
}

export interface PanelResponse<T = unknown> {
  metric_id: string
  display_name: string
  value: number
  unit: 'count' | 'percent' | 'score' | 'tokens' | 'ms' | 'currency' | 'days'
  period_start: string
  period_end: string
  dimensions: Record<string, string>
  numerator?: number
  denominator?: number
  source_of_truth: string
  freshness_at: string
  quality_flags: PanelQualityFlags
  data: T
}

// --- Panel-specific payloads ----------------------------------------------------

export interface OverviewPanelData {
  uv: number
  registered_users: number
  active_users: number
  completed_ai_tasks: number
  ai_success_rate: number
  total_tokens: number
  estimated_cost: number
  open_badcases: number
  /** FR-008: cost fields are estimates (not billing). */
  is_estimate?: boolean
}

export interface FunnelStep {
  step_name: string
  step_order: number
  count: number
  conversion_from_previous: number
  conversion_from_entry: number
  largest_drop_off: boolean
}

export interface FunnelPanelData {
  steps: FunnelStep[]
  total_entry: number
  total_completion: number
}

export interface ResumeDiagnosisMetric {
  success_count: number
  total_count: number
  success_rate: number
  report_views: number
  suggestions_shown: number
  suggestions_accepted: number
  acceptance_rate: number
  score_delta_before: number
  score_delta_after: number
  score_delta: number
}

export interface InterviewMetric {
  starts: number
  completions: number
  completion_rate: number
  avg_question_count: number
  report_views: number
  retries: number
  failure_rate: number
  failure_categories: Record<string, number>
}

export interface AIOperationMetric {
  call_count: number
  success_count: number
  failure_count: number
  success_rate: number
  failure_rate: number
  retry_count: number
  p50_latency_ms: number
  p95_latency_ms: number
  p99_latency_ms: number
  estimated_cost: number
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  is_estimate: boolean
  model_breakdown: Record<string, number>
  graph_breakdown: Record<string, number>
  node_breakdown: Record<string, number>
  prompt_fingerprint_breakdown: Record<string, number>
}

export interface FeedbackBadcaseMetric {
  thumbs_up: number
  thumbs_down: number
  helpfulness_score_avg: number | null
  text_feedback_count: number
  badcase_count_by_status: Record<string, number>
  badcase_count_by_severity: Record<string, number>
  badcase_count_by_type: Record<string, number>
  closure_rate: number
  fix_result_breakdown: Record<string, number>
}

export interface VersionExperimentMetric {
  event_count: number
  distinct_prompt_fingerprints: number
  distinct_models: number
  distinct_app_versions: number
  distinct_experiments: number
  top_versions: Array<{
    prompt_fingerprint: string
    rubric_version: string
    app_version: string
    model: string
    count: number
  }>
  top_experiments: Array<{ experiment_id: string; count: number }>
  trace_available: boolean
  top_versions_source: string
}

// --- Convenience typed panel exports ------------------------------------------

export type OverviewPanel = PanelResponse<OverviewPanelData>
export type FunnelPanel = PanelResponse<FunnelPanelData>
export type ResumeDiagnosisPanel = PanelResponse<ResumeDiagnosisMetric>
export type MockInterviewPanel = PanelResponse<InterviewMetric>
export type AIOperationsPanel = PanelResponse<AIOperationMetric>
export type FeedbackBadcasePanel = PanelResponse<FeedbackBadcaseMetric>
export type VersionExperimentPanel = PanelResponse<VersionExperimentMetric>