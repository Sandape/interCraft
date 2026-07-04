/**
 * Admin Console / AI Operations types — REQ-044 US3.
 *
 * Mirrors backend/app/modules/admin_console/ai_operations/schemas.py.
 *
 * [CROSS-TEAM-DEBT] Phase 2 batch 3 will replace the seed-driven
 * AI tasks / quality issues / cost-quality flag with real metric
 * snapshots from the pm_dashboard ``ai-operations`` + REQ-026
 * ``eval`` + REQ-033 ``badcases`` data sources. The TypeScript
 * surface (this file) must remain in lockstep with the backend
 * Pydantic Literals.
 *
 * FR-017 version dimensions + FR-018 quality issue link fields +
 * FR-019 cost-quality flag fields are the canonical FR contract for
 * the AI Operations workspace.
 */

import type { CohortSegment } from './admin-product-analytics'

// --- FR-016 4 FeatureAreas -------------------------------------------------

export type FeatureArea =
  | 'resume_optimize'
  | 'mock_interview'
  | 'error_coach'
  | 'resume_render'

// --- FR-016 5 failure categories ------------------------------------------

export type FailureCategory =
  | 'timeout'
  | 'token_limit'
  | 'parse_error'
  | 'eval_failed'
  | 'api_5xx'

// --- FR-017 4 version dimensions ------------------------------------------

export type VersionDimension =
  | 'prompt_fingerprint'
  | 'rubric_version'
  | 'model'
  | 'app_version'

// --- FR-016 KPI tiles (workspace header) ---------------------------------

export interface KPIBundle {
  totalVolume: number
  successRate: number
  p95LatencyMs: number
  totalCostUsd: number
  freshnessAt: string
  isEstimate: boolean
}

export interface KPIBundleResponse {
  kpis: KPIBundle
  freshnessAt: string
}

// --- FR-016 Volume by feature ---------------------------------------------

export interface VolumeByFeatureRow {
  featureArea: FeatureArea
  callCount: number
  successCount: number
  failureCount: number
}

export interface VolumeByFeatureResponse {
  rows: VolumeByFeatureRow[]
  total: number
  freshnessAt: string
}

// --- FR-016 Failure categories --------------------------------------------

export interface FailureCategoryBreakdown {
  category: FailureCategory
  count: number
  share: number
}

export interface FailureCategoryResponse {
  breakdown: FailureCategoryBreakdown[]
  total: number
  freshnessAt: string
}

// --- FR-016 Latency bands -------------------------------------------------

export interface LatencyBandEntry {
  featureArea: FeatureArea
  p50LatencyMs: number
  p95LatencyMs: number
  p99LatencyMs: number
}

export interface LatencyBands {
  entries: LatencyBandEntry[]
  freshnessAt: string
}

// --- FR-016 Token usage ---------------------------------------------------

export interface TokenUsageRow {
  featureArea: FeatureArea
  promptTokens: number
  completionTokens: number
  totalTokens: number
}

export interface TokenUsageResponse {
  rows: TokenUsageRow[]
  totalTokens: number
  freshnessAt: string
}

// --- FR-016 Cost summary --------------------------------------------------

export interface CostFeatureBreakdown {
  featureArea: FeatureArea
  costUsd: number
  share: number
}

export interface CostSummaryResponse {
  totalCostUsd: number
  byFeature: CostFeatureBreakdown[]
  lastReconciledAt: string
  isEstimate: boolean
  stale: boolean
  freshnessAt: string
}

// --- FR-017 Version selector ----------------------------------------------

export interface VersionDimensionAvailability {
  dimension: VersionDimension
  knownValues: string[]
  unknownCount: number
}

export interface VersionSelectorResponse {
  dimensions: VersionDimensionAvailability[]
  baselineLabel: string
  freshnessAt: string
}

// --- FR-018 AI quality issue (8 link fields) ------------------------------

export type AIQualityIssueStatus =
  | 'open'
  | 'reviewing'
  | 'regressing'
  | 'resolved'
  | 'wont_fix'

export interface AIQualityIssue {
  issueId: string
  title: string
  // 8 FR-018 link fields
  evalVerdict: string
  badcaseId: string
  affectedFeatureArea: FeatureArea
  affectedJourneyStep: string
  owner: string
  status: AIQualityIssueStatus
  recommendedAction: string
  featureAreaDimension: FeatureArea
  // Extra context
  detectedAt: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  freshnessAt: string
  badcaseDetailHref: string
  evalDetailHref: string
}

export interface AIQualityIssueListResponse {
  issues: AIQualityIssue[]
  total: number
  freshnessAt: string
}

// --- FR-019 Cost-quality flag ---------------------------------------------

export interface CostQualityFlag {
  flagged: boolean
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  costDeltaPct: number
  qualityDeltaPct: number
  costPerQualityDeltaUsd: number
  message: string
  linkedModel: string
  linkedPrompt: string
  linkedFeatureArea: FeatureArea
  linkedCohort: string
  windowStart: string
  windowEnd: string
}

// --- FR-020 Eval + badcase summary ----------------------------------------

export interface EvalRunSummary {
  totalRuns: number
  passRate: number
  openRuns: number
}

export interface BadcaseRow {
  badcaseId: string
  featureArea: FeatureArea
  evalVerdict: string
  status: string
  openedAt: string
  owner: string
}

export interface EvalBadcaseSummary {
  evalRunSummary: EvalRunSummary
  openBadcasesCount: number
  recentBadcases: BadcaseRow[]
  freshnessAt: string
}

// --- Re-export CohortSegment for use in AIOperations page (AC-17.3) -------
export type { CohortSegment }
