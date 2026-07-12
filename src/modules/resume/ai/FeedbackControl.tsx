import { useState } from "react";
import type { FeedbackCategory } from "./types";

const CATEGORIES: Array<{ value: FeedbackCategory; label: string; risk?: boolean }> = [
  { value: "helpful", label: "有帮助" },
  { value: "not_applicable", label: "不适用" },
  { value: "repeated", label: "重复" },
  { value: "poor_wording", label: "表达不佳" },
  { value: "fact_error", label: "事实有误", risk: true },
  { value: "other", label: "其他" },
];

export function FeedbackControl({
  analysisId,
  suggestionId,
  changeSetId,
  onSubmit,
  submitting = false,
}: {
  analysisId: string;
  suggestionId?: string | null;
  changeSetId?: string | null;
  onSubmit: (input: {
    analysis_id: string;
    suggestion_id?: string | null;
    change_set_id?: string | null;
    category: FeedbackCategory;
    comment?: string | null;
  }) => void;
  submitting?: boolean;
}) {
  const [category, setCategory] = useState<FeedbackCategory>("helpful");
  const [comment, setComment] = useState("");
  const [submittedCategory, setSubmittedCategory] = useState<FeedbackCategory | null>(null);

  const handleSubmit = () => {
    onSubmit({
      analysis_id: analysisId,
      suggestion_id: suggestionId ?? null,
      change_set_id: changeSetId ?? null,
      category,
      comment: comment.trim() || null,
    });
    setSubmittedCategory(category);
  };

  return (
    <section className="border border-[#d7d2c7] bg-[#fbfaf6] p-4" data-testid="feedback-control">
      <h3 className="text-sm font-semibold text-[#262724]">反馈这条建议</h3>
      <p className="mt-1 text-xs leading-5 text-[#686961]">不必填写自由文本，分类反馈即可帮助减少重复或高风险建议。</p>

      <div className="mt-3 grid grid-cols-2 gap-2" role="radiogroup" aria-label="反馈分类">
        {CATEGORIES.map((item) => (
          <label
            key={item.value}
            className={`flex min-h-10 cursor-pointer items-center gap-2 border px-3 text-xs ${
              category === item.value ? "border-[#8b4d31] bg-[#fff7ef] text-[#7f4328]" : "border-[#d7d2c7] bg-white text-[#676860]"
            }`}
          >
            <input
              type="radio"
              name={`feedback-${analysisId}-${suggestionId ?? "analysis"}`}
              value={item.value}
              checked={category === item.value}
              onChange={() => setCategory(item.value)}
              aria-label={item.label}
              className="accent-[#8b4d31]"
            />
            {item.label}
            {item.risk && <span className="ml-auto text-[10px] text-[#a75132]">会阻止直接采纳</span>}
          </label>
        ))}
      </div>

      <label className="mt-4 block text-xs font-medium text-[#3b3c38]" htmlFor={`feedback-comment-${suggestionId ?? analysisId}`}>
        可选说明
      </label>
      <textarea
        id={`feedback-comment-${suggestionId ?? analysisId}`}
        value={comment}
        maxLength={1000}
        onChange={(event) => setComment(event.target.value)}
        className="mt-2 min-h-20 w-full border border-[#c9c2b5] bg-white p-3 text-sm text-[#262724] outline-none focus:border-[#8b4d31]"
        placeholder="可留空；不要粘贴敏感原文。"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="min-h-10 bg-[#20211f] px-4 text-xs font-medium text-white disabled:opacity-40"
        >
          提交反馈
        </button>
        <span className="text-[11px] text-[#77786f]">{comment.length}/1000</span>
      </div>
      {submittedCategory && (
        <p className="mt-3 text-xs text-[#557a5a]" role="status" aria-live="polite">
          已记录“{CATEGORIES.find((item) => item.value === submittedCategory)?.label}”反馈。
        </p>
      )}
    </section>
  );
}
