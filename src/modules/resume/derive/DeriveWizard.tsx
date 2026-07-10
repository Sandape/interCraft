import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useJobs } from "@/hooks/queries/useJobs";
import { startDerive } from "./api";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function DeriveWizard({ open, onClose }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: jobsResp, isLoading: jobsLoading, isFetching } = useJobs();
  const jobs = jobsResp?.data ?? [];
  const [jobId, setJobId] = useState<string>("");
  const [pages, setPages] = useState<1 | 2 | 3>(1);
  const [templateId, setTemplateId] = useState("pikachu");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const jobsPending = jobsLoading || (isFetching && jobs.length === 0);

  // Open wizard after API-seeded jobs: force refresh so stale empty cache
  // from an earlier mount does not hide the new job.
  useEffect(() => {
    if (!open) return;
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
  }, [open, queryClient]);

  const selected = useMemo(
    () => jobs.find((j: { id: string }) => j.id === jobId),
    [jobs, jobId],
  );

  const hasJd = Boolean(
    selected &&
      String(
        (selected as { requirements_md?: string }).requirements_md || "",
      ).trim(),
  );

  if (!open) return null;

  async function handleStart() {
    setError(null);
    if (!jobId) {
      setError("请选择岗位");
      return;
    }
    if (!hasJd) {
      setError("该岗位没有 JD，请先在求职追踪中补充 requirements");
      return;
    }
    setBusy(true);
    try {
      const res = await startDerive({
        job_id: jobId,
        target_page_count: pages,
        template_id: templateId,
      });
      onClose();
      navigate(`/resume/derive/${res.run_id}`);
    } catch (e: unknown) {
      const err = e as { message?: string; body?: { error?: string; message?: string } };
      setError(err.body?.message || err.message || "启动派生失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      data-testid="derive-wizard"
    >
      <Card className="w-full max-w-lg space-y-4 p-6">
        <h2 className="text-xl font-semibold">一键派生简历</h2>
        <label className="block space-y-1 text-sm">
          <span>目标岗位</span>
          <select
            className="w-full rounded border px-2 py-2"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            data-testid="derive-job-select"
          >
            <option value="">
              {jobsPending ? "加载岗位中…" : "选择求职追踪中的岗位"}
            </option>
            {jobs.map((j: { id: string; company: string; position: string; requirements_md?: string }) => (
              <option key={j.id} value={j.id}>
                {j.company} · {j.position}
                {j.requirements_md?.trim() ? "" : "（无 JD）"}
              </option>
            ))}
          </select>
        </label>
        {open && !jobsPending && jobs.length === 0 && (
          <p className="text-sm text-muted-foreground" data-testid="derive-no-jobs">
            暂无岗位，请先在求职追踪中创建。
          </p>
        )}
        {selected && !hasJd && (
          <p className="text-sm text-destructive" data-testid="derive-no-jd">
            没有 JD 的岗位不能直接派生，请先补充 JD。
          </p>
        )}
        <fieldset className="space-y-1 text-sm">
          <legend>目标页数（硬约束）</legend>
          <div className="flex gap-3">
            {([1, 2, 3] as const).map((n) => (
              <label key={n} className="flex items-center gap-1">
                <input
                  type="radio"
                  name="pages"
                  checked={pages === n}
                  onChange={() => setPages(n)}
                />
                {n} 页
              </label>
            ))}
          </div>
        </fieldset>
        <label className="block space-y-1 text-sm">
          <span>模板</span>
          <select
            className="w-full rounded border px-2 py-2"
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
          >
            <option value="pikachu">Pikachu</option>
            <option value="onyx">Onyx</option>
            <option value="bronzor">Bronzor</option>
          </select>
        </label>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            取消
          </Button>
          <Button
            onClick={handleStart}
            disabled={busy || !jobId || !hasJd}
            data-testid="derive-start-btn"
          >
            开始生成
          </Button>
        </div>
      </Card>
    </div>
  );
}
