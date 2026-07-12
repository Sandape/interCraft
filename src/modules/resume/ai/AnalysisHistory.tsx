import { useMemo, useState } from "react";
import { AlertTriangle, History, RotateCcw } from "lucide-react";
import type { ResumeAnalysis, ResumeAnalysisComparison } from "./types";

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function AnalysisHistory({
  analyses,
  currentAnalysisId,
  comparison,
  onRefresh,
  onCompare,
  refreshing = false,
  comparing = false,
}: {
  analyses: ResumeAnalysis[];
  currentAnalysisId?: string | null;
  comparison?: ResumeAnalysisComparison | null;
  onRefresh: () => void;
  onCompare?: (beforeAnalysisId: string, afterAnalysisId: string) => void;
  refreshing?: boolean;
  comparing?: boolean;
}) {
  const current = useMemo(
    () => analyses.find((item) => item.id === currentAnalysisId) ?? analyses[0] ?? null,
    [analyses, currentAnalysisId],
  );
  const [selectedBefore, setSelectedBefore] = useState<string>("");
  const staleReasons = current?.stale_reasons ?? [];

  return (
    <section className="space-y-4" data-testid="analysis-history">
      {current?.is_stale && (
        <div className="border border-[#d9a58f] bg-[#fff7f2] p-4" role="alert" aria-live="polite">
          <div className="flex items-start gap-2 text-sm font-medium text-[#853f28]">
            <AlertTriangle className="mt-0.5 h-4 w-4" />
            当前分析已基于旧版本
          </div>
          <p className="mt-2 text-xs leading-5 text-[#734d3e]">
            原因：{staleReasons.length > 0 ? staleReasons.join("、") : "简历或岗位上下文已变化"}。旧结果保留为历史，不再作为当前结论。
          </p>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="mt-3 inline-flex min-h-10 items-center gap-2 bg-[#20211f] px-4 text-xs font-medium text-white disabled:opacity-40"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            基于最新版本重新分析
          </button>
        </div>
      )}

      <div className="flex items-center gap-2 text-sm font-semibold text-[#262724]">
        <History className="h-4 w-4 text-[#8b4d31]" />
        分析历史
      </div>

      <ol className="divide-y divide-[#d7d2c7] border-y border-[#d7d2c7]" aria-label="分析历史时间线">
        {analyses.map((item) => (
          <li key={item.id} className="py-3">
            <label className="flex items-start gap-3">
              <input
                type="radio"
                name="history-before"
                value={item.id}
                checked={selectedBefore === item.id}
                onChange={() => setSelectedBefore(item.id)}
                className="mt-1 accent-[#8b4d31]"
                aria-label={`选择 v${item.resume_version} ${formatDate(item.created_at)} 作为比较基准`}
              />
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-[#30312e]">
                  {item.mode === "job_fit" ? "岗位定制分析" : "通用体检"}
                  {item.id === current?.id ? " · 当前" : ""}
                </span>
                <span className="mt-1 block text-xs text-[#77786f]">
                  v{item.resume_version} · {formatDate(item.created_at)}
                </span>
              </span>
              <span className={item.is_stale ? "text-xs text-[#a75132]" : "text-xs text-[#557a5a]"}>
                {item.is_stale ? "已过期" : item.status}
              </span>
            </label>
          </li>
        ))}
        {analyses.length === 0 && <li className="py-4 text-xs text-[#77786f]">暂无历史分析。</li>}
      </ol>

      {current && onCompare && (
        <button
          type="button"
          onClick={() => selectedBefore && onCompare(selectedBefore, current.id)}
          disabled={!selectedBefore || selectedBefore === current.id || comparing}
          className="min-h-10 border border-[#403f39] px-4 text-xs font-medium text-[#2a2b28] disabled:opacity-40"
        >
          比较所选历史与当前
        </button>
      )}

      {comparison && (
        <section className="border border-[#c9c2b5] bg-white p-4" aria-label="分析前后比较" aria-live="polite">
          <h3 className="text-sm font-semibold text-[#262724]">前后比较</h3>
          <p className="mt-2 text-xs text-[#686961]">
            总体变化：{comparison.overall_delta == null ? "暂无分数变化" : `${comparison.overall_delta > 0 ? "+" : ""}${comparison.overall_delta}`}
          </p>
          <div className="mt-3 space-y-2">
            {comparison.dimension_deltas.map((item) => (
              <div key={item.key} className="flex justify-between gap-3 text-xs">
                <span className="text-[#3b3c38]">{item.key.replaceAll("_", " ")}</span>
                <span className="tabular-nums text-[#20211f]">
                  {item.before_score ?? "—"} → {item.after_score ?? "—"} ({item.delta == null ? "—" : `${item.delta > 0 ? "+" : ""}${item.delta}`})
                </span>
              </div>
            ))}
          </div>
          <div className="mt-4 grid gap-3 text-xs md:grid-cols-2">
            <div>
              <div className="font-medium text-[#557a5a]">已解决差距</div>
              <div className="mt-1 text-[#686961]">{comparison.resolved_gaps.length} 项</div>
            </div>
            <div>
              <div className="font-medium text-[#a75132]">新增差距</div>
              <div className="mt-1 text-[#686961]">{comparison.new_gaps.length} 项</div>
            </div>
          </div>
        </section>
      )}
    </section>
  );
}
