import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { promoteToRoot } from "./api";

interface Standard {
  id: string;
  name: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  standards: Standard[];
  onPromoted: (data: Record<string, unknown>) => void;
}

export function PromoteRootDialog({ open, onClose, standards, onPromoted }: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function handlePromote(id: string) {
    setBusyId(id);
    setError(null);
    try {
      const data = await promoteToRoot(id);
      onPromoted(data);
      onClose();
    } catch (e: unknown) {
      setError((e as { message?: string })?.message || "提升失败");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      data-testid="promote-root-dialog"
    >
      <Card className="w-full max-w-md space-y-4 p-6">
        <h2 className="text-lg font-semibold">从已有简历提升为根简历</h2>
        <p className="text-sm text-muted-foreground">
          选择一份标准简历，将其内容复制为根简历（职业素材库）。根简历不受页数限制。
        </p>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {standards.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无可提升的标准简历</p>
        ) : (
          <ul className="space-y-2">
            {standards.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-2 rounded border px-3 py-2"
              >
                <span className="truncate text-sm font-medium">{s.name}</span>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busyId !== null}
                  loading={busyId === s.id}
                  onClick={() => void handlePromote(s.id)}
                >
                  提升
                </Button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose} disabled={busyId !== null}>
            取消
          </Button>
        </div>
      </Card>
    </div>
  );
}
