import { describe, expect, it } from "vitest";
import { computeTargetPageBudget } from "../target-pages";

describe("target-pages", () => {
  it("budgets content for 1/2/3 pages", () => {
    expect(computeTargetPageBudget(1).maxChars).toBeLessThan(
      computeTargetPageBudget(2).maxChars,
    );
    expect(computeTargetPageBudget(3).maxChars).toBeGreaterThan(
      computeTargetPageBudget(2).maxChars,
    );
  });
});
