/** REQ-055 / REQ-061 derive API client */
import { request } from "@/api/client";

export type ResumeKind = "root" | "derived" | "standard";

export interface DeriveMilestone {
  code: string;
  status: string;
  settle_eligible?: boolean;
}

export interface DeriveRuntimeLinks {
  task_id: string | null;
  status_url: string;
  events_url: string | null;
}

export interface DeriveRunAccepted {
  run_id: string;
  status: string;
  task_id?: string | null;
  execution_id?: string | null;
  canonical_status?: string;
  available_actions?: string[];
  milestones?: DeriveMilestone[];
  acceptance?: Record<string, unknown> | null;
  runtime?: DeriveRuntimeLinks;
}

export interface DeriveRun {
  id: string;
  status: string;
  phase: string;
  progress_pct: number;
  derived_resume_id: string | null;
  target_page_count: number;
  error_code: string | null;
  error_message: string | null;
  artifacts: Record<string, unknown>;
  component_status?: Record<string, string>;
  canonical_status?: string;
  available_actions?: string[];
  milestones?: DeriveMilestone[];
  task_id?: string | null;
  acceptance?: Record<string, unknown> | null;
  runtime?: DeriveRuntimeLinks;
  settlement?: {
    chargeable_milestone_codes: string[];
    delivered_milestones: string[];
    failed_milestones: string[];
    pending_milestones: string[];
  };
}

export interface ExportGate {
  exportable: boolean;
  actual_page_count: number | null;
  target_page_count: number | null;
  blockers: string[];
}

export async function getRootResume() {
  return request<Record<string, unknown>>({
    method: "GET",
    path: "/api/v1/v2/resumes/root",
  });
}

export async function createRootResume(body: {
  name: string;
  slug: string;
  data?: Record<string, unknown>;
}) {
  return request<Record<string, unknown>>({
    method: "POST",
    path: "/api/v1/v2/resumes/root",
    body,
  });
}

export async function promoteToRoot(resumeId: string) {
  return request<Record<string, unknown>>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/promote-root`,
  });
}

export async function startDerive(body: {
  job_id: string;
  target_page_count: 1 | 2 | 3;
  template_id?: string;
  root_resume_id?: string;
}) {
  return request<DeriveRunAccepted>({
    method: "POST",
    path: "/api/v1/v2/resumes/derive",
    body,
  });
}

export async function getDeriveRun(runId: string) {
  return request<DeriveRun>({
    method: "GET",
    path: `/api/v1/v2/resumes/derive-runs/${encodeURIComponent(runId)}`,
  });
}

export async function cancelDeriveRun(runId: string) {
  return request<DeriveRun>({
    method: "POST",
    path: `/api/v1/v2/resumes/derive-runs/${encodeURIComponent(runId)}`,
  });
}

export async function getExportGate(resumeId: string) {
  return request<ExportGate>({
    method: "GET",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/export-gate`,
  });
}

export interface DeriveRationale {
  takeaway_notes: string[];
  selection_plan: Record<string, unknown>;
  unused_materials: unknown[];
  jd_parse: Record<string, unknown>;
  supplement_questions: SupplementQuestion[];
  pending_claims: PendingClaim[];
}

export interface SupplementQuestion {
  question_id: string;
  text: string;
  apply_mode?: string;
}

export interface PendingClaim {
  question_id?: string;
  reason?: string;
}

export interface SuggestionPreview {
  suggestion_id: string;
  apply_mode: string;
  preview_data: Record<string, unknown>;
  diff_summary: string;
  preview_token: string;
}

export async function getDeriveRationale(resumeId: string) {
  return request<DeriveRationale>({
    method: "GET",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/derive-rationale`,
  });
}

export async function previewSuggestion(
  resumeId: string,
  body: { suggestion_id: string; client_version?: number },
) {
  return request<SuggestionPreview>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/suggestions/preview`,
    body,
  });
}

export async function applySuggestion(
  resumeId: string,
  body: {
    suggestion_id: string;
    client_version?: number;
    preview_token?: string;
  },
) {
  return request<Record<string, unknown>>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/suggestions/apply`,
    body: {
      suggestion_id: body.suggestion_id,
      client_version: body.client_version,
      preview_token: body.preview_token,
    },
  });
}

export async function postSupplements(
  resumeId: string,
  body: {
    answers: Array<{ question_id: string; text: string }>;
    sync_target: "derived_only" | "root" | "discard";
  },
) {
  return request<Record<string, unknown>>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/supplements`,
    body,
  });
}

export async function resumeGuidance(
  runId: string,
  body: {
    action: string;
    template_id?: string;
    target_page_count?: 1 | 2 | 3;
    hide_module_ids?: string[];
  },
) {
  return request<DeriveRunAccepted>({
    method: "POST",
    path: `/api/v1/v2/resumes/derive-runs/${encodeURIComponent(runId)}/resume-guidance`,
    body,
  });
}

export async function listSuggestions(resumeId: string) {
  return request<{ suggestions: Array<Record<string, unknown>> }>({
    method: "GET",
    path: `/api/v1/v2/resumes/${encodeURIComponent(resumeId)}/suggestions`,
  });
}

export async function listJobDerivedResumes(jobId: string) {
  return request<{ data: Array<Record<string, unknown>> }>({
    method: "GET",
    path: `/api/v1/jobs/${encodeURIComponent(jobId)}/derived-resumes`,
  });
}
