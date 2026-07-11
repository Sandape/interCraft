// M032 — Resume v2 API client.
//
// 1:1 mirror of `backend/app/modules/resumes_v2/api.py`. Each function
// calls the v2 endpoint and returns a typed promise. Errors throw
// with status code preserved (the shared `@/api/client` throws
// `ApiError` / `ValidationError` / `RateLimitError` / etc., all of
// which carry a `status` field — see `src/api/errors.ts`).
//
// Endpoint shapes (per contracts/01-rest-api.md §1-6):
//   listResumes     GET    /api/v1/v2/resumes
//   getResume       GET    /api/v1/v2/resumes/{id}
//   createResume    POST   /api/v1/v2/resumes        → { resume }
//   updateResume    PUT    /api/v1/v2/resumes/{id}   (If-Match header)
//   deleteResume    DELETE /api/v1/v2/resumes/{id}
//   duplicateResume POST   /api/v1/v2/resumes/{id}/duplicate  → { resume }
//   setSharing      PUT    /api/v1/v2/resumes/{id}/sharing    → { sharing }
//   getStatistics   GET    /api/v1/v2/resumes/{id}/statistics → { statistics }
//   analyzeResume   POST   /api/v1/v2/resumes/{id}/analyze    → { analysis }
//   getAnalysis     GET    /api/v1/v2/resumes/{id}/analysis   → { analysis }
//   renderExport    POST   /api/v1/v2/export/render           → binary
//   getPublicResume GET    /api/v1/v2/public/{username}/{slug} → resume (public)
//   verifyPublicPw  POST   /api/v1/v2/public/{username}/{slug}/verify-password

import { request } from "@/api/client";
import type { ResumeDataV2, TemplateId } from "../schema/data";
import type { MujiThemeId } from "@/modules/resume/renderer/types";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

/** Single resume in a list response (no `data` blob). */
export interface ResumeV2ListItem {
  id: string;
  name: string;
  slug: string;
  tags: string[];
  is_public: boolean;
  is_locked: boolean;
  version: number;
  created_at: string | null;
  updated_at: string | null;
  statistics?: Record<string, number | null> | null;
  /** REQ-055 */
  resume_kind?: "root" | "derived" | "standard";
  job_id?: string | null;
  target_page_count?: number | null;
  actual_page_count?: number | null;
}

/** Full single-resume response including the `data` blob. */
export interface ResumeV2 {
  id: string;
  user_id: string;
  name: string;
  slug: string;
  tags: string[];
  is_public: boolean;
  is_locked: boolean;
  password_set: boolean;
  version: number;
  created_at: string | null;
  updated_at: string | null;
  data: ResumeDataV2;
  /** REQ-055 */
  resume_kind?: "root" | "derived" | "standard";
  root_resume_id?: string | null;
  job_id?: string | null;
  root_version_at_derive?: number | null;
  target_page_count?: number | null;
  actual_page_count?: number | null;
  derive_meta?: Record<string, unknown>;
}

export interface ResumeV2Conflict {
  error: "VERSION_CONFLICT";
  latest_data: ResumeDataV2;
  latest_version: number;
}

export interface ResumeV2Create {
  name: string;
  slug: string;
  template?: TemplateId;
  theme_id?: MujiThemeId;
  from_sample?: boolean;
}

export interface ResumeV2Update {
  name?: string;
  tags?: string[];
  /** Partial sub-tree of `ResumeDataV2`. The backend deep-merges
   *  this into the stored doc; unknown keys are ignored. */
  data?: Partial<ResumeDataV2>;
}

export interface SharingInput {
  is_public: boolean;
  password?: string;
}

export interface SharingResponse {
  is_public: boolean;
  password_set: boolean;
  public_url: string | null;
}

export interface StatisticsResponse {
  views: number;
  downloads: number;
  last_viewed_at: string | null;
  last_downloaded_at: string | null;
}

export interface AnalysisItem {
  /** Stable id from the LLM. Used as React key. */
  id?: string;
  /** High-level category (e.g. "summary", "experience"). */
  category?: string;
  /** The improvement suggestion. */
  suggestion?: string;
  /** Richer resume-v2 analysis text returned by the production backend. */
  text?: string;
  why?: string;
  exampleRewrite?: string;
  /** Severity ranking: high → low. */
  impact: "high" | "medium" | "low";
}

export interface AnalysisDimension {
  name: string;
  score: number;
}

export interface AnalysisResponse {
  status: "success" | "failed";
  analysis: {
    score: number;
    overallScore?: number;
    dimensions?: AnalysisDimension[];
    items: AnalysisItem[];
    strengths?: AnalysisItem[];
    suggestions?: AnalysisItem[];
  } | null;
  failure_reason: string | null;
  updated_at: string;
}

export type ExportFormat = "pdf" | "png" | "jpeg" | "json" | "markdown";

export interface ResumeExportRenderSettings {
  sourceMarkdown?: string;
  themeId?: string;
  lineHeight?: number;
  smartOnePageEnabled?: boolean;
  paginationState?: string;
  pageCount?: number;
  /** REQ-055 hard page gate */
  expectedPageCount?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Unwrap `{ resume: {...} }` envelopes used by duplicate and retained
 *  on create for backward compatibility with older v2 clients/tests. */
function unwrapEnvelope<T>(payload: T | { resume: T }): T {
  if (
    payload !== null &&
    typeof payload === "object" &&
    "resume" in (payload as object)
  ) {
    return (payload as { resume: T }).resume;
  }
  return payload as T;
}

// ─────────────────────────────────────────────────────────────────────────────
// Endpoints
// ─────────────────────────────────────────────────────────────────────────────

export async function listResumes(params?: {
  search?: string;
  tags?: string[];
  is_public?: boolean;
  sort?: "updated" | "created" | "name";
  kind?: "root" | "derived" | "standard" | "all";
}): Promise<ResumeV2ListItem[]> {
  const query: Record<string, string | number | boolean | undefined> = {};
  if (params?.search) query.search = params.search;
  if (params?.tags && params.tags.length) query.tags = params.tags.join(",");
  if (params?.is_public !== undefined) query.is_public = params.is_public;
  if (params?.sort) query.sort = params.sort;
  if (params?.kind) query.kind = params.kind;
  const res = await request<{ data: ResumeV2ListItem[] }>({
    method: "GET",
    path: "/api/v1/v2/resumes",
    query,
  });
  return res.data;
}

export async function getResume(id: string): Promise<ResumeV2> {
  return request<ResumeV2>({
    method: "GET",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}`,
  });
}

export async function createResume(payload: ResumeV2Create): Promise<ResumeV2> {
  const res = await request<ResumeV2 | { resume: ResumeV2 }>({
    method: "POST",
    path: "/api/v1/v2/resumes",
    body: payload,
  });
  return unwrapEnvelope(res);
}

export async function updateResume(
  id: string,
  payload: ResumeV2Update,
  version: number,
): Promise<ResumeV2 | ResumeV2Conflict> {
  // The If-Match header is mandatory for v2 PUT (REQ-019 / optimistic
  // concurrency). Use the shared request() client so 401 responses
  // benefit from the silent-refresh-then-retry envelope (BUG #2 fix
  // 2026-07-06). The `headers` option merges AFTER the standard
  // envelope so `If-Match` and any future headers are honored.
  return request<ResumeV2 | ResumeV2Conflict>({
    method: "PUT",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}`,
    body: payload,
    headers: {
      "If-Match": String(version),
    },
  });
}

export async function deleteResume(id: string): Promise<void> {
  await request<void>({
    method: "DELETE",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}`,
  });
}

export async function duplicateResume(id: string): Promise<ResumeV2> {
  const res = await request<ResumeV2 | { resume: ResumeV2 }>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}/duplicate`,
  });
  return unwrapEnvelope(res);
}

export async function setSharing(
  id: string,
  payload: SharingInput,
): Promise<SharingResponse> {
  return request<SharingResponse>({
    method: "PUT",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}/sharing`,
    body: payload,
  });
}

export async function getStatistics(id: string): Promise<StatisticsResponse> {
  return request<StatisticsResponse>({
    method: "GET",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}/statistics`,
  });
}

export async function analyzeResume(id: string): Promise<AnalysisResponse> {
  return request<AnalysisResponse>({
    method: "POST",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}/analyze`,
  });
}

export async function getAnalysis(id: string): Promise<AnalysisResponse> {
  return request<AnalysisResponse>({
    method: "GET",
    path: `/api/v1/v2/resumes/${encodeURIComponent(id)}/analysis`,
  });
}

export async function renderExport(
  id: string,
  format: ExportFormat,
  /**
   * Batch 3 (REQ-032 v2) — Optional rendered HTML payload. The
   * backend `POST /api/v1/v2/export/render` requires non-empty `html`
   * for PDF / PNG / JPEG (it returns 400 EMPTY_CONTENT otherwise).
   * Callers that have the current store data should render the live
   * preview pane to HTML and pass it here so the PDF reflects the
   * user's unsaved local edits. JSON exports ignore this field.
   */
  html?: string,
  settings?: ResumeExportRenderSettings,
): Promise<Blob> {
  // Export returns binary (PDF / PNG / JPEG). We use the shared
  // `request()` client with `raw: true` so 401 responses benefit from
  // silent-refresh (BUG #2 fix 2026-07-06) and the response body stays
  // as a `Response` we can `.blob()` from. The shared envelope's
  // 422/429/401-classification still applies before we hand the body
  // back to the caller.
  const body: Record<string, unknown> = { resume_id: id, format };
  if (html) body.html = html;
  if (settings?.sourceMarkdown !== undefined) body.source_markdown = settings.sourceMarkdown;
  if (settings?.themeId !== undefined) body.theme_id = settings.themeId;
  if (settings?.lineHeight !== undefined) body.line_height = settings.lineHeight;
  if (settings?.smartOnePageEnabled !== undefined) body.smart_one_page_enabled = settings.smartOnePageEnabled;
  if (settings?.paginationState !== undefined) body.pagination_state = settings.paginationState;
  if (settings?.pageCount !== undefined) body.preview_page_count = settings.pageCount;
  if (settings?.expectedPageCount !== undefined) {
    body.expected_page_count = settings.expectedPageCount;
  }
  const res = await request<Response>({
    method: "POST",
    path: "/api/v1/v2/export/render",
    body,
    raw: true,
  });
  return res.blob();
}

// ─────────────────────────────────────────────────────────────────────────────
// Public resume endpoints (Batch 3 — REQ-032 v2).
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Response shape of `GET /api/v1/v2/public/{username}/{slug}`.
 * Mirrors the regular ResumeV2 envelope — public callers see the full
 * `data` blob so the page can render via the same `PreviewPane`.
 */
export interface PublicResumeV2 {
  id: string;
  username: string;
  name: string;
  slug: string;
  /** Always true on this endpoint (the route returns 404 otherwise). */
  is_public: boolean;
  /** True when a password is required to view; the page will then
   *  render the password form before fetching the body. */
  password_set: boolean;
  version: number;
  updated_at: string | null;
  /** Full template data — same shape as `ResumeDataV2`. May be `null`
   *  when the resume is password-protected and the caller hasn't yet
   *  presented the cookie. The route returns 401 in that case. */
  data: ResumeDataV2 | null;
}

/**
 * Fetch a public resume by owner username + slug. Returns the full
 * resume document including the `data` template blob. Throws the
 * shared `ApiError` family on non-2xx — `status === 401` means a
 * password is required, `status === 404` means the slug is unknown or
 * the resume isn't public.
 */
export async function getPublicResume(
  username: string,
  slug: string,
): Promise<PublicResumeV2> {
  return request<PublicResumeV2>({
    method: "GET",
    path: `/api/v1/v2/public/${encodeURIComponent(username)}/${encodeURIComponent(slug)}`,
    skipAuth: true,
  });
}

/**
 * POST `{password}` to the password-unlock endpoint. On success the
 * backend sets an HttpOnly cookie (`v2_public_pw_<hash>`) that the
 * browser will replay on subsequent `getPublicResume` calls. The
 * response itself is `{ ok: true }` — we don't return any data; the
 * caller should refetch via `getPublicResume`.
 */
export async function verifyPublicPassword(
  username: string,
  slug: string,
  password: string,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>({
    method: "POST",
    path: `/api/v1/v2/public/${encodeURIComponent(username)}/${encodeURIComponent(slug)}/verify-password`,
    body: { password },
    skipAuth: true,
  });
}
