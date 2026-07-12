import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FeedbackControl } from "../FeedbackControl";

describe("FeedbackControl", () => {
  it("submits category feedback without requiring free text", () => {
    const onSubmit = vi.fn();
    render(<FeedbackControl analysisId="a1" suggestionId="s1" onSubmit={onSubmit} />);

    fireEvent.click(screen.getByLabelText("事实有误"));
    fireEvent.click(screen.getByRole("button", { name: "提交反馈" }));

    expect(onSubmit).toHaveBeenCalledWith({
      analysis_id: "a1",
      suggestion_id: "s1",
      change_set_id: null,
      category: "fact_error",
      comment: null,
    });
    expect(screen.getByRole("status")).toHaveTextContent("事实有误");
  });

  it("accepts an optional privacy-safe comment", () => {
    const onSubmit = vi.fn();
    render(<FeedbackControl analysisId="a1" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("可选说明"), { target: { value: "这条建议重复出现" } });
    fireEvent.click(screen.getByLabelText("重复"));
    fireEvent.click(screen.getByRole("button", { name: "提交反馈" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      category: "repeated",
      comment: "这条建议重复出现",
    }));
  });
});
