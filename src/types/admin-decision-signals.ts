/**
 * Admin Console Command Center / Decision Signal types — REQ-044 US1.
 *
 * Mirrors backend/app/modules/admin_console/decision_signals/schemas.py.
 *
 * The 10 DecisionSignal fields are the literal source-of-truth set
 * required by FR-008 + FR-009 + FR-018:
 *
 *   1. id
 *   2. category
 *   3. what_changed
 *   4. affected_segment
 *   5. comparison_baseline
 *   6. severity
 *   7. confidence
 *   8. owner
 *   9. freshness_at
 *  10. next_review_link
 *
 * Plus the auxiliary ``evidence_links`` array (FR-018), the
 * ``quality_flags`` object (FR-028), and the sort key fields
 * ``priority`` + ``detected_at`` + ``headline_metric_id``.
 *
 * [CROSS-TEAM-DEBT] The 4 confidence tiers + 6 categories must stay
 * in lockstep with backend Pydantic Literals. If you add a new tier
 * here, also add it to ``schemas.py`` DecisionSignal.confidence.
 */

// --- FR-007 6 categories --------------------------------------------------

export type DecisionSignalCategory =
  | 'product'
  | 'ai-quality'
  | 'ai-cost'
  | 'system-health'
  | 'incident'
  | 'data-quality'

// --- FR-009 4 confidence tiers --------------------------------------------

export type DecisionConfidenceTier =
  | 'confirmed'
  | 'sampled'
  | 'inferred'
  | 'candidate'

// --- Severity bands -------------------------------------------------------

export type DecisionSignalSeverity =
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | 'info'

// --- Evidence link --------------------------------------------------------

export type EvidenceLinkKind =
  | 'review'
  | 'eval'
  | 'badcase'
  | 'log'
  | 'trace'
  | 'metric'
  | 'report'

export type EvidencePrivacyClass = 'public' | 'internal' | 'restricted'

export interface EvidenceLink {
  label: string
  href: string
  kind: EvidenceLinkKind
  privacyClass: EvidencePrivacyClass
}

// --- Quality flags (FR-028) -----------------------------------------------

export interface SignalQualityFlags {
  stale: boolean
  partialBaseline: boolean
  delayedIngestion: boolean
  missingVersionFields: string[]
  sampledData: boolean
  partialData: boolean
  noData: boolean
}

// --- The 10-field DecisionSignal -----------------------------------------

export interface DecisionSignal {
  id: string
  category: DecisionSignalCategory
  whatChanged: string
  affectedSegment: string
  comparisonBaseline: string
  severity: DecisionSignalSeverity
  confidence: DecisionConfidenceTier
  owner: string
  freshnessAt: string
  nextReviewLink: string
  evidenceLinks: EvidenceLink[]
  qualityFlags: SignalQualityFlags
  priority: number
  detectedAt: string
  headlineMetricId: string | null
  title: string
}

// --- List response envelope -----------------------------------------------

export interface DecisionSignalListResponse {
  signals: DecisionSignal[]
  total: number
  highSeverityCount: number
  quietSteadyState: boolean
  freshnessAt: string
  lastReviewedAt: string
  openReviews: number
}

// --- 4 KPI tiles (overview) ----------------------------------------------

export interface CommandCenterOverview {
  productHealth: number
  productHealthUnit: string
  aiQuality: number
  aiQualityUnit: string
  aiCost: number
  aiCostUnit: string
  systemHealth: number
  systemHealthUnit: string
  freshnessAt: string
}

export interface CommandCenterOverviewResponse {
  overview: CommandCenterOverview
  freshnessAt: string
}