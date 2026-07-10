import { useState } from "react";
import { SuggestionPanel } from "./SuggestionPanel";
import { TakeawayPanel } from "./TakeawayPanel";
import { UnusedMaterialsPanel } from "./UnusedMaterialsPanel";
import { JdFitPanel } from "./JdFitPanel";
import { PageControlPanel } from "./PageControlPanel";
import { SupplementPanel } from "./SupplementPanel";
import { StaleRootBanner } from "./StaleRootBanner";
import type { ResumeKind } from "./api";

type TabId = "suggestions" | "rationale" | "jd" | "pages" | "supplement";

const TABS: { id: TabId; label: string }[] = [
  { id: "suggestions", label: "建议" },
  { id: "rationale", label: "依据" },
  { id: "jd", label: "JD匹配" },
  { id: "pages", label: "页数" },
  { id: "supplement", label: "补充" },
];

interface Props {
  resumeId: string;
  resumeKind: ResumeKind | string;
  targetPageCount?: number | null;
  actualPageCount?: number | null;
  rootVersionAtDerive?: number | null;
  rootVersion?: number | null;
  jobId?: string | null;
  onRegenerate?: () => void;
}

export function DeriveWorkbench({
  resumeId,
  resumeKind,
  targetPageCount,
  actualPageCount,
  rootVersionAtDerive,
  rootVersion,
  onRegenerate,
}: Props) {
  const [tab, setTab] = useState<TabId>("suggestions");
  const stale =
    resumeKind === "derived" &&
    rootVersionAtDerive != null &&
    rootVersion != null &&
    rootVersionAtDerive < rootVersion;

  return (
    <aside
      className="border-l border-surface-border bg-surface dark:bg-dark-surface w-80 shrink-0 overflow-y-auto p-4"
      data-testid="derive-workbench"
    >
      <h2 className="text-sm font-semibold mb-3">派生工作台</h2>
      {resumeKind !== "derived" ? (
        <p className="text-sm text-muted-foreground">仅派生简历显示派生辅助面板。</p>
      ) : (
        <>
          <StaleRootBanner stale={stale} onRegenerate={onRegenerate} />
          <div className="flex flex-wrap gap-1 mb-4 border-b pb-2">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`rounded px-2 py-1 text-xs ${
                  tab === t.id
                    ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15"
                    : "text-muted-foreground hover:bg-muted"
                }`}
                onClick={() => setTab(t.id)}
                data-testid={`derive-tab-${t.id}`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {tab === "suggestions" && <SuggestionPanel resumeId={resumeId} />}
          {tab === "rationale" && (
            <div className="space-y-4">
              <TakeawayPanel resumeId={resumeId} />
              <UnusedMaterialsPanel resumeId={resumeId} />
            </div>
          )}
          {tab === "jd" && <JdFitPanel resumeId={resumeId} />}
          {tab === "pages" && (
            <PageControlPanel
              resumeId={resumeId}
              targetPageCount={targetPageCount}
              actualPageCount={actualPageCount}
            />
          )}
          {tab === "supplement" && <SupplementPanel resumeId={resumeId} />}
        </>
      )}
    </aside>
  );
}
