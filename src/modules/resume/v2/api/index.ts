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

import { request } from "@/api/client";
import type { ResumeDataV2, TemplateId } from "../schema/data";

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
}

export interface ResumeV2Create {
  name: string;
  slug: string;
  template?: TemplateId;
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
  id: string;
  /** High-level category (e.g. "summary", "experience"). */
  category: string;
  /** The improvement suggestion. */
  suggestion: string;
  /** Severity ranking: high → low. */
  impact: "high" | "medium" | "low";
}

export interface AnalysisResponse {
  status: "success" | "failed";
  analysis: {
    score: number;
    items: AnalysisItem[];
  } | null;
  failure_reason: string | null;
  updated_at: string;
}

export type ExportFormat = "pdf" | "png" | "jpeg" | "json";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Strip the `/api/v1` prefix from a stored resume data blob so callers
 *  can re-hydrate the editor store. The backend sometimes wraps the
 *  create / duplicate response as `{ resume: {...} }` per the in-flight
 *  frontend contract — this helper unwraps that shape. */
function unwrapEnvelope<T>(payload: T | { resume: T }): T {
  if (
    payload !== null &&
    typeof payload === "object" &&
    "resume" in (payload as object)
  ) {
    return (payload as { resume: T }).resume;
  }
  return payload;
}

// ─────────────────────────────────────────────────────────────────────────────
// Endpoints
// ─────────────────────────────────────────────────────────────────────────────

export async function listResumes(params?: {
  search?: string;
  tags?: string[];
  is_public?: boolean;
  sort?: "updated" | "created" | "name";
}): Promise<ResumeV2ListItem[]> {
  const query: Record<string, string | number | boolean | undefined> = {};
  if (params?.search) query.search = params.search;
  if (params?.tags && params.tags.length) query.tags = params.tags.join(",");
  if (params?.is_public !== undefined) query.is_public = params.is_public;
  if (params?.sort) query.sort = params.sort;
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
): Promise<ResumeV2> {
  // The If-Match header is mandatory for v2 PUT (REQ-019 / optimistic
  // concurrency). The shared `request()` helper does not expose a
  // `headers` option, so we go through `fetch` directly with the same
  // auth / request-id envelope. Errors are re-thrown as the shared
  // helper would so callers see consistent error shapes.
  const { env } = await import("@/api/env");
  const { getAccessToken } = await import("@/api/token-storage");
  const { newRequestId } = await import("@/api/env");
  const { deviceFingerprint } = await import("@/api/device-fingerprint");
  const { classifyBackendError } = await import("@/api/errors");

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
    "X-Request-ID": newRequestId(),
    "X-Device-Fingerprint": deviceFingerprint(),
    "If-Match": String(version),
  };
  const access = getAccessToken();
  if (access) headers["Authorization"] = `Bearer ${access}`;

  const url = `${env.API_BASE_URL}/api/v1/v2/resumes/${encodeURIComponent(id)}`;
  const res = await fetch(url, {
    method: "PUT",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw classifyBackendError(res.status, body, headers["X-Request-ID"]);
  }
  return (await res.json()) as ResumeV2;
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
): Promise<Blob> {
  // Export returns binary (PDF / PNG / JPEG) so we bypass the JSON
  // helper and use raw fetch to preserve the response body as a Blob.
  const { env } = await import("@/api/env");
  const { getAccessToken } = await import("@/api/token-storage");
  const { newRequestId } = await import("@/api/env");
  const { deviceFingerprint } = await import("@/api/device-fingerprint");
  const { classifyBackendError } = await import("@/api/errors");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-ID": newRequestId(),
    "X-Device-Fingerprint": deviceFingerprint(),
  };
  const access = getAccessToken();
  if (access) headers["Authorization"] = `Bearer ${access}`;

  const url = `${env.API_BASE_URL}/api/v1/v2/export/render`;
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({ resume_id: id, format }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw classifyBackendError(res.status, body, headers["X-Request-ID"]);
  }
  return res.blob();
}