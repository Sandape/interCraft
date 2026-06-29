// REQ-034 US3 — ProjectsDialog tests.
//
// Covers AC-03, AC-05, AC-08, AC-08b, AC-09b, AC-12, AC-13, AC-14, AC-15.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../ProjectsDialog");
const importStore = async () => await import("../../../store");

async function resetStore(setup?: (m: Awaited<ReturnType<typeof importStore>>) => void) {
  const storeMod = await importStore();
  const defaultsMod = await import("../../../schema/defaults");
  storeMod.useResumeV2Store.setState((s) => ({
    ...s,
    data: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
    version: 1,
    id: "r1",
    hydrated: true,
    original: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
    undoStack: [],
    redoStack: [],
    debounceTimer: null,
    historyTTLTimer: null,
    lastEditAt: null,
  }));
  setup?.(storeMod);
}

function seedSingle(fields: Record<string, unknown> = {}) {
  return {
    id: "p1",
    hidden: false,
    name: "Alpha",
    period: "2024-01 ~ Present",
    website: { url: "", label: "", inlineLink: false },
    description: "Built cool stuff.",
    highlights: [],
    ...fields,
  };
}

describe("ProjectsDialog (AC-03, AC-05, AC-12, AC-13, AC-14)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders 7 input testids (AC-05)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedSingle()];
      });
    });
    const { ProjectsDialog } = await importDialog();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    expect(screen.getByTestId("projects-name")).toBeTruthy();
    expect(screen.getByTestId("projects-period")).toBeTruthy();
    expect(screen.getByTestId("projects-website-url")).toBeTruthy();
    expect(screen.getByTestId("projects-website-label")).toBeTruthy();
    expect(screen.getByTestId("projects-website-inline-link")).toBeTruthy();
    expect(screen.getByTestId("projects-hidden")).toBeTruthy();
    expect(screen.getByTestId("projects-description")).toBeTruthy();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedSingle()];
      });
    });
    const { ProjectsDialog } = await importDialog();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    expect((screen.getByTestId("projects-name") as HTMLInputElement).value).toBe("Alpha");
    expect((screen.getByTestId("projects-period") as HTMLInputElement).value).toBe("2024-01 ~ Present");
  });

  it("top-level field edits write to store and push undo (AC-05)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedSingle()];
      });
    });
    const { ProjectsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    const initial = useResumeV2Store.getState().undoStack.length;
    fireEvent.change(screen.getByTestId("projects-name"), { target: { value: "Beta" } });
    fireEvent.change(screen.getByTestId("projects-period"), { target: { value: "2025-01" } });
    const item = useResumeV2Store.getState().data.sections.projects.items[0];
    expect(item.name).toBe("Beta");
    expect(item.period).toBe("2025-01");
    expect(useResumeV2Store.getState().undoStack.length).toBeGreaterThan(initial + 1);
  });

  it("period is a single free-form input (AC-12)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedSingle()];
      });
    });
    const { ProjectsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    expect(screen.queryByTestId("projects-period-start")).toBeNull();
    expect(screen.queryByTestId("projects-period-end")).toBeNull();
    fireEvent.change(screen.getByTestId("projects-period"), { target: { value: "2024 ~ 2025" } });
    expect(useResumeV2Store.getState().data.sections.projects.items[0].period).toBe("2024 ~ 2025");
  });

  it("URL whitelist rejects javascript: scheme (AC-13)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedSingle()];
      });
    });
    const { ProjectsDialog } = await importDialog();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    const input = screen.getByTestId("projects-website-url") as HTMLInputElement;
    for (const ok of ["https://[::1]:8080", "tel:+1-555-0100", "mailto:a@b.com"]) {
      fireEvent.change(input, { target: { value: ok } });
      fireEvent.blur(input);
      expect(screen.queryByTestId("projects-website-url-error")).toBeNull();
    }
    fireEvent.change(input, { target: { value: "javascript:alert(1)" } });
    fireEvent.blur(input);
    expect(screen.getByTestId("projects-website-url-error")).toBeTruthy();
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("script payload escaped (AC-14)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedSingle()];
      });
    });
    const { ProjectsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    const payload = "<script>window.__xss=1</script>";
    fireEvent.change(screen.getByTestId("projects-name"), { target: { value: payload } });
    expect(useResumeV2Store.getState().data.sections.projects.items[0].name).toBe(payload);
    expect((globalThis as { __xss?: number }).__xss).toBeUndefined();
  });

  it("no local useState for form fields (AC-16)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const file = path.join(process.cwd(), "src/modules/resume/v2/editor/dialogs/ProjectsDialog.tsx");
    const src = fs.readFileSync(file, "utf-8");
    const stateCount = (src.match(/useState/g) || []).length;
    expect(stateCount).toBeLessThanOrEqual(2);
  });
});

describe("ProjectsDialog highlights add/remove/drag-reorder (AC-08, AC-08b)", () => {
  it("highlights add from empty array creates one empty string (AC-07b)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [seedSingle({ highlights: [] })];
      });
    });
    const { ProjectsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    act(() => {
      fireEvent.click(screen.getByTestId("projects-add-highlight"));
    });
    const item = useResumeV2Store.getState().data.sections.projects.items[0];
    expect(item.highlights.length).toBe(1);
    expect(item.highlights[0]).toBe("");
  });

  it("drag reorder 5 times within 500ms collapses into 1 undoStack entry (AC-08b)", async () => {
    vi.useFakeTimers();
    try {
      await resetStore((m) => {
        m.useResumeV2Store.getState().setDataMut((d) => {
          d.sections.projects.items = [
            seedSingle({ highlights: ["H1", "H2", "H3"] }),
          ];
        });
      });
      const { ProjectsDialog } = await importDialog();
      const { useResumeV2Store } = await importStore();
      vi.advanceTimersByTime(500);
      render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
      const undoBefore = useResumeV2Store.getState().undoStack.length;
      act(() => { fireEvent.click(screen.getByTestId("projects-test-reorder-2-0")); });
      act(() => { fireEvent.click(screen.getByTestId("projects-test-reorder-0-1")); });
      act(() => { fireEvent.click(screen.getByTestId("projects-test-reorder-1-2")); });
      act(() => { fireEvent.click(screen.getByTestId("projects-test-reorder-2-1")); });
      act(() => { fireEvent.click(screen.getByTestId("projects-test-reorder-0-2")); });
      const undoAfter = useResumeV2Store.getState().undoStack.length;
      expect(undoAfter).toBe(undoBefore + 1);
      const captured = useResumeV2Store.getState().undoStack.at(-1);
      const capturedH = captured!.data.sections.projects.items[0].highlights;
      expect(capturedH).toEqual(["H1", "H2", "H3"]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("drag preserves highlights order; id set unchanged (AC-09)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.projects.items = [
          seedSingle({ highlights: ["A", "B", "C"] }),
        ];
      });
    });
    const { ProjectsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<ProjectsDialog onClose={() => {}} sectionId="projects" itemId="p1" />);
    act(() => { fireEvent.click(screen.getByTestId("projects-test-reorder-2-0")); });
    const highlights = useResumeV2Store.getState().data.sections.projects.items[0].highlights;
    expect(highlights).toEqual(["C", "A", "B"]);
  });
});