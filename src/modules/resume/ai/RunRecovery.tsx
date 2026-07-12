import { Link } from "react-router-dom";
import { AlertTriangle, Loader2, RotateCcw, XCircle } from "lucide-react";
import { AIMilestoneList } from "@/components/ai";
import type { Milestone } from "@/types/ai-runtime";
import type { RunStatus } from "./types";
import type { AnalysisRunStatus, ResumeAIMilestone } from "./api";

const RUNNING_STATUSES = new Set<RunStatus>(["queued", "running", "canceling"]);
const CANONICAL_RUNNING = new Set([
  "accepted",
  "queued",
  "running",
  "waiting_user",
  "retry_wait",
  "cancelling",
  "result_confirming",
]);

function statusCopy(status: RunStatus, canonical?: string | null) {
  if (canonical === "partially_succeeded" || status === "partial_success" || status === "partial") {
    return "部分完成，仍有组件失败或被跳过";
  }
  switch (status) {
    case "queued":
      return "已排队，等待真实 AI 运行";
    case "running":
      return "正在运行，结果以服务端状态为准";
    case "needs_guidance":
      return "需要补充材料后才能继续";
    case "canceling":
      return "正在取消，完成前不会发布新草稿";
    case "cancelled":
      return "已取消，不会展示为成功结果";
    case "failed":
      return "运行失败，没有生成假成功结果";
    default:
      return "运行已完成";
  }
}

function toMilestones(items: ResumeAIMilestone[] | null | undefined): Milestone[] {
  if (!items?.length) return [];
  const allowed = new Set([
    "pending",
    "running",
    "delivered",
    "failed",
    "cancelled",
    "invalidated",
  ]);
  return items.map((m) => ({
    code: m.code,
    label: m.code,
    status: (allowed.has(m.status) ? m.status : "pending") as Milestone["status"],
    settle_eligible: Boolean(m.settle_eligible),
    points_settled: 0,
  }));
}

export function RunRecovery({
  run,
  onRetry,
  onCancel,
  retrying = false,
  cancelling = false,
  taskId = null,
  canonicalStatus = null,
  milestones = null,
}: {
  run: AnalysisRunStatus | null;
  onRetry: () => void;
  onCancel: () => void;
  retrying?: boolean;
  cancelling?: boolean;
  taskId?: string | null;
  canonicalStatus?: string | null;
  milestones?: ResumeAIMilestone[] | null;
}) {
  if (!run) return null;

  const status = run.status;
  const running =
    RUNNING_STATUSES.has(status) ||
    (canonicalStatus ? CANONICAL_RUNNING.has(canonicalStatus) : false);
  const failed =
    status === "failed" ||
    status === "cancelled" ||
    status === "partial_success" ||
    status === "partial" ||
    canonicalStatus === "failed" ||
    canonicalStatus === "cancelled" ||
    canonicalStatus === "partially_succeeded";
  const progress = typeof run.progress_percent === "number" ? Math.max(0, Math.min(100, run.progress_percent)) : null;
  const milestoneList = toMilestones(milestones ?? run.milestones);

  return (
    <section
      className={`border p-4 ${
        running ? "border-[#c9c2b5] bg-[#fbfaf6]" : failed ? "border-[#d9a58f] bg-[#fff7f2]" : "border-[#d7d2c7] bg-[#fbfaf6]"
      }`}
      data-testid="run-recovery"
      role={failed ? "alert" : "status"}
      aria-live="polite"
    >
      <div className="flex items-start gap-2">
        {running ? (
          <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-[#8b4d31] motion-reduce:animate-none" />
        ) : failed ? (
          <AlertTriangle className="mt-0.5 h-4 w-4 text-[#a75132]" />
        ) : (
          <RotateCcw className="mt-0.5 h-4 w-4 text-[#557a5a]" />
        )}
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-[#262724]">
            {statusCopy(status, canonicalStatus)}
          </h3>
          <p className="mt-1 text-xs leading-5 text-[#686961]">
            {canonicalStatus
              ? `规范状态：${canonicalStatus} · ${run.phase || "等待服务端阶段更新"}`
              : run.phase || "等待服务端阶段更新"}
          </p>
          {run.error?.message && <p className="mt-2 text-xs text-[#853f28]">{run.error.message}</p>}
          {taskId && (
            <Link
              to={`/ai-tasks/${encodeURIComponent(taskId)}`}
              className="mt-2 inline-flex text-xs text-[#8b4d31] underline"
              data-testid="resume-ai-task-link"
            >
              查看 AI 任务详情
            </Link>
          )}
        </div>
      </div>

      {milestoneList.length > 0 && (
        <div className="mt-4" data-testid="resume-ai-milestones">
          <AIMilestoneList milestones={milestoneList} />
        </div>
      )}

      {progress !== null && (
        <div className="mt-4" aria-label={`运行进度 ${progress}%`}>
          <div className="h-1.5 overflow-hidden bg-[#e4e0d7]">
            <div className="h-full bg-[#8b4d31]" style={{ width: `${progress}%` }} />
          </div>
          <div className="mt-1 text-right text-[11px] text-[#77786f]">{progress}%</div>
        </div>
      )}

      {run.components && Object.keys(run.components).length > 0 && (
        <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
          {Object.entries(run.components).map(([name, value]) => (
            <div key={name} className="border border-[#e2ded5] bg-white p-2">
              <dt className="truncate text-[#686961]">{name}</dt>
              <dd className="mt-1 font-medium text-[#262724]">{value}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {running && (
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelling || status === "canceling"}
            className="inline-flex min-h-10 items-center gap-2 border border-[#a75132] px-4 text-xs font-medium text-[#853f28] disabled:opacity-40"
          >
            <XCircle className="h-3.5 w-3.5" />
            取消运行
          </button>
        )}
        {(failed || status === "needs_guidance") && (
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying || (run.error?.retryable === false && status === "failed")}
            className="inline-flex min-h-10 items-center gap-2 bg-[#20211f] px-4 text-xs font-medium text-white disabled:opacity-40"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            重试真实 AI
          </button>
        )}
      </div>
    </section>
  );
}
