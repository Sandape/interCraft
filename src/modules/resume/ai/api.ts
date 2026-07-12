import { request } from "@/api/client";
import type {
  AnalysisMode,
  FeedbackCategory,
  ResumeAnalysis,
  ResumeAnalysisComparison,
  ResumeSuggestion,
  RunStatus,
  SupplementConfirmationInput,
  SuggestionStatus,
} from "./types";

/** REQ-061 US3 — canonical runtime fields on intelligence start/status. */
export interface ResumeAIRuntimeLinks {
  task_id: string | null;
  status_url: string;
  events_url: string | null;
}

export interface ResumeAIMilestone {
  code: string;
  status: string;
  settle_eligible?: boolean;
}

export interface AnalysisRunAccepted {
  run_id: string;
  analysis_id?: string | null;
  status: "queued" | "running" | string;
  status_url: string;
  idempotent_replay?: boolean;
  task_id?: string | null;
  execution_id?: string | null;
  task_version?: number;
  canonical_status?: string;
  available_actions?: string[];
  milestones?: ResumeAIMilestone[];
  point_summary?: {
    quoted_max?: number;
    reserved?: number;
    settled?: number;
    released?: number;
    settlement_status?: string;
  } | null;
  acceptance?: Record<string, unknown> | null;
  runtime?: ResumeAIRuntimeLinks;
}

export interface AnalysisRunStatus {
  run_id: string;
  analysis_id: string | null;
  status: RunStatus;
  phase: string;
  progress_percent?: number;
  components?: Record<string, "pending" | "running" | "succeeded" | "failed" | "skipped">;
  retryable_components?: string[];
  error: { code?: string; message?: string; retryable?: boolean } | null;
  created_at?: string;
  finished_at?: string | null;
  task_id?: string | null;
  task_version?: number;
  canonical_status?: string;
  available_actions?: string[];
  milestones?: ResumeAIMilestone[];
  point_summary?: AnalysisRunAccepted["point_summary"];
  acceptance?: Record<string, unknown> | null;
  runtime?: ResumeAIRuntimeLinks;
}

export interface SuggestionPreview {
  preview_token: string | null;
  base_resume_version: number;
  compatible: string[];
  conflicts: Array<{ suggestion_ids: string[]; code: string; message: string }>;
  blocked: Array<{ suggestion_ids: string[]; code: string; message: string }>;
  diff: {
    before_markdown: string;
    after_markdown: string;
    patches: Array<{ op: string; path: string; value?: unknown }>;
  } | null;
  page_impact: { status: string; export_gate_stale: boolean };
  evidence?: Record<string, unknown> | null;
}

export interface ApplyResult {
  resume: { id: string; version: number; data: Record<string, unknown> };
  change_set_id: string;
  applied_suggestion_ids: string[];
  analysis_stale: boolean;
  export_gate_stale: boolean;
  evidence?: Record<string, unknown> | null;
  base_resume_version?: number;
  result_resume_version?: number;
}

export function startAnalysis(
  resumeId: string,
  body: { mode: AnalysisMode; client_version: number; job_id?: string | null; force?: boolean },
) {
  return request<AnalysisRunAccepted>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/intelligence-runs`,
    body,
  });
}

export function getAnalysisRun(runId: string) {
  return request<AnalysisRunStatus>({
    method: "GET",
    path: `/api/v1/v2/resume-intelligence/runs/${encodeURIComponent(runId)}`,
  });
}

export function cancelRun(runId: string) {
  return request<AnalysisRunStatus>({
    method: "POST",
    path: `/api/v1/v2/resume-intelligence/runs/${encodeURIComponent(runId)}/cancel`,
  });
}

export async function listAnalyses(resumeId: string, mode: AnalysisMode) {
  const result = await request<{ items: ResumeAnalysis[] }>({
    method: "GET",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/analyses`,
    query: { mode },
  });
  return result.items;
}

export async function listSuggestions(
  resumeId: string,
  analysisId: string,
  status?: SuggestionStatus[],
) {
  // Prefer analysis-scoped route to avoid collision with legacy derive
  // GET /v2/resumes/{id}/suggestions (derive_meta suggestions).
  void resumeId;
  const result = await request<{ items?: ResumeSuggestion[]; suggestions?: ResumeSuggestion[] }>({
    method: "GET",
    path: `/api/v1/v2/analyses/${encodeURIComponent(analysisId)}/suggestions`,
    query: {
      status: status && status.length > 0 ? status.join(",") : undefined,
    },
  });
  return result.items ?? result.suggestions ?? [];
}

export function regenerateSuggestions(analysisId: string, idempotencyKey: string) {
  return request<AnalysisRunAccepted>({
    method: "POST",
    path: `/api/v1/v2/analyses/${encodeURIComponent(analysisId)}/suggestions/regenerate`,
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export function updateSuggestionStatus(
  suggestionId: string,
  body: { action: "ignore" | "defer" | "reopen"; reason?: string | null },
) {
  return request<ResumeSuggestion>({
    method: "POST",
    path: `/api/v1/v2/suggestions/${encodeURIComponent(suggestionId)}/status`,
    body,
  });
}

export function previewSuggestions(
  resumeId: string,
  body: { analysis_id: string; suggestion_ids: string[]; client_version: number },
) {
  return request<SuggestionPreview>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/suggestions/preview-batch`,
    body,
  });
}

export function applySuggestions(
  resumeId: string,
  body: { preview_token: string; client_version: number },
  idempotencyKey: string,
) {
  return request<ApplyResult>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/suggestions/apply-batch`,
    headers: { "Idempotency-Key": idempotencyKey },
    body,
  });
}

export function undoChangeSet(changeSetId: string, clientVersion: number, idempotencyKey: string) {
  return request<ApplyResult>({
    method: "POST",
    path: `/api/v1/v2/suggestion-change-sets/${encodeURIComponent(changeSetId)}/undo`,
    headers: { "Idempotency-Key": idempotencyKey },
    body: { client_version: clientVersion },
  });
}

export function submitFeedback(body: {
  analysis_id: string;
  suggestion_id?: string | null;
  change_set_id?: string | null;
  category: FeedbackCategory;
  comment?: string | null;
}) {
  return request<{ id?: string; feedback_id?: string }>({
    method: "POST",
    path: "/api/v1/v2/resume-intelligence/feedback",
    body,
  });
}

export function compareAnalyses(beforeAnalysisId: string, afterAnalysisId: string) {
  return request<ResumeAnalysisComparison>({
    method: "GET",
    path: `/api/v1/v2/analyses/${encodeURIComponent(beforeAnalysisId)}/compare`,
    query: { target_analysis_id: afterAnalysisId },
  });
}

export function refreshAnalysis(analysisId: string) {
  return request<AnalysisRunAccepted>({
    method: "POST",
    path: `/api/v1/v2/analyses/${encodeURIComponent(analysisId)}/refresh`,
  });
}

export function confirmSupplementFact(body: SupplementConfirmationInput) {
  return request<{ ok: boolean; stale_analysis?: boolean; root_updated?: boolean }>({
    method: "POST",
    path: "/api/v1/v2/resume-intelligence/supplements/confirm",
    body,
  });
}
