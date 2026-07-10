import { Button } from "@/components/ui/Button";

interface Props {
  stale: boolean;
  onRegenerate?: () => void;
}

export function StaleRootBanner({ stale, onRegenerate }: Props) {
  if (!stale) return null;
  return (
    <div
      className="mb-3 flex items-center justify-between gap-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm"
      data-testid="stale-root-banner"
    >
      <span>根简历已更新。当前派生仍是旧快照，不会自动同步。</span>
      {onRegenerate && (
        <Button size="sm" variant="secondary" onClick={onRegenerate}>
          基于最新根简历重新生成
        </Button>
      )}
    </div>
  );
}
