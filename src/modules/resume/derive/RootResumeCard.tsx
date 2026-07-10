import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { createRootResume, getRootResume } from "./api";
import { PromoteRootDialog } from "./PromoteRootDialog";

interface Props {
  standardResumes?: Array<{ id: string; name: string }>;
}

export function RootResumeCard({ standardResumes = [] }: Props) {
  const [root, setRoot] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [promoteOpen, setPromoteOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getRootResume();
        if (!cancelled) setRoot(data);
      } catch (e: unknown) {
        const status = (e as { status?: number })?.status;
        if (!cancelled) {
          setRoot(null);
          if (status !== 404) setError("无法加载根简历");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreate() {
    setBusy(true);
    setError(null);
    try {
      const data = await createRootResume({
        name: "根简历（职业素材库）",
        slug: `root-${Date.now().toString(36)}`,
      });
      setRoot(data);
      setLoading(false);
    } catch (e: unknown) {
      const msg = (e as { message?: string })?.message || "创建失败";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <Card className="p-4" data-testid="root-resume-loading">
        <p className="text-sm text-muted-foreground">加载根简历…</p>
      </Card>
    );
  }

  if (!root) {
    return (
      <>
        <Card className="p-4 space-y-3 border-dashed" data-testid="root-resume-empty">
          <h2 className="text-lg font-semibold">根简历（职业素材库）</h2>
          <p className="text-sm text-muted-foreground">
            根简历可很长，不受 1/2/3 页限制。先沉淀全部真实素材，再按岗位一键派生。
          </p>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button onClick={handleCreate} disabled={busy} data-testid="create-root-btn">
              创建根简历
            </Button>
            {standardResumes.length > 0 && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => setPromoteOpen(true)}
                data-testid="promote-root-open-btn"
              >
                从已有简历提升
              </Button>
            )}
            {standardResumes.slice(0, 3).map((r) => (
              <Button
                key={r.id}
                variant="secondary"
                disabled={busy}
                onClick={() => setPromoteOpen(true)}
              >
                从「{r.name}」提升
              </Button>
            ))}
          </div>
        </Card>
        <PromoteRootDialog
          open={promoteOpen}
          onClose={() => setPromoteOpen(false)}
          standards={standardResumes}
          onPromoted={(data) => {
            setRoot(data);
            setLoading(false);
          }}
        />
      </>
    );
  }

  const completeness = (root.data as { metadata?: { rootCompleteness?: unknown } })
    ?.metadata?.rootCompleteness;

  return (
    <Card className="p-4 space-y-2" data-testid="root-resume-card">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">根简历</p>
          <h2 className="text-lg font-semibold">{String(root.name)}</h2>
        </div>
        <Link
          to={`/resume/${String(root.id)}`}
          className="btn-primary btn-md inline-flex items-center rounded px-3 py-2 text-sm"
        >
          编辑素材库
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">
        不受投递页数限制 · 版本 {String(root.version)}
        {completeness ? " · 已生成完整度提示（非强制评分）" : ""}
      </p>
    </Card>
  );
}
