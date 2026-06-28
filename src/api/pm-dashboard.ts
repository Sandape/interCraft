/**
 * PM Dashboard V1 API client — REQ-033 US1.
 *
 * Each method returns a typed envelope matching the backend
 * ``pm_dashboard`` module contract. Uses GET with query params per
 * ``specs/033-eval-pm-dashboard/contracts/pm-dashboard-api.md``.
 *
 * Endpoint surface (US1):
 *
 * - ``GET /api/v1/pm-dashboard/metrics/overview`` — returns
 *   ``{ panels: PanelResponse<OverviewPanelData>[], freshness_at, request_id }``.
 * - ``GET /api/v1/pm-dashboard/metrics/funnel`` — returns
 *   ``{ panel: PanelResponse<FunnelPanelData>, freshness_at, request_id }``.
 *
 * The other 6 panel types (resume, interview, AI ops, feedback, version)
 * are placeholders pending US2-US4 + US7 — they use the real backend
 * contract shape so swapping in the new endpoints is a one-line change.
 */
import { apiClient, withMock } from './client'
import type {
  AIOperationsPanel,
  DashboardFilter,
  FeedbackBadcasePanel,
  FunnelPanel,
  FunnelPanelData,
  MockInterviewPanel,
  OverviewPanel,
  OverviewPanelData,
  ResumeDiagnosisPanel,
  VersionExperimentPanel,
} from '../types/pm-dashboard'

// ---------------------------------------------------------------------------
// US1 — real endpoints
// ---------------------------------------------------------------------------

function _toQuery(filter: DashboardFilter): Record<string, string> {
  const q: Record<string, string> = {
    date_range_start: filter.date_range_start,
    date_range_end: filter.date_range_end,
  }
  if (filter.environment) q.environment = filter.environment
  if (filter.release_stage) q.release_stage = filter.release_stage
  if (filter.app_version) q.app_version = filter.app_version
  if (filter.prompt_fingerprint) q.prompt_fingerprint = filter.prompt_fingerprint
  if (filter.rubric_version) q.rubric_version = filter.rubric_version
  if (filter.model) q.model = filter.model
  if (filter.experiment_id) q.experiment_id = filter.experiment_id
  if (filter.graph) q.graph = filter.graph
  if (filter.node) q.node = filter.node
  return q
}

function _mockOverview(filter: DashboardFilter): OverviewPanel {
  return {
    metric_id: 'pm.overview',
    display_name: 'Product Overview',
    value: 0,
    unit: 'count',
    period_start: filter.date_range_start,
    period_end: filter.date_range_end,
    dimensions: {},
    source_of_truth: 'pm_metric_snapshots',
    freshness_at: new Date().toISOString(),
    quality_flags: { partial_data: true },
    data: {
      uv: 0,
      registered_users: 0,
      active_users: 0,
      completed_ai_tasks: 0,
      ai_success_rate: 0,
      total_tokens: 0,
      estimated_cost: 0,
      open_badcases: 0,
      is_estimate: true,
    },
  }
}

function _mockFunnel(filter: DashboardFilter): FunnelPanel {
  return {
    metric_id: 'pm.funnel',
    display_name: 'Core Funnel',
    value: 0,
    unit: 'count',
    period_start: filter.date_range_start,
    period_end: filter.date_range_end,
    dimensions: {},
    source_of_truth: 'product_events',
    freshness_at: 'unknown',
    quality_flags: { partial_data: true },
    data: { steps: [], total_entry: 0, total_completion: 0 } as FunnelPanelData,
  }
}

export const pmDashboardApi = {
  /**
   * GET /api/v1/pm-dashboard/metrics/overview — US1 (T075).
   *
   * Returns the bundled overview panel with all 8 FR-002 fields. Real
   * backend returns ``{ panels: [...], freshness_at, request_id }``;
   * the helper unwraps to the first panel for the typed return shape.
   */
  getOverview: (filter: DashboardFilter) =>
    withMock(
      async () => {
        const env = await apiClient.request<{
          panels: OverviewPanel[]
          freshness_at: string
          request_id: string
        }>({
          method: 'GET',
          path: '/api/v1/pm-dashboard/metrics/overview',
          query: _toQuery(filter),
        })
        return env.panels[0] ?? _mockOverview(filter)
      },
      () => _mockOverview(filter),
    )(),

  /**
   * GET /api/v1/pm-dashboard/metrics/funnel — US1 (T075).
   *
   * Returns the funnel panel with ordered steps + per-step conversion
   * rates. Real backend returns ``{ panel: {...}, freshness_at,
   * request_id }``; the helper unwraps to the typed panel.
   */
  getFunnel: (filter: DashboardFilter) =>
    withMock(
      async () => {
        const env = await apiClient.request<{
          panel: FunnelPanel
          freshness_at: string
          request_id: string
        }>({
          method: 'GET',
          path: '/api/v1/pm-dashboard/metrics/funnel',
          query: _toQuery(filter),
        })
        return env.panel ?? _mockFunnel(filter)
      },
      () => _mockFunnel(filter),
    )(),

  // -- US2-US4 + US7 placeholders. Real endpoints will land in subsequent
  // sub-batches; the typed shapes match the contract in
  // ``contracts/pm-dashboard-api.md``.

  getResumeDiagnosis: (filter: DashboardFilter) =>
    withMock(
      () =>
        apiClient.request<ResumeDiagnosisPanel>({
          method: 'GET',
          path: '/api/v1/pm-dashboard/metrics/resume-diagnosis',
          query: _toQuery(filter),
        }),
      () => ({
        metric_id: 'pm.resume_diagnosis',
        display_name: 'Resume Diagnosis',
        value: 0,
        unit: 'count' as const,
        period_start: filter.date_range_start,
        period_end: filter.date_range_end,
        dimensions: {},
        source_of_truth: 'resume_diagnosis_outcomes',
        freshness_at: 'unknown',
        quality_flags: { partial_data: true },
        data: {
          diagnosis_count: 0,
          success_rate: 0,
          failure_rate: 0,
          report_views: 0,
          suggestions_shown: 0,
          suggestions_accepted: 0,
          acceptance_rate: 0,
          score_delta_avg: null,
        },
      }),
    )(),

  getMockInterview: (filter: DashboardFilter) =>
    withMock(
      () =>
        apiClient.request<MockInterviewPanel>({
          method: 'GET',
          path: '/api/v1/pm-dashboard/metrics/mock-interview',
          query: _toQuery(filter),
        }),
      () => ({
        metric_id: 'pm.mock_interview',
        display_name: 'Mock Interview',
        value: 0,
        unit: 'count' as const,
        period_start: filter.date_range_start,
        period_end: filter.date_range_end,
        dimensions: {},
        source_of_truth: 'interview_outcomes',
        freshness_at: 'unknown',
        quality_flags: { partial_data: true },
        data: {
          starts: 0,
          completions: 0,
          completion_rate: 0,
          avg_question_count: 0,
          report_views: 0,
          retries: 0,
          failure_rate: 0,
          failure_categories: {},
        },
      }),
    )(),

  getAIOperations: (filter: DashboardFilter) =>
    withMock(
      () =>
        apiClient.request<AIOperationsPanel>({
          method: 'GET',
          path: '/api/v1/pm-dashboard/metrics/ai-operations',
          query: _toQuery(filter),
        }),
      () => ({
        metric_id: 'pm.ai_operations',
        display_name: 'AI Operations',
        value: 0,
        unit: 'count' as const,
        period_start: filter.date_range_start,
        period_end: filter.date_range_end,
        dimensions: {},
        source_of_truth: 'ai_invocation_records',
        freshness_at: 'unknown',
        quality_flags: { partial_data: true },
        data: {
          call_count: 0,
          success_rate: 0,
          failure_rate: 0,
          retry_count: 0,
          p50_latency_ms: 0,
          p95_latency_ms: 0,
          total_tokens: 0,
          estimated_cost: 0,
          cache_hit_rate: null,
          model_breakdown: {},
          graph_node_breakdown: {},
        },
      }),
    )(),

  getFeedbackBadcase: (filter: DashboardFilter) =>
    withMock(
      () =>
        apiClient.request<FeedbackBadcasePanel>({
          method: 'GET',
          path: '/api/v1/pm-dashboard/metrics/feedback-badcase',
          query: _toQuery(filter),
        }),
      () => ({
        metric_id: 'pm.feedback_badcase',
        display_name: 'Feedback & Badcase',
        value: 0,
        unit: 'count' as const,
        period_start: filter.date_range_start,
        period_end: filter.date_range_end,
        dimensions: {},
        source_of_truth: 'badcases + feedback_signals',
        freshness_at: 'unknown',
        quality_flags: { partial_data: true },
        data: {
          thumbs_up: 0,
          thumbs_down: 0,
          helpfulness_score_avg: null,
          text_feedback_count: 0,
          badcase_count_by_status: {},
          badcase_count_by_severity: {},
          badcase_count_by_type: {},
          closure_rate: 0,
          fix_result_breakdown: {},
        },
      }),
    )(),

  getVersionExperiment: (filter: DashboardFilter) =>
    withMock(
      () =>
        apiClient.request<VersionExperimentPanel>({
          method: 'GET',
          path: '/api/v1/pm-dashboard/metrics/version-experiment',
          query: _toQuery(filter),
        }),
      () => ({
        metric_id: 'pm.version_experiment',
        display_name: 'Version & Experiment',
        value: 0,
        unit: 'count' as const,
        period_start: filter.date_range_start,
        period_end: filter.date_range_end,
        dimensions: {},
        source_of_truth: 'pm_metric_snapshots.dimensions',
        freshness_at: 'unknown',
        quality_flags: { partial_data: true },
        data: {
          app_versions: [],
          prompt_fingerprints: [],
          rubric_versions: [],
          experiment_groups: [],
          trace_coverage: 0,
          run_id_count: 0,
        },
      }),
    )(),
}