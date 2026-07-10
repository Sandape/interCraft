import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { getExportGate, resumeGuidance, type ExportGate } from "./api";
import { DeriveGuidance } from "./DeriveGuidance";

interface Props {
  resumeId: string;
  targetPageCount?: number | null;
  actualPageCount?: number | null;
  deriveRunId?: string | null;
}

export function PageControlPanel({
  resumeId,
  targetPageCount,
  actualPageCount,
  deriveRunId,
}: Props) {
  const navigate = useNavigate();
  const [gate, setGate] = useState<ExportGate | null>(null);
  const [guidanceOpen, setGuidanceOpen] = useState(false);
  const [guidanceBusy, setGuidanceBusy] = useState(false);
  const [guidanceError, setGuidanceError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getExportGate(resumeId)
      .then((g) => {
        if (!cancelled) setGate(g);
      })
      .catch(() => {
        if (!cancelled) setGate(null);
      });
    return () => {
      cancelled = true;
    };
  }, [resumeId]);

  const target = gate?.target_page_count ?? targetPageCount;
  const actual = gate?.actual_page_count ?? actualPageCount;
  const ok = gate?.exportable ?? false;
  const blockers = gate?.blockers || [];
  const pageMismatch = blockers.includes("page_count_mismatch");

  async function handleGuidanceContinue(opts: {
    action: string;
    template_id?: string;
    target_page_count?: 1 | 2 | 3;
  }) {
    if (!deriveRunId) {
      setGuidanceOpen(false);
      return;
    }
    setGuidanceBusy(true);
    setGuidanceError(null);
    try {
      const res = await resumeGuidance(deriveRunId, opts);
      setGuidanceOpen(false);
      navigate(`/resume/derive/${res.run_id}`);
    } catch (e: unknown) {
      setGuidanceError((e as { message?: string })?.message || "引导操作失败");
    } finally {
      setGuidanceBusy(false);
    }
  }

  return (
    <>
      <div className="space-y-2 text-sm" data-testid="page-control-panel">
        <h3 className="font-medium">页面控制</h3>
        <p>
          目标 {target ?? "—"} 页 · 实际 {actual ?? "—"} 页
        </p>
        {ok ? (
          <p className="text-green-700" data-testid="export-gate-ok">
            页数达标，可导出 PDF
          </p>
        ) : (
          <div
            className="text-destructive space-y-1"
            data-testid="export-gate-deny"
          >
            <p>未达标，禁止最终导出</p>
            <ul className="list-disc pl-4" data-testid="export-gate-blockers">
              {(blockers.length ? blockers : ["page_count_mismatch"]).map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
            {pageMismatch && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setGuidanceOpen(true)}
                data-testid="page-guidance-btn"
              >
                查看引导
              </Button>
            )}
          </div>
        )}
        {guidanceError && <p className="text-xs text-destructive">{guidanceError}</p>}
        {guidanceBusy && <p className="text-xs text-muted-foreground">正在提交引导…</p>}
      </div>
      <DeriveGuidance
        open={guidanceOpen}
        runId={deriveRunId || undefined}
        onClose={() => setGuidanceOpen(false)}
        onContinue={(opts) => void handleGuidanceContinue(opts)}
      />
    </>
  );
}
