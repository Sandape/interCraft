import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { AIMilestoneList, AITaskActions } from "@/components/ai";
import { useAITask } from "@/hooks/queries/useAITasks";
import type { AvailableAction, Milestone } from "@/types/ai-runtime";
import { getDeriveRun, type DeriveMilestone, type DeriveRun } from "./api";

/** @deprecated Prefer server terminal/canonical_status; kept for test import stability. */
export const DERIVE_CLIENT_TIMEOUT_MS = 30_000;

const DOMAIN_TERMINAL = new Set([
  "succeeded",
  "needs_guidance",
  "failed",
  "canceled",
  "cancelled",
  "partially_succeeded",
]);

const CANONICAL_TERMINAL = new Set([
  "succeeded",
  "partially_succeeded",
  "failed",
  "cancelled",
  "expired",
]);

function isTerminal(run: DeriveRun): boolean {
  if (run.canonical_status && CANONICAL_TERMINAL.has(run.canonical_status)) {
    return true;
  }
  return DOMAIN_TERMINAL.has(run.status);
}

function toMilestones(items: DeriveMilestone[] | undefined): Milestone[] {
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

export function DeriveProgress() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<DeriveRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const data = await getDeriveRun(runId);
        if (cancelled) return;
        setRun(data);
        setError(null);
        if (isTerminal(data)) return;
      } catch (e: unknown) {
        if (!cancelled) {
          setError((e as { message?: string })?.message || "轮询失败");
        }
      }
    };

    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [runId]);

  const taskId = run?.task_id ?? run?.runtime?.task_id ?? null;
  const { data: canonicalTask, refetch: refetchCanonical } = useAITask(taskId, {
    enabled: Boolean(taskId),
  });

  const done = run ? isTerminal(run) : false;
  const milestones = toMilestones(run?.milestones);
  const actionsFromRun = (run?.available_actions ?? []) as AvailableAction[];
  const actionsTask =
    canonicalTask ??
    (taskId
      ? {
          task_id: taskId,
          task_version: 1,
          available_actions: actionsFromRun,
          status: (run?.canonical_status ?? "running") as
            | "accepted"
            | "queued"
            | "running"
            | "waiting_user"
            | "retry_wait"
            | "cancelling"
            | "result_confirming"
            | "succeeded"
            | "partially_succeeded"
            | "failed"
            | "cancelled"
            | "expired",
          terminal: done,
          point_summary: {
            quoted_max: 0,
            reserved: 0,
            settled: 0,
            released: 0,
            settlement_status: "unsettled" as const,
          },
        }
      : null);

  return (
    <div className="mx-auto max-w-xl p-6" data-testid="derive-progress">
      <Card className="space-y-3 p-6">
        <h1 className="text-xl font-semibold">
          {done ? "派生任务结束" : "派生生成中"}
        </h1>
        {error && (
          <p className="text-sm text-destructive" data-testid="derive-progress-error">
            {error}
          </p>
        )}
        {run && (
          <>
            <p className="text-sm" data-testid="derive-progress-status">
              状态：{run.canonical_status ?? run.status} · 阶段：{run.phase}
              {typeof run.progress_pct === "number" ? ` · 进度 ${run.progress_pct}%` : ""}
            </p>
            {taskId && (
              <Link
                to={`/ai-tasks/${encodeURIComponent(taskId)}`}
                className="inline-flex text-sm underline"
                data-testid="derive-task-link"
              >
                打开 AI 任务
              </Link>
            )}
            {milestones.length > 0 && (
              <div data-testid="derive-milestones">
                <AIMilestoneList milestones={milestones} />
              </div>
            )}
            {run.settlement && (
              <p className="text-xs text-muted-foreground" data-testid="derive-settlement">
                已交付里程碑：{(run.settlement.delivered_milestones ?? []).join(", ") || "无"}
                {" · "}
                失败：{(run.settlement.failed_milestones ?? []).join(", ") || "无"}
              </p>
            )}
            {actionsTask && (actionsTask.available_actions?.length ?? 0) > 0 && (
              <div data-testid="derive-server-actions">
                <AITaskActions
                  task={actionsTask}
                  onConflictRefresh={() => {
                    void refetchCanonical();
                  }}
                />
              </div>
            )}
            {run.error_message && (
              <p
                className="text-sm text-amber-700"
                data-testid="derive-progress-error-message"
              >
                {run.error_message}
              </p>
            )}
            {(run.status === "failed" || run.canonical_status === "failed") && (
              <div className="space-y-2" data-testid="derive-progress-failed">
                <p className="text-sm text-destructive">
                  派生失败
                  {run.error_code ? `（${run.error_code}）` : ""}。请返回后重试。
                </p>
                <Link to="/resume" className="inline-flex text-sm underline">
                  返回简历中心
                </Link>
              </div>
            )}
            {done && run.derived_resume_id && (
              <Link
                to={`/resume/${run.derived_resume_id}`}
                className="btn-primary btn-md inline-flex items-center rounded px-3 py-2 text-sm"
                data-testid="derive-open-derived"
              >
                打开派生简历
              </Link>
            )}
            {run.status === "needs_guidance" && (
              <p className="text-sm" data-testid="derive-guidance">
                自动页数校准未完全达标，请在编辑器中按引导调整模板/模块后再导出。
              </p>
            )}
          </>
        )}
        {!run && !error && (
          <p className="text-sm text-muted-foreground" data-testid="derive-progress-waiting">
            等待任务状态…
          </p>
        )}
      </Card>
    </div>
  );
}

export default DeriveProgress;
