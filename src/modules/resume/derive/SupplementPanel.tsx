import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { getDeriveRationale, postSupplements, type SupplementQuestion } from "./api";

interface Props {
  resumeId: string;
  onApplied?: () => void;
}

export function SupplementPanel({ resumeId, onApplied }: Props) {
  const [questions, setQuestions] = useState<SupplementQuestion[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [syncTarget, setSyncTarget] = useState<"derived_only" | "root" | "discard">("derived_only");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getDeriveRationale(resumeId)
      .then((r) => {
        setQuestions(r.supplement_questions || []);
        setPendingCount((r.pending_claims || []).length);
      })
      .catch(() => {
        setQuestions([]);
        setPendingCount(0);
      });
  }, [resumeId]);

  async function handleSubmit() {
    setBusy(true);
    setError(null);
    setMessage(null);
    const payload = questions
      .map((q) => ({
        question_id: q.question_id,
        text: (answers[q.question_id] || "").trim(),
      }))
      .filter((a) => a.text.length > 0);
    if (payload.length === 0) {
      setError("请至少填写一项补充内容");
      setBusy(false);
      return;
    }
    try {
      await postSupplements(resumeId, { answers: payload, sync_target: syncTarget });
      setMessage("补充已提交");
      onApplied?.();
    } catch (e: unknown) {
      setError((e as { message?: string })?.message || "提交失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 text-sm" data-testid="supplement-panel">
      <h3 className="font-medium">补充问题</h3>
      {pendingCount > 0 && (
        <p className="text-xs text-amber-700">尚有 {pendingCount} 项待确认声明，可能影响导出。</p>
      )}
      {questions.length === 0 ? (
        <p className="text-muted-foreground">暂无需要补充的问题</p>
      ) : (
        <div className="space-y-3">
          {questions.map((q) => (
            <label key={q.question_id} className="block space-y-1">
              <span className="text-xs font-medium">{q.text}</span>
              <textarea
                className="w-full rounded border px-2 py-1 text-sm min-h-[4rem]"
                value={answers[q.question_id] || ""}
                onChange={(e) =>
                  setAnswers((prev) => ({ ...prev, [q.question_id]: e.target.value }))
                }
                data-testid={`supplement-answer-${q.question_id}`}
              />
            </label>
          ))}
          <label className="block space-y-1">
            <span className="text-xs font-medium">同步目标</span>
            <select
              className="w-full rounded border px-2 py-1 text-sm"
              value={syncTarget}
              onChange={(e) =>
                setSyncTarget(e.target.value as "derived_only" | "root" | "discard")
              }
              data-testid="supplement-sync-target"
            >
              <option value="derived_only">仅更新派生简历</option>
              <option value="root">同步到根简历</option>
              <option value="discard">放弃补充</option>
            </select>
          </label>
          {error && <p className="text-destructive text-xs">{error}</p>}
          {message && (
            <p className="text-green-700 text-xs" data-testid="supplement-success">
              {message}
            </p>
          )}
          <Button
            size="sm"
            variant="secondary"
            loading={busy}
            onClick={() => void handleSubmit()}
            data-testid="supplement-submit"
          >
            提交补充
          </Button>
        </div>
      )}
    </div>
  );
}
