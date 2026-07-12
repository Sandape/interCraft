import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ResumeSuggestion, SupplementConfirmationInput, SupplementScope } from "./types";

const SCOPE_OPTIONS: Array<{ value: SupplementScope; label: string; hint: string }> = [
  { value: "derived_only", label: "仅当前岗位", hint: "只允许本次派生稿使用，不改根简历" },
  { value: "root", label: "同步回根简历", hint: "写入根简历事实库，并要求重新分析" },
  { value: "discard", label: "暂不使用", hint: "不进入正文、导出或后续建议" },
];

export function SupplementFactFlow({
  suggestions,
  onConfirm,
  confirming = false,
}: {
  suggestions: ResumeSuggestion[];
  onConfirm: (input: SupplementConfirmationInput) => void;
  confirming?: boolean;
}) {
  const blocked = useMemo(
    () => suggestions.filter((item) => item.action_mode === "needs_supplement"),
    [suggestions],
  );
  const [activeId, setActiveId] = useState<string | null>(() => blocked[0]?.id ?? null);
  const [answer, setAnswer] = useState("");
  const [scope, setScope] = useState<SupplementScope>("derived_only");
  const [submitted, setSubmitted] = useState(false);
  const active = blocked.find((item) => item.id === activeId) ?? blocked[0] ?? null;

  if (blocked.length === 0) {
    return (
      <section className="border border-[#d7d2c7] bg-[#fbfaf6] p-4" data-testid="supplement-fact-flow">
        <div className="flex items-start gap-2 text-sm font-medium text-[#2f4f35]">
          <CheckCircle2 className="mt-0.5 h-4 w-4" />
          当前没有需要补充事实的建议
        </div>
        <p className="mt-2 text-xs leading-5 text-[#686961]">AI 不会把未确认的新事实直接写入简历。</p>
      </section>
    );
  }

  const handleSubmit = () => {
    if (!active) return;
    onConfirm({
      suggestion_id: active.id,
      answer: answer.trim(),
      scope,
    });
    setSubmitted(true);
  };

  return (
    <section className="border border-[#d7d2c7] bg-[#fbfaf6] p-4" data-testid="supplement-fact-flow">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 text-[#a75132]" />
        <div>
          <h3 className="text-sm font-semibold text-[#262724]">需要先确认真实信息</h3>
          <p className="mt-1 text-xs leading-5 text-[#686961]">
            这些建议会引入新事实，已阻止直接应用。请回答具体问题并选择作用范围。
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="需要补充事实的建议">
        {blocked.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={(active?.id ?? "") === item.id}
            onClick={() => {
              setActiveId(item.id);
              setAnswer("");
              setSubmitted(false);
            }}
            className={`border px-3 py-1.5 text-xs ${
              (active?.id ?? "") === item.id
                ? "border-[#8b4d31] bg-[#fff7ef] text-[#7f4328]"
                : "border-[#d7d2c7] text-[#676860]"
            }`}
          >
            {item.title}
          </button>
        ))}
      </div>

      {active && (
        <div className="mt-4 space-y-4">
          <div className="border-l-2 border-[#b96a43] pl-3">
            <p className="text-sm font-medium text-[#262724]">{active.title}</p>
            <p className="mt-1 text-xs leading-5 text-[#686961]">{active.explanation}</p>
            <p className="mt-2 text-[11px] text-[#8b4d31]">
              问题：请补充与 {active.anchor?.node_id ?? "对应经历"} 相关的规模、职责、行动或结果。
            </p>
          </div>

          <label className="block text-xs font-medium text-[#3b3c38]" htmlFor="supplement-answer">
            你的确认事实
          </label>
          <textarea
            id="supplement-answer"
            value={answer}
            onChange={(event) => {
              setAnswer(event.target.value);
              setSubmitted(false);
            }}
            className="min-h-24 w-full border border-[#c9c2b5] bg-white p-3 text-sm text-[#262724] outline-none focus:border-[#8b4d31]"
            placeholder="例如：负责 6 人项目组，在 3 个月内将交付周期缩短 20%。"
          />

          <fieldset className="space-y-2">
            <legend className="text-xs font-medium text-[#3b3c38]">作用范围</legend>
            {SCOPE_OPTIONS.map((option) => (
              <label key={option.value} className="flex items-start gap-2 border border-[#e2ded5] bg-white p-3">
                <input
                  type="radio"
                  name="supplement-scope"
                  value={option.value}
                  checked={scope === option.value}
                  onChange={() => setScope(option.value)}
                  aria-label={option.label}
                  className="mt-1 accent-[#8b4d31]"
                />
                <span>
                  <span className="block text-sm font-medium text-[#262724]">{option.label}</span>
                  <span className="mt-0.5 block text-xs text-[#686961]">{option.hint}</span>
                </span>
              </label>
            ))}
          </fieldset>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={confirming || (scope !== "discard" && answer.trim().length === 0)}
            className="min-h-11 bg-[#20211f] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {scope === "discard" ? "不使用此事实" : "确认补充事实"}
          </button>
          {submitted && (
            <p className="text-xs text-[#557a5a]" role="status" aria-live="polite">
              已提交，等待服务端确认后才会进入建议流程。
            </p>
          )}
        </div>
      )}
    </section>
  );
}
