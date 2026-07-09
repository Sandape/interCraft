// REQ-034 US5 — LanguageDialog tests.
//
// Covers AC-04 (R1: 4 input testids, NO keywords),
// AC-10/AC-15 (level slider 0..5 + Hidden label),
// AC-19 (close loops undo to S0),
// AC-20 (no local draft state),
// AC-18 (XSS escaping).

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../LanguageDialog");
const importStore = async () => await import("../../../store");

async function resetStore(
  setup?: (m: Awaited<ReturnType<typeof importStore>>) => void,
) {
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
    id: "l1",
    hidden: false,
    language: "English",
    fluency: "Fluent",
    level: 4,
    ...fields,
  };
}

describe("LanguageDialog (AC-04, AC-15, AC-18, AC-19, AC-20)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders all 4 input testids (AC-04, R1) — no keywords", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.languages.items = [seedSingle()];
      });
    });
    const { LanguageDialog } = await importDialog();
    render(<LanguageDialog onClose={() => {}} sectionId="languages" itemId="l1" />);
    expect(screen.getByTestId("languages-language")).toBeTruthy();
    expect(screen.getByTestId("languages-fluency")).toBeTruthy();
    expect(screen.getByTestId("languages-level")).toBeTruthy();
    expect(screen.getByTestId("languages-hidden")).toBeTruthy();
    // R1: NO keywords field
    expect(screen.queryByTestId("languages-keywords-add")).toBeNull();
    expect(screen.queryByTestId("languages-keywords")).toBeNull();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.languages.items = [seedSingle()];
      });
    });
    const { LanguageDialog } = await importDialog();
    render(<LanguageDialog onClose={() => {}} sectionId="languages" itemId="l1" />);
    expect((screen.getByTestId("languages-language") as HTMLInputElement).value).toBe(
      "English",
    );
    expect((screen.getByTestId("languages-fluency") as HTMLInputElement).value).toBe(
      "Fluent",
    );
    const slider = screen.getByTestId("languages-level") as HTMLInputElement;
    expect(Number(slider.value)).toBe(4);
    expect(screen.getByTestId("languages-level-label").textContent).toBe("4 / 5");
  });

  it("level=0 displays 'Hidden', level=3 displays '3 / 5' (AC-15, R3 + R15)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.languages.items = [seedSingle({ level: 0 })];
      });
    });
    const { LanguageDialog } = await importDialog();
    render(<LanguageDialog onClose={() => {}} sectionId="languages" itemId="l1" />);
    expect(screen.getByTestId("languages-level-label").textContent).toBe("Hidden");
    const slider = screen.getByTestId("languages-level") as HTMLInputElement;
    expect(Number(slider.value)).toBe(0);
    // R15: level=0 still writes to store (independent of hidden field)
    act(() => {
      fireEvent.change(slider, { target: { value: "3" } });
    });
    expect(screen.getByTestId("languages-level-label").textContent).toBe("3 / 5");
  });

  it("non-integer level input is rejected with red border + toast", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.languages.items = [seedSingle({ level: 3 })];
      });
    });
    const { LanguageDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<LanguageDialog onClose={() => {}} sectionId="languages" itemId="l1" />);
    const input = screen.getByTestId("languages-level-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "3.7" } });
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
    // level unchanged
    expect(useResumeV2Store.getState().data.sections.languages.items[0].level).toBe(3);
    // error displayed
    expect(screen.getByTestId("languages-level-error")).toBeTruthy();
  });

  it("field edits write to store + undoStack (AC-04)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.languages.items = [seedSingle()];
      });
    });
    const { LanguageDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<LanguageDialog onClose={() => {}} sectionId="languages" itemId="l1" />);
    const initial = useResumeV2Store.getState().undoStack.length;
    fireEvent.change(screen.getByTestId("languages-language"), {
      target: { value: "Spanish" },
    });
    fireEvent.change(screen.getByTestId("languages-fluency"), {
      target: { value: "Native" },
    });
    fireEvent.change(screen.getByTestId("languages-level-input"), {
      target: { value: "2" },
    });
    const item = useResumeV2Store.getState().data.sections.languages.items[0];
    expect(item.language).toBe("Spanish");
    expect(item.fluency).toBe("Native");
    expect(item.level).toBe(2);
    expect(useResumeV2Store.getState().undoStack.length).toBeGreaterThan(initial);
  });

  it("no local draft state — close loops undo to S0 (AC-19, AC-20)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.languages.items = [seedSingle()];
      });
    });
    const { useResumeV2Store } = await importStore();
    const S0 = JSON.parse(
      JSON.stringify(useResumeV2Store.getState().data),
    );
    const { LanguageDialog } = await importDialog();
    render(<LanguageDialog onClose={() => {}} sectionId="languages" itemId="l1" />);
    fireEvent.change(screen.getByTestId("languages-language"), {
      target: { value: "X" },
    });
    fireEvent.change(screen.getByTestId("languages-fluency"), {
      target: { value: "Y" },
    });
    fireEvent.change(screen.getByTestId("languages-level-input"), {
      target: { value: "5" },
    });
    // Simulate DialogHost close = loops undo until data deep equals S0
    const state = useResumeV2Store.getState();
    let depth = state.undoStack.length;
    while (depth > 0) {
      state.undo();
      depth -= 1;
      const cur = useResumeV2Store.getState().data;
      if (JSON.stringify(cur) === JSON.stringify(S0)) break;
    }
    expect(useResumeV2Store.getState().data).toEqual(S0);
  });

  it("XSS payloads escaped (AC-18)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.languages.items = [seedSingle()];
      });
    });
    const { LanguageDialog } = await importDialog();
    render(<LanguageDialog onClose={() => {}} sectionId="languages" itemId="l1" />);
    const payload = "<script>alert(1)</script>";
    fireEvent.change(screen.getByTestId("languages-language"), {
      target: { value: payload },
    });
    const inp = screen.getByTestId("languages-language") as HTMLInputElement;
    expect(inp.value).toBe(payload);
    // Confirm the rendered text is the payload (no script child)
    expect((inp as HTMLElement).querySelector("script")).toBeNull();
  });
});
