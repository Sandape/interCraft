import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SupplementFactFlow } from "../SupplementFactFlow";
import type { ResumeSuggestion } from "../types";

function suggestion(overrides: Partial<ResumeSuggestion> = {}): ResumeSuggestion {
  return {
    id: "s1",
    analysis_id: "a1",
    base_resume_version: 3,
    kind: "quantify",
    action_mode: "needs_supplement",
    priority: "high",
    title: "补充项目量化结果",
    explanation: "缺少规模与结果，不能直接写入。",
    anchor: { node_id: "exp-1", start: 0, end: 8, context_checksum: "abc" },
    status: "open",
    source_refs: [],
    ...overrides,
  };
}

describe("SupplementFactFlow", () => {
  it("blocks direct apply and submits confirmed facts with scope", () => {
    const onConfirm = vi.fn();
    render(<SupplementFactFlow suggestions={[suggestion()]} onConfirm={onConfirm} />);

    expect(screen.getByText("需要先确认真实信息")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("你的确认事实"), {
      target: { value: "负责 6 人团队，交付周期缩短 20%。" },
    });
    fireEvent.click(screen.getByLabelText("同步回根简历"));
    fireEvent.click(screen.getByRole("button", { name: "确认补充事实" }));

    expect(onConfirm).toHaveBeenCalledWith({
      suggestion_id: "s1",
      answer: "负责 6 人团队，交付周期缩短 20%。",
      scope: "root",
    });
    expect(screen.getByRole("status")).toHaveTextContent("已提交");
  });

  it("shows honest empty state when no supplement is required", () => {
    render(<SupplementFactFlow suggestions={[suggestion({ action_mode: "direct" })]} onConfirm={vi.fn()} />);
    expect(screen.getByText("当前没有需要补充事实的建议")).toBeInTheDocument();
  });
});
