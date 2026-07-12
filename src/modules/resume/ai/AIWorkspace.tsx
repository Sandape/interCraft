import { useState } from "react";
import { AlertTriangle, Check, ChevronRight, Loader2, RotateCcw, Sparkles, X } from "lucide-react";
import { AITaskActions } from "@/components/ai";
import { useAITask } from "@/hooks/queries/useAITasks";
import { AnalysisHistory } from "./AnalysisHistory";
import { FeedbackControl } from "./FeedbackControl";
import { RunRecovery } from "./RunRecovery";
import { SupplementFactFlow } from "./SupplementFactFlow";
import { useAIWorkspaceController } from "./useAIWorkspaceController";

type Tab = "overview" | "gaps" | "suggestions" | "history";

export function AIWorkspace({
  resumeId,
  resumeKind,
  jobId,
  onClose,
}: {
  resumeId: string;
  resumeKind: string;
  jobId?: string | null;
  onClose: () => void;
}) {
  const controller = useAIWorkspaceController({ resumeId, resumeKind, jobId });
  const [tab, setTab] = useState<Tab>("overview");
  const analysis = controller.analysis;
  const busy = controller.starting || controller.run?.status === "queued" || controller.run?.status === "running";
  const { data: canonicalTask, refetch: refetchCanonicalTask } = useAITask(
    controller.taskId,
    { enabled: Boolean(controller.taskId) },
  );

  return (
    <aside
      className="fixed inset-0 z-50 flex flex-col bg-[#f7f5ef] shadow-2xl md:absolute md:bottom-auto md:left-auto md:right-0 md:top-0 md:h-[calc(100vh-3.5rem)] md:w-[420px] md:border-l md:border-[#d7d2c7]"
      aria-label="AI 简历指导"
      data-testid="ai-workspace"
    >
      <header className="border-b border-[#d7d2c7] bg-[#fbfaf6] px-5 pb-4 pt-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#8b5e3c]">
              <Sparkles className="h-3.5 w-3.5" /> AI career intelligence
            </div>
            <h2 className="text-lg font-semibold text-[#20211f]">AI 简历指导</h2>
            <p className="mt-1 text-xs leading-5 text-[#676860]">
              {controller.mode === "job_fit" ? "岗位定制 · 证据与差距" : "通用体检 · 不展示岗位匹配分"}
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded p-2 text-[#676860] hover:bg-black/5" aria-label="关闭 AI 指导">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-4 flex items-center justify-between border-t border-[#e4e0d7] pt-3 text-[11px] text-[#77786f]">
          <span>简历版本 v{controller.version}</span>
          <span>{analysis?.is_stale ? "分析已过期" : analysis ? "分析可用" : "尚未分析"}</span>
        </div>
      </header>

      <nav className="grid grid-cols-4 border-b border-[#d7d2c7] bg-[#fbfaf6]" role="tablist" aria-label="AI 指导内容">
        {([
          ["overview", "概览"],
          ["gaps", "差距"],
          ["suggestions", "建议"],
          ["history", "历史"],
        ] as Array<[Tab, string]>).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`min-h-11 border-b-2 text-xs font-medium ${tab === key ? "border-[#9a5938] text-[#7f4328]" : "border-transparent text-[#74756e] hover:text-[#20211f]"}`}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div className="sr-only" aria-live="polite">
          {controller.analysisIsLocallyStale || analysis?.is_stale ? "当前分析已过期，需要重新分析。" : ""}
          {controller.previewIsLocallyStale ? "建议预览已因本地编辑失效。" : ""}
        </div>

        {controller.run && (
          <div className="mb-5 space-y-3">
            <RunRecovery
              run={controller.run}
              onRetry={controller.retry}
              onCancel={controller.cancelRun}
              retrying={controller.starting}
              cancelling={controller.cancelling}
              taskId={controller.taskId}
              canonicalStatus={controller.canonicalStatus}
              milestones={controller.milestones}
            />
            {canonicalTask && (
              <div data-testid="resume-ai-task-actions">
                <AITaskActions
                  task={canonicalTask}
                  onConflictRefresh={() => {
                    void refetchCanonicalTask();
                  }}
                />
              </div>
            )}
          </div>
        )}

        {controller.conflictDraft && (
          <div className="mb-5 border border-[#d9a58f] bg-[#fff7f2] p-4" role="alert">
            <div className="flex gap-2 text-sm font-medium text-[#853f28]">
              <AlertTriangle className="mt-0.5 h-4 w-4" /> 服务端版本冲突，已保留你的本地草稿
            </div>
            <p className="mt-2 text-xs leading-5 text-[#734d3e]">
              AI 应用没有覆盖未保存内容。编辑器已加载服务端最新版本，请从草稿与最新版本中人工合并后重新预览。
            </p>
          </div>
        )}

        {!analysis && !busy && (
          <div className="border-y border-[#d7d2c7] py-8">
            <p className="text-sm font-medium text-[#20211f]">从当前已保存版本开始分析</p>
            <p className="mt-2 text-xs leading-5 text-[#686961]">
              {controller.mode === "job_fit"
                ? "AI 会读取目标岗位与候选人证据，结果绑定当前简历和 JD 版本。"
                : "AI 会检查表达、结构、成果与可读性，不会生成虚假的岗位匹配分。"}
            </p>
            <button
              type="button"
              onClick={() => controller.start(false)}
              disabled={controller.starting || controller.isDirty || controller.saving}
              className="mt-5 inline-flex min-h-11 items-center gap-2 bg-[#20211f] px-4 text-sm font-medium text-white transition-colors hover:bg-[#393a36] disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Sparkles className="h-4 w-4" /> 开始真实 AI 分析
            </button>
          </div>
        )}

        {busy && !controller.run && (
          <div className="py-10 text-center" aria-live="polite">
            <Loader2 className="mx-auto h-5 w-5 animate-spin text-[#9a5938] motion-reduce:animate-none" />
            <p className="mt-3 text-sm text-[#30312e]">正在分析证据与岗位要求</p>
            <p className="mt-1 text-xs text-[#77786f]">准备真实模型调用</p>
          </div>
        )}

        {analysis?.status === "failed" && !busy && (
          <div className="border border-[#d9a58f] bg-[#fff7f2] p-4" role="alert">
            <div className="flex items-start gap-2 text-sm font-medium text-[#853f28]">
              <AlertTriangle className="mt-0.5 h-4 w-4" /> 本次真实 AI 分析未完成
            </div>
            <p className="mt-2 text-xs leading-5 text-[#734d3e]">
              没有生成固定或伪造结果。你可以从当前已保存版本安全重试。
            </p>
            <button
              type="button"
              onClick={() => controller.retry()}
              disabled={controller.starting || controller.isDirty || controller.saving}
              className="mt-4 min-h-11 bg-[#20211f] px-4 text-xs font-medium text-white disabled:opacity-40"
            >
              重试真实 AI 分析
            </button>
          </div>
        )}

        {analysis && analysis.status !== "failed" && tab === "overview" && (
          <div className="space-y-6">
            {controller.mode === "job_fit" && (
              <section className="border-b border-[#d7d2c7] pb-6">
                <div className="flex items-end justify-between">
                  <div>
                    <div className="text-4xl font-semibold tracking-tight text-[#20211f]">{analysis.overall_score ?? "—"}</div>
                    <div className="mt-1 text-xs text-[#77786f]">当前证据覆盖 / 100</div>
                  </div>
                  <div className="text-right text-xs text-[#676860]">
                    <div>置信度 {analysis.confidence_band ?? "—"}</div>
                    <div className="mt-1">{analysis.job_context?.company} · {analysis.job_context?.position}</div>
                  </div>
                </div>
                <p className="mt-4 border-l-2 border-[#b96a43] pl-3 text-[11px] leading-5 text-[#676860]">{analysis.disclaimer}</p>
              </section>
            )}
            {analysis.hard_blockers.length > 0 && (
              <div className="border border-[#d9a58f] bg-[#fff7f2] p-4" role="alert">
                <div className="flex gap-2 text-sm font-medium text-[#853f28]"><AlertTriangle className="mt-0.5 h-4 w-4" /> 硬性要求存在证据缺口</div>
                <p className="mt-2 text-xs leading-5 text-[#734d3e]">总分不会掩盖这些要求，请先核实真实经历。</p>
              </div>
            )}
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-[#77786f]">维度</h3>
              <div className="mt-3 divide-y divide-[#e2ded5] border-y border-[#d7d2c7]">
                {analysis.dimensions.map((dimension) => (
                  <div key={dimension.key} className="flex items-center justify-between py-3 text-sm">
                    <span className="text-[#3b3c38]">{dimension.key.replaceAll("_", " ")}</span>
                    <span className="font-semibold tabular-nums text-[#20211f]">{dimension.score}</span>
                  </div>
                ))}
                {analysis.dimensions.length === 0 && <div className="py-4 text-xs text-[#77786f]">通用体检不会显示岗位维度分。</div>}
              </div>
            </section>
            <button type="button" onClick={() => controller.retry()} className="text-xs font-medium text-[#8b4d31] hover:underline">基于最新版本重新分析</button>
          </div>
        )}

        {analysis && analysis.status !== "failed" && tab === "gaps" && (
          <div className="space-y-3">
            {analysis.gaps.map((gap) => (
              <article key={gap.id} className="border-b border-[#d7d2c7] pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-medium leading-5 text-[#262724]">{gap.requirement_excerpt}</div>
                  <span className="shrink-0 bg-[#ebe5da] px-2 py-1 text-[10px] text-[#6d553e]">{gap.coverage}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-[#686961]">{gap.explanation}</p>
                <div className="mt-2 flex items-center gap-1 text-[11px] text-[#8b4d31]">{gap.recommended_action}<ChevronRight className="h-3 w-3" /></div>
              </article>
            ))}
            {analysis.gaps.length === 0 && <p className="text-xs text-[#77786f]">当前模式没有岗位差距。</p>}
          </div>
        )}

        {analysis && analysis.status !== "failed" && tab === "suggestions" && (
          <div>
            <div className="space-y-3">
              {controller.suggestions.map((suggestion) => {
                const checked = controller.selected.includes(suggestion.id);
                const direct = suggestion.action_mode === "direct";
                return (
                  <article key={suggestion.id} className="border-b border-[#d7d2c7] pb-4" aria-labelledby={`suggestion-${suggestion.id}`}>
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!direct || suggestion.status === "applied"}
                        onChange={() => controller.setSelected(checked ? controller.selected.filter((id) => id !== suggestion.id) : [...controller.selected, suggestion.id])}
                        className="mt-1 h-4 w-4 accent-[#8b4d31]"
                        aria-label={`选择建议：${suggestion.title}`}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span id={`suggestion-${suggestion.id}`} className="text-sm font-medium text-[#262724]">{suggestion.title}</span>
                          <span className="text-[10px] uppercase tracking-wide text-[#8b4d31]">{suggestion.priority}</span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[#686961]">{suggestion.explanation}</p>
                        <button
                          type="button"
                          onClick={() => controller.focusSuggestion(suggestion.anchor.node_id)}
                          className="mt-2 text-[11px] text-[#8b4d31] hover:underline"
                        >
                          定位到简历位置
                        </button>
                        {!direct && <p className="mt-2 text-[11px] text-[#9a5938]">需要补充事实或人工判断，不能直接写入</p>}
                        <div className="mt-3 flex flex-wrap gap-2">
                          {suggestion.status !== "ignored" && (
                            <button
                              type="button"
                              onClick={() => controller.updateSuggestionStatus(suggestion.id, "ignore", "user_feedback")}
                              className="text-[11px] text-[#8b4d31] hover:underline"
                            >
                              忽略
                            </button>
                          )}
                          {suggestion.status !== "deferred" && (
                            <button
                              type="button"
                              onClick={() => controller.updateSuggestionStatus(suggestion.id, "defer")}
                              className="text-[11px] text-[#8b4d31] hover:underline"
                            >
                              稍后处理
                            </button>
                          )}
                          {suggestion.status !== "open" && (
                            <button
                              type="button"
                              onClick={() => controller.updateSuggestionStatus(suggestion.id, "reopen")}
                              className="text-[11px] text-[#8b4d31] hover:underline"
                            >
                              重新打开
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
            {controller.suggestions.length === 0 && (
              <div className="space-y-3">
                <p className="text-xs text-[#77786f]">暂无建议。可在分析完成后重新生成建议。</p>
                {analysis?.status === "complete" && (
                  <button
                    type="button"
                    onClick={() => controller.regenerateSuggestions()}
                    disabled={controller.regeneratingSuggestions}
                    className="min-h-10 border border-[#403f39] px-3 text-xs font-medium text-[#2a2b28] disabled:opacity-40"
                  >
                    {controller.regeneratingSuggestions ? "正在重新生成…" : "重新生成建议"}
                  </button>
                )}
              </div>
            )}

            {controller.suggestions.some((item) => item.action_mode === "needs_supplement") && (
              <div className="mt-5">
                <SupplementFactFlow
                  suggestions={controller.suggestions}
                  onConfirm={controller.confirmSupplement}
                  confirming={controller.confirmingSupplement}
                />
              </div>
            )}

            {controller.preview && (
              <section className="mt-5 border border-[#c9c2b5] bg-white p-4" aria-live="polite">
                <div className="flex items-center gap-2 text-sm font-medium text-[#262724]">
                  {controller.previewIsLocallyStale ? <AlertTriangle className="h-4 w-4 text-[#a75132]" /> : <Check className="h-4 w-4 text-[#557a5a]" />}
                  {controller.previewIsLocallyStale ? "简历已修改，预览失效" : "完整变更预览"}
                </div>
                <div className="mt-4 grid gap-3 text-xs md:grid-cols-2">
                  <div>
                    <div className="mb-1 font-semibold text-[#3b3c38]">修改前</div>
                    <pre className="max-h-56 overflow-auto whitespace-pre-wrap border border-[#e2ded5] bg-[#fbfaf6] p-3 font-mono text-[11px] leading-5 text-[#30312e]">
                      {controller.preview.diff?.before_markdown ?? "无可用预览"}
                    </pre>
                  </div>
                  <div>
                    <div className="mb-1 font-semibold text-[#3b3c38]">修改后</div>
                    <pre className="max-h-56 overflow-auto whitespace-pre-wrap border border-[#e2ded5] bg-[#fffaf4] p-3 font-mono text-[11px] leading-5 text-[#30312e]">
                      {controller.preview.diff?.after_markdown ?? "无可用预览"}
                    </pre>
                  </div>
                </div>
                <div className="mt-3 space-y-2 text-[11px] text-[#686961]" aria-label="JSON patch 摘要">
                  {controller.preview.diff?.patches.map((patch, index) => <div key={`${patch.path}-${index}`} className="font-mono">{patch.op} {patch.path}</div>)}
                </div>
                {controller.preview.blocked.length > 0 && <p className="mt-3 text-xs text-[#9a5938]">{controller.preview.blocked.length} 项因事实要求被阻止。</p>}
              </section>
            )}

            <div className="sticky bottom-0 -mx-5 mt-5 border-t border-[#d7d2c7] bg-[#f7f5ef] px-5 py-4" role="region" aria-label="批量应用建议">
              <div className="mb-2 text-[11px] text-[#676860]">已选择 {controller.selected.length} 项；只会应用被选中且通过预览的建议。</div>
              <div className="flex gap-2">
                <button type="button" onClick={controller.previewSelected} disabled={controller.selected.length === 0 || controller.previewing} className="min-h-11 flex-1 border border-[#403f39] px-3 text-xs font-medium text-[#2a2b28] disabled:opacity-40">预览 {controller.selected.length} 项</button>
                <button type="button" onClick={controller.applyPreview} disabled={!controller.preview?.preview_token || controller.previewIsLocallyStale || controller.applying} className="min-h-11 flex-1 bg-[#20211f] px-3 text-xs font-medium text-white disabled:opacity-40">确认应用</button>
              </div>
            </div>
            {controller.lastChangeSetId && <button type="button" onClick={controller.undoLastApply} disabled={controller.undoing} className="mt-3 inline-flex items-center gap-1 text-xs text-[#8b4d31]"><RotateCcw className="h-3.5 w-3.5" /> 撤销本次 AI 应用</button>}
            {analysis && (controller.selected[0] || controller.suggestions[0]?.id) && (
              <div className="mt-5">
                <FeedbackControl
                  analysisId={analysis.id}
                  suggestionId={controller.selected[0] ?? controller.suggestions[0]?.id}
                  changeSetId={controller.lastChangeSetId}
                  onSubmit={controller.submitFeedback}
                  submitting={controller.submittingFeedback}
                />
              </div>
            )}
          </div>
        )}

        {analysis && tab === "history" && (
          <AnalysisHistory
            analyses={controller.analyses}
            currentAnalysisId={analysis.id}
            comparison={controller.comparison}
            onRefresh={controller.retry}
            onCompare={controller.compareAnalyses}
            refreshing={controller.starting}
            comparing={controller.comparingAnalyses}
          />
        )}

        {[controller.startError, controller.cancelError, controller.previewError, controller.applyError, controller.undoError, controller.supplementError, controller.feedbackError, controller.comparisonError].filter(Boolean).map((error, index) => (
          <div key={index} className="mt-4 border border-[#d9a58f] bg-[#fff7f2] p-3 text-xs text-[#853f28]" role="alert">{error instanceof Error ? error.message : "操作失败，请重试"}</div>
        ))}
      </div>
    </aside>
  );
}
