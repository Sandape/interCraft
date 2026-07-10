import { Loader2, Copy, Trash2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { timeAgo } from "@/lib/utils";

export interface DerivedResumeItem {
  id: string;
  name: string;
  job_id?: string | null;
  target_page_count?: number | null;
  actual_page_count?: number | null;
  updated_at?: string | null;
}

interface Props {
  items: DerivedResumeItem[];
  onDuplicate?: (id: string) => void;
  onDelete?: (id: string) => void;
  onOpen?: (id: string) => void;
  duplicatingId?: string | null;
  deletingId?: string | null;
}

export function DerivedResumeList({
  items,
  onDuplicate,
  onDelete,
  onOpen,
  duplicatingId,
  deletingId,
}: Props) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="derived-resume-list">
        暂无派生简历
      </p>
    );
  }

  return (
    <ul className="space-y-2" data-testid="derived-resume-list">
      {items.map((item) => (
        <li key={item.id}>
          <Card className="flex flex-wrap items-center justify-between gap-2 p-3">
            <div className="min-w-0">
              <div className="font-medium truncate">{item.name}</div>
              <div className="text-xs text-muted-foreground">
                目标 {item.target_page_count ?? "—"} 页 · 实际{" "}
                {item.actual_page_count ?? "—"} 页
                {item.updated_at ? ` · ${timeAgo(item.updated_at)}` : ""}
              </div>
            </div>
            <div className="flex flex-wrap gap-1">
              {onOpen && (
                <Button
                  size="sm"
                  variant="secondary"
                  leftIcon={<ExternalLink className="h-3 w-3" />}
                  onClick={() => onOpen(item.id)}
                  data-testid="derived-resume-open"
                >
                  打开
                </Button>
              )}
              {onDuplicate && (
                <Button
                  size="sm"
                  variant="secondary"
                  leftIcon={
                    duplicatingId === item.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )
                  }
                  disabled={duplicatingId === item.id}
                  onClick={() => onDuplicate(item.id)}
                  data-testid="derived-resume-duplicate"
                >
                  复制
                </Button>
              )}
              {onDelete && (
                <Button
                  size="sm"
                  variant="danger"
                  leftIcon={
                    deletingId === item.id ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Trash2 className="h-3 w-3" />
                    )
                  }
                  disabled={deletingId === item.id}
                  onClick={() => onDelete(item.id)}
                  data-testid="derived-resume-delete"
                >
                  删除
                </Button>
              )}
            </div>
          </Card>
        </li>
      ))}
    </ul>
  );
}
