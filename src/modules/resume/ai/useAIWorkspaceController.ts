import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/errors";
import type { ResumeDataV2 } from "@/modules/resume/v2/schema/data";
import { useResumeV2Store } from "@/modules/resume/v2/store";
import {
  applySuggestions,
  cancelRun,
  compareAnalyses,
  confirmSupplementFact,
  getAnalysisRun,
  listAnalyses,
  listSuggestions,
  previewSuggestions,
  regenerateSuggestions,
  startAnalysis,
  submitFeedback,
  undoChangeSet,
  updateSuggestionStatus,
  type SuggestionPreview,
} from "./api";
import { resumeAIKeys } from "./queryKeys";
import type { AnalysisMode, FeedbackCategory, ResumeAnalysisComparison, SupplementConfirmationInput } from "./types";

function newIdempotencyKey(prefix: string) {
  const id = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  return `${prefix}-${id}`;
}

export function useAIWorkspaceController({
  resumeId,
  resumeKind,
  jobId,
}: {
  resumeId: string;
  resumeKind: string;
  jobId?: string | null;
}) {
  const mode: AnalysisMode = resumeKind === "derived" && jobId ? "job_fit" : "general";
  const queryClient = useQueryClient();
  const version = useResumeV2Store((state) => state.version);
  const isDirty = useResumeV2Store((state) => state.isDirty);
  const saving = useResumeV2Store((state) => state.saving);
  const lastEditAt = useResumeV2Store((state) => state.lastEditAt);
  const flushSave = useResumeV2Store((state) => state.flushSave);
  const resetFromServer = useResumeV2Store((state) => state.resetFromServer);
  const focusAIAnchor = useResumeV2Store((state) => state.focusAIAnchor);
  const [runId, setRunId] = useState<string | null>(null);
  const [acceptedTask, setAcceptedTask] = useState<Awaited<
    ReturnType<typeof startAnalysis>
  > | null>(null);
  const [lastRunStatus, setLastRunStatus] = useState<Awaited<
    ReturnType<typeof getAnalysisRun>
  > | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<SuggestionPreview | null>(null);
  const [previewLocalRevision, setPreviewLocalRevision] = useState<number | null>(null);
  const [lastChangeSetId, setLastChangeSetId] = useState<string | null>(null);
  const [conflictDraft, setConflictDraft] = useState<ResumeDataV2 | null>(null);
  const [comparison, setComparison] = useState<ResumeAnalysisComparison | null>(null);

  const analysesQuery = useQuery({
    queryKey: resumeAIKeys.analyses(resumeId, mode),
    queryFn: () => listAnalyses(resumeId, mode),
  });
  const currentAnalysis = analysesQuery.data?.[0] ?? null;

  useEffect(() => {
    // Selection and signed preview tokens belong to one immutable analysis.
    // A refresh that publishes a newer analysis must never leave the previous
    // analysis' apply action armed in the UI.
    setSelected([]);
    setPreview(null);
    setPreviewLocalRevision(null);
  }, [currentAnalysis?.id]);

  const runQuery = useQuery({
    queryKey: resumeAIKeys.run(runId ?? "idle"),
    queryFn: () => getAnalysisRun(runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1200 : false;
    },
  });

  const suggestionsQuery = useQuery({
    queryKey: resumeAIKeys.suggestions(resumeId, currentAnalysis?.id ?? "none"),
    queryFn: () => listSuggestions(resumeId, currentAnalysis!.id),
    enabled: Boolean(currentAnalysis?.id && currentAnalysis.status === "complete"),
  });

  const startMutation = useMutation({
    mutationFn: async (force: boolean) => {
      await flushSave();
      const state = useResumeV2Store.getState();
      if (state.isDirty || state.saving) throw new Error("简历尚未保存，暂不能分析");
      return startAnalysis(resumeId, {
        mode,
        client_version: state.version,
        job_id: mode === "job_fit" ? jobId : null,
        force,
      });
    },
    onSuccess: (result) => {
      setRunId(result.run_id);
      setAcceptedTask(result);
      setLastRunStatus(null);
    },
  });

  const terminalRun = runQuery.data?.status;
  useEffect(() => {
    if (runQuery.data) {
      setLastRunStatus(runQuery.data);
    }
  }, [runQuery.data]);
  useEffect(() => {
    if (runId && terminalRun && !["queued", "running"].includes(terminalRun)) {
      void queryClient.invalidateQueries({ queryKey: resumeAIKeys.analyses(resumeId, mode) });
      void queryClient.invalidateQueries({ queryKey: resumeAIKeys.suggestions(resumeId, runId) });
      setRunId(null);
    }
  }, [mode, queryClient, resumeId, runId, terminalRun]);

  const runStatus = runQuery.data ?? lastRunStatus;
  const taskId = runStatus?.task_id ?? acceptedTask?.task_id ?? null;
  const canonicalStatus =
    runStatus?.canonical_status ?? acceptedTask?.canonical_status ?? runStatus?.status ?? null;
  const availableActions =
    runStatus?.available_actions ?? acceptedTask?.available_actions ?? [];
  const milestones = runStatus?.milestones ?? acceptedTask?.milestones ?? null;
  const runtimeLinks = runStatus?.runtime ?? acceptedTask?.runtime ?? null;
  const previewIsLocallyStale =
    preview !== null && previewLocalRevision !== (lastEditAt ?? 0);
  const analysisIsLocallyStale = Boolean(currentAnalysis && currentAnalysis.resume_version !== version);

  const previewMutation = useMutation({
    mutationFn: async () => {
      await flushSave();
      const state = useResumeV2Store.getState();
      if (state.isDirty || state.saving) throw new Error("请等待保存完成后再预览");
      const localRevision = state.lastEditAt ?? 0;
      const result = await previewSuggestions(resumeId, {
        analysis_id: currentAnalysis!.id,
        suggestion_ids: selected,
        client_version: state.version,
      });
      return { result, localRevision };
    },
    onSuccess: ({ result, localRevision }) => {
      setPreview(result);
      setPreviewLocalRevision(localRevision);
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      await flushSave();
      if (!preview?.preview_token || previewIsLocallyStale) throw new Error("预览已过期，请重新预览");
      const state = useResumeV2Store.getState();
      if (state.isDirty || state.version !== preview.base_resume_version) {
        throw new Error("简历已修改，请重新预览");
      }
      return applySuggestions(
        resumeId,
        { preview_token: preview.preview_token, client_version: state.version },
        newIdempotencyKey("apply"),
      );
    },
    onSuccess: (result) => {
      resetFromServer({
        id: result.resume.id,
        version: result.resume.version,
        data: result.resume.data as unknown as ResumeDataV2,
      });
      setLastChangeSetId(result.change_set_id);
      setPreview(null);
      setSelected([]);
      setConflictDraft(null);
      void queryClient.invalidateQueries({ queryKey: resumeAIKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["resume-v2", resumeId] });
    },
    onError: (error) => {
      if (!(error instanceof ApiError) || error.status !== 409) return;
      const state = useResumeV2Store.getState();
      setConflictDraft(JSON.parse(JSON.stringify(state.data)) as ResumeDataV2);
      const latestData = error.details?.latest_data;
      const latestVersion = error.details?.latest_version;
      if (latestData && typeof latestVersion === "number") {
        resetFromServer({
          id: resumeId,
          version: latestVersion,
          data: latestData as ResumeDataV2,
        });
      }
    },
  });

  const undoMutation = useMutation({
    mutationFn: () =>
      undoChangeSet(
        lastChangeSetId!,
        useResumeV2Store.getState().version,
        newIdempotencyKey("undo"),
      ),
    onSuccess: (result) => {
      resetFromServer({
        id: result.resume.id,
        version: result.resume.version,
        data: result.resume.data as unknown as ResumeDataV2,
      });
      setLastChangeSetId(null);
      void queryClient.invalidateQueries({ queryKey: resumeAIKeys.all });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelRun(runId!),
    onSuccess: (result) => {
      void queryClient.setQueryData(resumeAIKeys.run(result.run_id), result);
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateSuggestions(currentAnalysis!.id, newIdempotencyKey("regen")),
    onSuccess: (result) => setRunId(result.run_id),
  });

  const suggestionStatusMutation = useMutation({
    mutationFn: ({ suggestionId, action, reason }: { suggestionId: string; action: "ignore" | "defer" | "reopen"; reason?: string | null }) =>
      updateSuggestionStatus(suggestionId, { action, reason }),
    onSuccess: () => {
      if (currentAnalysis?.id) {
        void queryClient.invalidateQueries({ queryKey: resumeAIKeys.suggestions(resumeId, currentAnalysis.id) });
      }
    },
  });

  const supplementMutation = useMutation({
    mutationFn: (input: SupplementConfirmationInput) => confirmSupplementFact(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: resumeAIKeys.all });
    },
  });

  const feedbackMutation = useMutation({
    mutationFn: (input: {
      analysis_id: string;
      suggestion_id?: string | null;
      change_set_id?: string | null;
      category: FeedbackCategory;
      comment?: string | null;
    }) => submitFeedback(input),
  });

  const comparisonMutation = useMutation({
    mutationFn: ({ beforeId, afterId }: { beforeId: string; afterId: string }) => compareAnalyses(beforeId, afterId),
    onSuccess: (result) => setComparison(result),
  });

  return useMemo(
    () => ({
      mode,
      version,
      isDirty,
      saving,
      analysis: currentAnalysis,
      analyses: analysesQuery.data ?? [],
      analysisLoading: analysesQuery.isLoading,
      run: runQuery.data ?? null,
      suggestions: suggestionsQuery.data ?? [],
      suggestionsLoading: suggestionsQuery.isLoading,
      selected,
      setSelected,
      preview,
      previewIsLocallyStale,
      analysisIsLocallyStale,
      lastChangeSetId,
      conflictDraft,
      comparison,
      taskId,
      canonicalStatus,
      availableActions,
      milestones,
      runtimeLinks,
      acceptedTask,
      start: (force = false) => startMutation.mutate(force),
      starting: startMutation.isPending,
      startError: startMutation.error,
      retry: () => startMutation.mutate(true),
      cancelRun: () => cancelMutation.mutate(),
      cancelling: cancelMutation.isPending,
      cancelError: cancelMutation.error,
      regenerateSuggestions: () => regenerateMutation.mutate(),
      regeneratingSuggestions: regenerateMutation.isPending,
      updateSuggestionStatus: (suggestionId: string, action: "ignore" | "defer" | "reopen", reason?: string | null) =>
        suggestionStatusMutation.mutate({ suggestionId, action, reason }),
      updatingSuggestionStatus: suggestionStatusMutation.isPending,
      focusSuggestion: (nodeId: string) => focusAIAnchor(nodeId),
      confirmSupplement: (input: SupplementConfirmationInput) => supplementMutation.mutate(input),
      confirmingSupplement: supplementMutation.isPending,
      supplementError: supplementMutation.error,
      submitFeedback: (input: {
        analysis_id: string;
        suggestion_id?: string | null;
        change_set_id?: string | null;
        category: FeedbackCategory;
        comment?: string | null;
      }) => feedbackMutation.mutate(input),
      submittingFeedback: feedbackMutation.isPending,
      feedbackError: feedbackMutation.error,
      compareAnalyses: (beforeId: string, afterId: string) => comparisonMutation.mutate({ beforeId, afterId }),
      comparingAnalyses: comparisonMutation.isPending,
      comparisonError: comparisonMutation.error,
      previewSelected: () => previewMutation.mutate(),
      previewing: previewMutation.isPending,
      previewError: previewMutation.error,
      applyPreview: () => applyMutation.mutate(),
      applying: applyMutation.isPending,
      applyError: applyMutation.error,
      undoLastApply: () => undoMutation.mutate(),
      undoing: undoMutation.isPending,
      undoError: undoMutation.error,
    }),
    [
      mode, version, isDirty, saving, currentAnalysis, analysesQuery.data,
      analysesQuery.isLoading, runQuery.data, suggestionsQuery.data,
      suggestionsQuery.isLoading, selected, preview, previewIsLocallyStale,
      analysisIsLocallyStale, lastChangeSetId, conflictDraft, comparison,
      taskId, canonicalStatus, availableActions, milestones, runtimeLinks, acceptedTask,
      lastRunStatus,
      startMutation, cancelMutation, regenerateMutation, suggestionStatusMutation,
      supplementMutation, feedbackMutation, comparisonMutation, previewMutation,
      applyMutation, undoMutation, focusAIAnchor,
    ],
  );
}
