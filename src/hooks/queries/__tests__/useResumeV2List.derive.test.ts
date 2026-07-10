/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import type { ResumeV2ListItem } from "@/modules/resume/v2/api";

function filterDerived(items: ResumeV2ListItem[]) {
  return items.filter((r) => (r.resume_kind || "standard") === "derived");
}

describe("Resume list derive filter (REQ-056 US5)", () => {
  it("keeps derived items when resume_kind is set", () => {
    const items = [
      { id: "1", name: "Root", slug: "r", resume_kind: "root" as const },
      { id: "2", name: "Der", slug: "d", resume_kind: "derived" as const },
      { id: "3", name: "Std", slug: "s", resume_kind: "standard" as const },
    ] as ResumeV2ListItem[];
    expect(filterDerived(items)).toHaveLength(1);
    expect(filterDerived(items)[0].id).toBe("2");
  });
});
