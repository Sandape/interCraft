// T151 — AI Analysis settings panel (US14).
//
// Per FR-091a, each "Analyze" click hits DeepSeek V4 Pro fresh — no
// in-memory cache. The backend performs 3× retry (1s/2s/4s) on 429/5xx
// and stores the result via UPSERT into resume_analysis_v2.
//
// Disabled state (T154): when the LLM client is not configured
// (DEEPSEEK_API_KEY missing), the panel shows a "AI provider not
// configured" hint with a link to settings instead of the Analyze
// button.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  Loader2,
  CircleAlert,
  CheckCircle2,
  Lightbulb,
} from "lucide-react";
import {
  analyzeResume,
  getAnalysis,
  type AnalysisResponse,
  type AnalysisItem,
} from "../../api";

export interface AnalysisPanelProps {
  resumeId: string;
  /** True when the resume has any non-empty content (gates the Analyze button). */
  hasContent?: boolean;
  /** True when the LLM client is configured (DEEPSEEK_API_KEY set). */
  llmConfigured?: boolean;
}

const IMPACT_RANK: Record<AnalysisItem["impact"], number> = {
  high: 0,
  medium: 1,
  low: 2,
};

function sortByImpact(items: AnalysisItem[]): AnalysisItem[] {
  return [...items].sort(
    (a, b) =>
      (IMPACT_RANK[a.impact] ?? 9) - (IMPACT_RANK[b.impact] ?? 9),
  );
}

function CircularGauge({
  value,
  size = 96,
}: {
  value: number;
  size?: number;
}): JSX.Element {
  const safe = Math.max(0, Math.min(100, value));
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (safe / 100) * c;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      data-testid="analysis-overall-score"
      data-score={safe}
      className="text-ink-1"
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke="currentColor"
        strokeWidth={stroke}
        fill="none"
        className="text-surface-muted"
        opacity={0.5}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke="currentColor"
        strokeWidth={stroke}
        fill="none"
        strokeDasharray={c}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="text-brand"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-ink-1 text-[18px] font-semibold"
      >
        {safe}
      </text>
    </svg>
  );
}

function DimensionBar({
  name,
  score,
}: {
  name: string;
  score: number;
}): JSX.Element {
  const safe = Math.max(0, Math.min(100, score));
  return (
    <div
      data-testid="analysis-dimension-bar"
      data-dimension={name}
      className="space-y-0.5"
    >
      <div className="flex items-center justify-between text-[10px] text-ink-2">
        <span>{name}</span>
        <span className="tabular-nums text-ink-3">{safe}</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-surface-muted">
        <div
          className="h-full bg-brand"
          style={{ width: `${safe}%` }}
          aria-hidden
        />
      </div>
    </div>
  );
}

export function AnalysisPanel({
  resumeId,
  hasContent = true,
  llmConfigured = true,
}: AnalysisPanelProps): JSX.Element {
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initial fetch — show last result if any
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const res = await getAnalysis(resumeId);
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load analysis.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resumeId]);

  const onAnalyze = async () => {
    if (!hasContent || analyzing) return;
    setAnalyzing(true);
    setError(null);
    try {
      const res = await analyzeResume(resumeId);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyze failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  // T154: disabled state when LLM not configured
  if (!llmConfigured) {
    return (
      <div
        className="space-y-1.5 text-[11px] text-ink-2"
        data-testid="analysis-disabled"
      >
        <div className="flex items-center gap-1 text-amber-600">
          <CircleAlert className="h-3 w-3" />
          <span>AI provider not configured</span>
        </div>
        <p className="text-ink-3">
          Set the <code>DEEPSEEK_API_KEY</code> environment variable to
          enable AI analysis.
        </p>
        <Link
          to="/settings"
          className="inline-flex h-6 items-center rounded border border-surface-border bg-white px-2 text-[10px] text-ink-2 hover:bg-surface-muted"
        >
          Open settings
        </Link>
      </div>
    );
  }

  const a = data?.analysis;
  const isFailed = data?.status === "failed";

  return (
    <div className="space-y-2" data-testid="analysis-panel">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!hasContent || analyzing}
          data-testid="analysis-analyze-button"
          className="inline-flex h-7 items-center gap-1 rounded bg-brand px-2 text-[11px] font-medium text-white hover:bg-brand/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {analyzing ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Sparkles className="h-3 w-3" />
          )}
          {analyzing ? "Analyzing…" : "Analyze"}
        </button>
        {!hasContent && (
          <span className="text-[10px] text-ink-3">
            Add content first
          </span>
        )}
      </div>

      {error && (
        <p
          data-testid="analysis-error"
          className="flex items-center gap-1 text-[10px] text-rose-600"
        >
          <CircleAlert className="h-3 w-3" />
          {error}
        </p>
      )}

      {isFailed && data?.failure_reason && (
        <p
          data-testid="analysis-failure"
          className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-800"
        >
          {data.failure_reason}
        </p>
      )}

      {loading && !data && (
        <p className="flex items-center gap-1 text-[10px] text-ink-3">
          <Loader2 className="h-3 w-3 animate-spin" /> Loading…
        </p>
      )}

      {a && (
        <>
          <div className="flex items-center gap-3 rounded border border-surface-border bg-white px-3 py-2">
            <CircularGauge value={a.overallScore} />
            <div className="flex-1 text-[11px] text-ink-2">
              <div className="font-semibold text-ink-1">
                Overall score
              </div>
              <div className="text-[10px] text-ink-3">
                Based on 10 weighted dimensions
              </div>
            </div>
          </div>

          {a && (
            <div className="space-y-1 rounded border border-surface-border bg-white px-2 py-1.5">
              {(
                a.dimensions && a.dimensions.length > 0
                  ? a.dimensions
                  : Array.from({ length: 10 }, (_, i) => ({
                      name: `维度 ${i + 1}`,
                      score: 0,
                    }))
              ).map((d, i) => (
                <DimensionBar
                  key={`${d.name}-${i}`}
                  name={d.name}
                  score={d.score}
                />
              ))}
            </div>
          )}

          {a && (
            <div className="rounded border border-surface-border bg-white px-2 py-1.5">
              <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-ink-3">
                <CheckCircle2 className="h-3 w-3" /> Strengths
              </div>
              <ul className="space-y-1.5 text-[11px]">
                {(
                  a.strengths && a.strengths.length > 0
                    ? sortByImpact(a.strengths)
                    : Array.from({ length: 3 }, (_, i) => ({
                        impact: "low" as const,
                        text: `优势 ${i + 1}`,
                        why: "",
                        exampleRewrite: "",
                      }))
                ).map((s, i) => (
                  <li
                    key={`str-${i}`}
                    data-testid="analysis-strength"
                    data-impact={s.impact}
                    className="space-y-0.5"
                  >
                    <div className="font-medium text-ink-1">
                      <span
                        className={
                          s.impact === "high"
                            ? "text-emerald-600"
                            : s.impact === "medium"
                              ? "text-amber-600"
                              : "text-ink-3"
                        }
                      >
                        [{s.impact}]
                      </span>{" "}
                      {s.text}
                    </div>
                    {s.why && (
                      <div className="text-[10px] text-ink-3">{s.why}</div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {a && (
            <div className="rounded border border-surface-border bg-white px-2 py-1.5">
              <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-ink-3">
                <Lightbulb className="h-3 w-3" /> Suggestions
              </div>
              <ul className="space-y-2 text-[11px]">
                {(
                  a.suggestions && a.suggestions.length > 0
                    ? sortByImpact(a.suggestions)
                    : Array.from({ length: 3 }, (_, i) => ({
                        impact: "low" as const,
                        text: `建议 ${i + 1}`,
                        why: "",
                        exampleRewrite: "",
                      }))
                ).map((s, i) => (
                  <li
                    key={`sug-${i}`}
                    data-testid="analysis-suggestion"
                    data-impact={s.impact}
                    className="space-y-0.5"
                  >
                    <div className="font-medium text-ink-1">
                      <span
                        className={
                          s.impact === "high"
                            ? "text-rose-600"
                            : s.impact === "medium"
                              ? "text-amber-600"
                              : "text-ink-3"
                        }
                      >
                        [{s.impact}]
                      </span>{" "}
                      {s.text}
                    </div>
                    {s.why && (
                      <div className="text-[10px] text-ink-3">{s.why}</div>
                    )}
                    {s.exampleRewrite && (
                      <div className="rounded bg-surface-muted px-1.5 py-0.5 text-[10px] text-ink-2">
                        <span className="text-ink-3">重写: </span>
                        {s.exampleRewrite}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
