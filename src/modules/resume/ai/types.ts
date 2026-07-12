export type AnalysisMode = "general" | "job_fit";

export type ConfidenceBand = "low" | "medium" | "high";

export type GapCoverage =
  | "covered"
  | "weak"
  | "evidence_not_shown"
  | "missing_evidence"
  | "real_gap"
  | "unknown";

export type SuggestionStatus =
  | "open"
  | "previewed"
  | "applied"
  | "ignored"
  | "deferred"
  | "stale"
  | "conflict"
  | "withdrawn"
  | "undone";

export type RunStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "partial_success"
  | "needs_guidance"
  | "canceling"
  | "cancelled"
  | "failed"
  | "complete"
  | "partial";

export type FeedbackCategory =
  | "helpful"
  | "not_applicable"
  | "repeated"
  | "poor_wording"
  | "fact_error"
  | "other";

export type SupplementScope = "derived_only" | "root" | "discard";

export interface JobContext {
  job_id: string | null;
  company: string | null;
  position: string;
  jd_hash: string;
  refreshable: boolean;
}

export interface AnalysisDimension {
  key:
    | "hard_requirements"
    | "experience_evidence"
    | "skills_keywords"
    | "outcomes_quantification"
    | "responsibility_relevance"
    | "expression_readability";
  weight: number;
  score: number;
  explanation: string;
  requirement_ids: string[];
}

export interface SourceRef {
  source_id: string;
  source_type: "root_resume" | "current_resume" | "confirmed_supplement";
  anchor: string;
  excerpt: string | null;
  content_hash: string;
}

export interface AnalysisGap {
  id: string;
  requirement_excerpt: string;
  priority: "hard" | "important" | "nice";
  coverage: GapCoverage;
  confidence: number;
  explanation: string;
  evidence_refs: SourceRef[];
  recommended_action: string;
  can_rewrite: boolean;
  needs_supplement: boolean;
  must_not_claim: boolean;
}

export interface ResumeAnalysis {
  id: string;
  resume_id: string;
  resume_version: number;
  mode: AnalysisMode;
  status: "queued" | "running" | "complete" | "partial" | "failed" | "cancelled";
  is_stale: boolean;
  stale_reasons: string[];
  overall_score: number | null;
  confidence_score: number | null;
  confidence_band: ConfidenceBand | null;
  confidence_reasons: string[];
  job_context: JobContext | null;
  dimensions: AnalysisDimension[];
  gaps: AnalysisGap[];
  hard_blockers: string[];
  disclaimer: string;
  scoring_version?: string;
  prompt_version?: string;
  schema_version?: string;
  created_at: string;
}

export interface ResumeAnalysisComparison {
  before_analysis_id: string;
  after_analysis_id: string;
  overall_delta: number | null;
  dimension_deltas: Array<{
    key: AnalysisDimension["key"];
    before_score: number | null;
    after_score: number | null;
    delta: number | null;
  }>;
  resolved_gaps: AnalysisGap[];
  new_gaps: AnalysisGap[];
  unchanged_gaps: AnalysisGap[];
}

export interface SuggestionAnchor {
  node_id: string;
  start: number;
  end: number;
  context_checksum: string;
}

export interface PageImpact {
  status: "unchanged" | "may_expand" | "may_shrink" | "needs_measurement" | string;
  estimated_delta_lines?: number | null;
  export_gate_stale?: boolean;
}

export interface ResumeSuggestion {
  id: string;
  analysis_id: string;
  base_resume_version: number;
  kind: "rewrite" | "add_evidence" | "quantify" | "reorder" | "remove" | "manual_review";
  action_mode: "direct" | "needs_supplement" | "needs_judgment" | "do_not_write";
  priority: "high" | "medium" | "low";
  title: string;
  explanation: string;
  anchor: SuggestionAnchor;
  requirement_refs?: string[];
  page_impact?: PageImpact;
  status_reason?: string | null;
  status: SuggestionStatus;
  source_refs: SourceRef[];
}

export interface SupplementQuestion {
  id: string;
  suggestion_id: string;
  prompt: string;
  experience_anchor?: string | null;
  requirement_excerpt?: string | null;
  impact_summary?: string | null;
  answer?: string;
}

export interface SupplementConfirmationInput {
  suggestion_id: string;
  question_id?: string;
  answer: string;
  scope: SupplementScope;
}
