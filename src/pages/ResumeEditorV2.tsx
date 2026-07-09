/**
 * ResumeEditorV2 — entry point for the v2 editor.
 *
 * US1 (T028) shipped a read-only placeholder. US2 (T048) wires the
 * Template Gallery + a minimal preview via `PreviewTest`. US3 (T057)
 * wires the full `BuilderShell` (3-column resizable layout) backed
 * by a TanStack Query fetch + a minimal Zustand store.
 *
 * The full auto-save + SSE sync lands in US12 (T112–T120). For now,
 * edits flow through the store but are NOT persisted to the server.
 *
 * Legacy rows now open through Markdown. If an older backend still returns
 * LEGACY_FORMAT, the page surfaces a retry-only migration state instead of
 * linking back to the retired structured editor.
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BuilderShell } from "@/modules/resume/v2/editor/BuilderShell";
import { useResumeV2Store } from "@/modules/resume/v2/store";
import { useResumeSse } from "@/modules/resume/v2/hooks/useResumeSse";
import { getResume, type ResumeV2 } from "@/modules/resume/v2/api";
import type { ResumeDataV2 } from "@/modules/resume/v2/schema/data";
import { defaultResumeDataV2 } from "@/modules/resume/v2/schema/defaults";
import { fireToast } from "@/modules/resume/v2/editor/center/toast";
import { convertLegacyResumeToMarkdown } from "@/modules/resume/converter";

export default function ResumeEditorV2() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const resetFromServer = useResumeV2Store((s) => s.resetFromServer);
  const setData = useResumeV2Store((s) => s.setData);
  const storeData = useResumeV2Store((s) => s.data);
  const lastSavedAt = useResumeV2Store((s) => s.lastSavedAt);
  const queryClient = useQueryClient();

  // Track 404 / 403 / stale 400-LEGACY_FORMAT explicitly because the shared
  // `request()` throws a generic Error — the body shape (status code)
  // is on the underlying Response but `request()` does not surface it.
  // We re-implement the fetch with explicit status checks below to
  // keep the editor accurate.
  const [notFound, setNotFound] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [legacy, setLegacy] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["resume-v2", id],
    queryFn: async () => {
      try {
        const r = await getResume(id!);
        return r;
      } catch (e) {
        // Best-effort status sniffing: the wrapped `request()` throws
        // on any non-2xx, but for 404/403/400-LEGACY we need the status.
        // We re-fetch with explicit status checks via the raw API.
        const { env } = await import("@/api/env");
        const { getAccessToken } = await import("@/api/token-storage");
        const headers: Record<string, string> = { Accept: "application/json" };
        const access = getAccessToken();
        if (access) headers["Authorization"] = `Bearer ${access}`;
        const res = await fetch(`${env.API_BASE_URL}/api/v1/v2/resumes/${id}`, { headers });
        if (res.status === 404) {
          setNotFound(true);
          throw new Error("Resume not found");
        }
        if (res.status === 403) {
          setForbidden(true);
          throw new Error("Forbidden");
        }
        if (res.status === 400) {
          // T126 — peek at the body for LEGACY_FORMAT. The 027 gateway
          // returns `{ error, message }` envelopes; we read the body
          // once and surface the message + banner.
          let body: { error?: string; message?: string } = {};
          try {
            body = (await res.json()) as { error?: string; message?: string };
          } catch {
            /* swallow — body may be empty */
          }
          if (body.error === "LEGACY_FORMAT") {
            setLegacy(body.message ?? "This resume needs Markdown migration before it can open.");
            fireToast("This resume needs Markdown migration before it can open.");
            throw new Error("LEGACY_FORMAT");
          }
        }
        throw e;
      }
    },
    enabled: !!id,
    retry: false,
  });

  useEffect(() => {
    if (query.data) {
      const serverData = query.data.data as unknown as ResumeDataV2;
      // REQ-032 layout-dnd fix: when refetching (e.g. triggered by our
      // own `lastSavedAt → invalidateQueries` invalidation above), the
      // server's snapshot may be STALE — it reflects the last
      // successfully-received PUT, but a debounced PUT for subsequent
      // local edits may not yet have arrived at the server. Replacing
      // `s.data` with the stale snapshot would clobber those pending
      // edits (observed in T081 layout-dnd Playwright test: after
      // Add Page + drag Profiles to sidebar, the Add Page's PUT
      // response invalidates → refetch returns PRE-drag data → drag is
      // reverted). Skip the reset when:
      //   - the store is hydrated AND the local data differs from the
      //     server's snapshot (i.e. user has unsaved local edits), OR
      //   - a save is currently in flight (`saving` or `pendingSave`),
      //     so we know the next response will arrive shortly.
      const storeState = useResumeV2Store.getState();
      if (storeState.hydrated) {
        const localDirty = storeState.isDirty;
        const saveInFlight =
          storeState.saving || storeState.pendingSave !== null;
        if (localDirty || saveInFlight) {
          return;
        }
      }
      // Defensive: if server data is missing critical fields, fill from
      // defaults so the editor never crashes on partial data.
      const serverMarkdown = serverData?.metadata?.markdown;
      const serverSourceMarkdown = serverMarkdown?.sourceMarkdown ?? "";
      const markdown = {
        ...defaultResumeDataV2.metadata.markdown,
        ...(serverMarkdown ?? {}),
      };
      let shouldPersistConvertedMarkdown = false;
      if (!serverSourceMarkdown.trim()) {
        const conversion = convertLegacyResumeToMarkdown(serverData);
        markdown.sourceMarkdown = conversion.convertedMarkdown;
        markdown.legacyConversionStatus = conversion.status;
        markdown.legacyConversionWarnings = conversion.warnings;
        shouldPersistConvertedMarkdown =
          conversion.status !== "not_needed" && conversion.convertedMarkdown.trim().length > 0;
      }
      const merged: ResumeDataV2 = {
        ...defaultResumeDataV2,
        ...serverData,
        metadata: {
          ...defaultResumeDataV2.metadata,
          ...(serverData?.metadata ?? {}),
          markdown,
        },
      };
      resetFromServer({
        id: query.data.id,
        data: merged,
        version: query.data.version,
      });
      if (shouldPersistConvertedMarkdown) {
        setData(merged);
      }
    }
  }, [query.data, resetFromServer, setData]);

  // T118 — Subscribe to cross-tab SSE updates for this resume.
  useResumeSse(id ?? null);

  // REQ-043 fix #2 — After a successful store-side auto-save (PUT
  // resolved without 409 / 423), the Zustand store already updated its
  // local `data` + `version` via `resetFromServer`, but the React
  // Query cache (`["resume-v2", id]`) is still stale. If the user
  // navigates away and back to the editor (or another consumer like
  // the resume list page reads this key), they'd see the pre-PUT
  // snapshot. We invalidate on `lastSavedAt` change so the next
  // mount / refetch pulls the fresh server state. (`lastSavedAt`
  // is set in store.runSave on the 200 path — see store/index.ts.)
  useEffect(() => {
    if (!id || lastSavedAt === null) return;
    queryClient.invalidateQueries({ queryKey: ["resume-v2", id] });
    queryClient.invalidateQueries({ queryKey: ["resumes-v2-list"] });
  }, [lastSavedAt, id, queryClient]);

  if (!id) {
    return (
      <div className="p-8 text-sm text-ink-3">
        <div className="mb-2 text-base text-ink-1">缺少简历 id</div>
        <button
          type="button"
          onClick={() => navigate("/dashboard")}
          className="text-xs text-primary-500 hover:underline"
        >
          返回
        </button>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="p-8 text-sm text-ink-3">
        <div className="mb-2 text-base text-ink-1">简历不存在</div>
        <button
          type="button"
          onClick={() => navigate("/dashboard")}
          className="text-xs text-primary-500 hover:underline"
        >
          返回
        </button>
      </div>
    );
  }

  if (forbidden) {
    return (
      <div className="p-8 text-sm text-ink-3">
        <div className="mb-2 text-base text-ink-1">没有访问权限</div>
        <button
          type="button"
          onClick={() => navigate("/dashboard")}
          className="text-xs text-primary-500 hover:underline"
        >
          返回
        </button>
      </div>
    );
  }

  if (legacy) {
    return (
      <div className="p-8 text-sm text-ink-3" data-testid="legacy-banner">
        <div
          className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-amber-900"
          role="status"
        >
          <div className="mb-1 text-sm font-semibold">Resume migration is required</div>
          <div className="text-xs leading-relaxed">{legacy}</div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              setLegacy(null);
              void query.refetch();
            }}
            className="text-xs text-primary-500 hover:underline"
            data-testid="legacy-retry-markdown"
          >
            Retry Markdown migration
          </button>
          <span aria-hidden className="text-surface-border">|</span>
          <button
            type="button"
            onClick={() => navigate("/dashboard")}
            className="text-xs text-ink-3 hover:underline"
          >
            返回看板
          </button>
        </div>
      </div>
    );
  }

  if (query.isLoading) {
    return <div className="p-8 text-sm text-ink-3">正在加载简历…</div>;
  }

  if (query.isError) {
    return (
      <div className="p-8 text-sm text-ink-3">
        <div className="mb-2 text-base text-ink-1">加载失败</div>
        <div className="text-xs text-ink-3">{String(query.error)}</div>
      </div>
    );
  }

  const resume = query.data;
  return (
    <BuilderShell
      data={storeData}
      onChange={(next) => setData(next)}
      resumeId={id ?? ""}
      resumeSlug={resume?.slug}
      ownerUsername={undefined}
      isPublic={Boolean(resume?.is_public)}
      passwordSet={Boolean(resume?.password_set)}
    />
  );
}
