import { useEffect, useState } from "react";
import { ApiError } from "@/api/errors";
import { Button } from "@/components/ui/Button";
import { useResumeV2Store } from "@/modules/resume/v2/store";
import {
  applySuggestion,
  listSuggestions,
  previewSuggestion,
} from "./api";

interface Suggestion {
  id: string;
  priority?: string;
  type?: string;
  problem?: string;
  apply_mode?: string;
  status?: string;
}

interface Props {
  resumeId: string;
}

export function SuggestionPanel({ resumeId }: Props) {
  const [items, setItems] = useState<Suggestion[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewSummary, setPreviewSummary] = useState<string | null>(null);
  const [previewToken, setPreviewToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const clientVersion = useResumeV2Store((s) => s.version);

  function reload() {
    listSuggestions(resumeId)
      .then((r) => setItems((r.suggestions as unknown as Suggestion[]) || []))
      .catch(() => setItems([]));
  }

  useEffect(() => {
    reload();
  }, [resumeId]);

  async function handlePreview(s: Suggestion) {
    setBusyId(s.id);
    setError(null);
    setPreviewId(null);
    setPreviewSummary(null);
    setPreviewToken(null);
    try {
      const preview = await previewSuggestion(resumeId, {
        suggestion_id: s.id,
        client_version: clientVersion,
      });
      setPreviewId(s.id);
      setPreviewSummary(preview.diff_summary || "变更预览已就绪");
      setPreviewToken(preview.preview_token);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409) {
        setError(e.message || "简历版本冲突，请刷新后重试");
      } else {
        setError((e as { message?: string })?.message || "预览失败");
      }
    } finally {
      setBusyId(null);
    }
  }

  async function handleApply(s: Suggestion) {
    if (!previewToken || previewId !== s.id) {
      setError("请先预览后再采纳");
      return;
    }
    setBusyId(s.id);
    setError(null);
    try {
      await applySuggestion(resumeId, {
        suggestion_id: s.id,
        client_version: clientVersion,
        preview_token: previewToken,
      });
      setPreviewId(null);
      setPreviewSummary(null);
      setPreviewToken(null);
      reload();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409) {
        setError(e.message || "版本冲突或预览已过期，请重新预览");
      } else {
        setError((e as { message?: string })?.message || "采纳失败");
      }
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-3 text-sm" data-testid="suggestion-panel">
      <h3 className="font-medium">AI 优化建议</h3>
      {error && <p className="text-xs text-destructive">{error}</p>}
      {items.length === 0 && (
        <p className="text-muted-foreground">暂无建议</p>
      )}
      {items.map((s) => (
        <div key={s.id} className="rounded border p-2 space-y-1">
          <div className="flex justify-between gap-2">
            <span className="font-medium">{s.type || "suggestion"}</span>
            <span className="text-xs uppercase">{s.priority}</span>
          </div>
          <p>{s.problem}</p>
          <p className="text-xs text-muted-foreground">
            处理方式：{s.apply_mode || "—"}（需确认后生效）
          </p>
          {s.apply_mode === "direct" && (
            <div className="flex flex-wrap gap-2 pt-1">
              <Button
                size="sm"
                variant="secondary"
                loading={busyId === s.id && previewId !== s.id}
                disabled={busyId !== null && busyId !== s.id}
                onClick={() => void handlePreview(s)}
                data-testid={`suggestion-preview-${s.id}`}
              >
                预览
              </Button>
              {previewId === s.id && previewSummary && (
                <>
                  <p
                    className="w-full text-xs text-muted-foreground"
                    data-testid={`suggestion-preview-summary-${s.id}`}
                  >
                    {previewSummary}
                  </p>
                  <Button
                    size="sm"
                    variant="primary"
                    loading={busyId === s.id}
                    onClick={() => void handleApply(s)}
                    data-testid={`suggestion-apply-${s.id}`}
                  >
                    确认采纳
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
