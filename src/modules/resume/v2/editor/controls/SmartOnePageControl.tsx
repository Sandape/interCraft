import type {
  LineHeightPreset,
  SmartOnePageStatus,
} from "@/modules/resume/renderer/types";

export interface SmartOnePageControlProps {
  enabled: boolean;
  status: SmartOnePageStatus;
  selectedLineHeight: LineHeightPreset | null;
  onEnable: () => void;
  onDisable: () => void;
}

function statusText(status: SmartOnePageStatus, selectedLineHeight: LineHeightPreset | null): string {
  if (status === "already-fit") {
    return selectedLineHeight ? `已适配一页，行距 ${selectedLineHeight}` : "已适配一页";
  }
  if (status === "fit") {
    return selectedLineHeight ? `已压缩到一页，行距 ${selectedLineHeight}` : "已压缩到一页";
  }
  if (status === "infeasible") return "无法压缩到一页，内容已完整保留";
  return "关闭";
}

export function SmartOnePageControl({
  enabled,
  status,
  selectedLineHeight,
  onEnable,
  onDisable,
}: SmartOnePageControlProps) {
  return (
    <div className="flex items-center gap-2 text-xs text-ink-2">
      <button
        type="button"
        data-testid="smart-one-page-toggle"
        aria-pressed={enabled}
        onClick={enabled ? onDisable : onEnable}
        className={[
          "h-8 rounded border px-3 text-xs font-medium transition-colors",
          enabled
            ? "border-primary-500 bg-primary-50 text-primary-700"
            : "border-surface-border bg-white text-ink-1 hover:bg-surface-muted",
        ].join(" ")}
      >
        智能一页
      </button>
      <span
        data-testid="smart-one-page-status"
        className="min-w-[9rem] text-[11px] text-ink-3"
      >
        {statusText(status, selectedLineHeight)}
      </span>
    </div>
  );
}
