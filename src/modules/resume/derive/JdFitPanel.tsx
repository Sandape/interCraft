import { useEffect, useState } from "react";
import { getDeriveRationale } from "./api";

interface Props {
  resumeId: string;
}

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.map((x) => String(x)).filter(Boolean);
}

function keywordInPlanEntries(
  kw: string,
  entries: unknown[],
): boolean {
  return entries.some((e) => {
    if (!e || typeof e !== "object") return false;
    const row = e as { ref?: string; item?: unknown };
    const blob = `${row.ref || ""} ${JSON.stringify(row.item || "")}`.toLowerCase();
    return blob.includes(kw.toLowerCase());
  });
}

export function JdFitPanel({ resumeId }: Props) {
  const [covered, setCovered] = useState<string[]>([]);
  const [weak, setWeak] = useState<string[]>([]);
  const [missing, setMissing] = useState<string[]>([]);

  useEffect(() => {
    getDeriveRationale(resumeId)
      .then((r) => {
        const jd = r.jd_parse || {};
        const plan = r.selection_plan || {};
        const present = asStringArray(jd.evidence_present);
        const absent = asStringArray(jd.evidence_missing);
        const high = new Set(asStringArray(jd.priority_high));
        const mid = asStringArray(jd.priority_mid);
        const included = Array.isArray(plan.included) ? plan.included : [];
        const compressed = Array.isArray(plan.compressed) ? plan.compressed : [];

        const weakKw = mid.filter(
          (kw) =>
            present.includes(kw) &&
            !high.has(kw) &&
            keywordInPlanEntries(kw, compressed) &&
            !keywordInPlanEntries(kw, included),
        );

        setCovered(present);
        setWeak(weakKw);
        setMissing(absent);
      })
      .catch(() => {
        setCovered([]);
        setWeak([]);
        setMissing([]);
      });
  }, [resumeId]);

  function KeywordGroup({ title, items, tone }: { title: string; items: string[]; tone: string }) {
    return (
      <div className="space-y-1">
        <h4 className={`text-xs font-semibold uppercase tracking-wide ${tone}`}>{title}</h4>
        {items.length === 0 ? (
          <p className="text-muted-foreground text-xs">无</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {items.map((k) => (
              <span key={k} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {k}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm" data-testid="jd-fit-panel">
      <h3 className="font-medium">JD 关键词匹配</h3>
      <p className="text-xs text-muted-foreground">按覆盖程度分组，不展示数值评分。</p>
      <KeywordGroup title="已覆盖" items={covered} tone="text-green-700" />
      <KeywordGroup title="待加强" items={weak} tone="text-amber-700" />
      <KeywordGroup title="缺失" items={missing} tone="text-destructive" />
    </div>
  );
}
