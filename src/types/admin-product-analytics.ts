/**
 * Admin Console / Product Analytics types — REQ-044 US2.
 *
 * Mirrors backend/app/modules/admin_console/product_analytics/schemas.py.
 *
 * [CROSS-TEAM-DEBT] Phase 2 batch 2 will replace the seed-driven funnel
 * / cohort / adoption rows with real metric snapshots from the
 * pm_dashboard 6 panels. The TypeScript surface (this file) must
 * remain in lockstep with the backend Pydantic Literals.
 *
 * Privacy guard (FR-032): UserPrivacySafeField "name" union MUST NOT
 * include raw_resume / raw_interview_answer / raw_prompt /
 * raw_model_output. AC-15.4 grep gate verifies this on the frontend
 * page that renders the field set.
 */

// --- FR-011 7 question tabs ------------------------------------------------

export type QuestionTab =
  | 'activation'
  | 'funnel'
  | 'retention'
  | 'adoption'
  | 'journey'
  | 'release'
  | 'experiment'

// --- FR-011 QuestionTemplate ----------------------------------------------

export interface QuestionTemplate {
  templateId: string
  tab: QuestionTab
  title: string
  description: string
  requiredCohortId: string | null
  requiredPeriodDays: number
  metricId: string
  owner: string
  freshnessAt: string
}

export interface QuestionTemplateListResponse {
  templates: QuestionTemplate[]
  total: number
  freshnessAt: string
}

// --- FR-012 Funnel ---------------------------------------------------------

export interface FunnelStep {
  stepName: string
  count: number
  stepConversion: number | null
  dropOff: number | null
}

export interface TimeToConvertBand {
  p50Seconds: number
  ci95LowerSeconds: number
  ci95UpperSeconds: number
  sampleSize: number
}

export interface FunnelComparisonDelta {
  comparisonPeriodLabel: string
  stepConversionDelta: number
}

export interface FunnelResponse {
  funnelId: string
  steps: FunnelStep[]
  entryConversion: number
  comparisonDelta: FunnelComparisonDelta | null
  timeToConvert: TimeToConvertBand | null
  cohortId: string | null
  cohortPopulation: number
  lastComputedAt: string
  freshnessAt: string
}

// --- FR-013 Cohort ---------------------------------------------------------

export interface CohortSegment {
  id: string
  name: string
  definition: string
  population: number
  owner: string
  lastComputedAt: string
  stale: boolean
}

export interface CohortListResponse {
  cohorts: CohortSegment[]
  total: number
  freshnessAt: string
}

// --- FR-014 Feature Adoption ----------------------------------------------

export type FeatureAdoptionMetricName =
  | 'discovery_users'
  | 'first_use_users'
  | 'repeat_users'
  | 'frequency_avg'
  | 'downstream_success_rate'

export interface FeatureAdoptionMetric {
  metricName: FeatureAdoptionMetricName
  currentValue: number
  unit: string
  comparisonDelta: number
  sampleSize: number
  insufficientData: boolean
}

export interface FeatureAdoptionRow {
  featureId: string
  featureName: string
  metrics: [FeatureAdoptionMetric, FeatureAdoptionMetric, FeatureAdoptionMetric, FeatureAdoptionMetric, FeatureAdoptionMetric]
  cohortId: string | null
  cohortPopulation: number
  lastComputedAt: string
  freshnessAt: string
}

export interface FeatureAdoptionResponse {
  features: FeatureAdoptionRow[]
  total: number
  freshnessAt: string
}

// --- FR-015 User Privacy-Safe ---------------------------------------------

export type UserVisibilityLevel = 'full' | 'masked' | 'hidden'

// ALLOW-LIST: only these 7 field names are exposed. Adding a new
// field requires updating both this union AND the backend Pydantic
// Literal — and is gated by the AC-15.4 privacy grep.
export type UserPrivacySafeFieldName =
  | 'email'
  | 'role'
  | 'journey_summary'
  | 'incidents_count'
  | 'quality_score'
  | 'created_at'
  | 'last_active_at'

export interface UserPrivacySafeField {
  name: UserPrivacySafeFieldName
  visibility: UserVisibilityLevel
  value: string | null
}

export interface UserPrivacySafe {
  userId: string
  fields: UserPrivacySafeField[]
  cohortPopulation: number
  lastComputedAt: string
  freshnessAt: string
}