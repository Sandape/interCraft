import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { getDeriveRun, type DeriveRun } from "./api";

/** REQ-056 SC-005: surface failure if still non-terminal after this window. */
export const DERIVE_CLIENT_TIMEOUT_MS = 30_000;

const TERMINAL = new Set([
  "succeeded",
  "needs_guidance",
  "failed",
  "canceled",
]);

export function DeriveProgress() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<DeriveRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    startedAt.current = Date.now();
    setTimedOut(false);

    const tick = async () => {
      try {
        const data = await getDeriveRun(runId);
        if (cancelled) return;
        setRun(data);
        if (TERMINAL.has(data.status)) {
          setTimedOut(false);
          return;
        }
        if (Date.now() - startedAt.current >= DERIVE_CLIENT_TIMEOUT_MS) {
          setTimedOut(true);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError((e as { message?: string })?.message || "轮询失败");
        }
      }
    };

    tick();
    const id = window.setInterval(tick, 1500);
    const timeoutId = window.setTimeout(() => {
      if (!cancelled) setTimedOut(true);
    }, DERIVE_CLIENT_TIMEOUT_MS);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      window.clearTimeout(timeoutId);
    };
  }, [runId]);

  const done = run && TERMINAL.has(run.status);
  const showTimeout =
    timedOut && run && !TERMINAL.has(run.status) && !error;

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
        {showTimeout && (
          <div
            className="space-y-2 rounded border border-amber-300 bg-amber-50 p-3 text-sm"
            data-testid="derive-progress-timeout"
          >
            <p className="font-medium text-amber-900">
              等待超时：派生后台可能暂不可用或任务卡住。
            </p>
            <p className="text-amber-800">
              你可以返回简历中心稍后重试，或刷新本页继续查看状态。
            </p>
            <Link
              to="/resume"
              className="inline-flex text-sm underline"
              data-testid="derive-timeout-back"
            >
              返回简历中心
            </Link>
          </div>
        )}
        {run && (
          <>
            <p className="text-sm" data-testid="derive-progress-status">
              状态：{run.status} · 阶段：{run.phase} · 进度 {run.progress_pct}%
            </p>
            {run.error_message && (
              <p
                className="text-sm text-amber-700"
                data-testid="derive-progress-error-message"
              >
                {run.error_message}
              </p>
            )}
            {run.status === "failed" && (
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
