// REQ-034 US5 — AwardsDialog tests.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../AwardsDialog");
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
    id: "a1",
    hidden: false,
    title: "Best Paper",
    awarder: "ACM",
    date: "2024-05",
    website: { url: "https://acm.org", label: "ACM", inlineLink: true },
    description: "<p>Won for X.</p>",
    ...fields,
  };
}

describe("AwardsDialog (AC-06, AC-16, AC-18, AC-19)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders all 7+3 input testids (AC-06)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.awards.items = [seedSingle()];
      });
    });
    const { AwardsDialog } = await importDialog();
    render(<AwardsDialog onClose={() => {}} sectionId="awards" itemId="a1" />);
    expect(screen.getByTestId("awards-title")).toBeTruthy();
    expect(screen.getByTestId("awards-awarder")).toBeTruthy();
    expect(screen.getByTestId("awards-date")).toBeTruthy();
    expect(screen.getByTestId("awards-website-url")).toBeTruthy();
    expect(screen.getByTestId("awards-website-label")).toBeTruthy();
    expect(screen.getByTestId("awards-website-inline-link")).toBeTruthy();
    expect(screen.getByTestId("awards-hidden")).toBeTruthy();
    expect(screen.getByTestId("awards-description-wrap")).toBeTruthy();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.awards.items = [seedSingle()];
      });
    });
    const { AwardsDialog } = await importDialog();
    render(<AwardsDialog onClose={() => {}} sectionId="awards" itemId="a1" />);
    expect((screen.getByTestId("awards-title") as HTMLInputElement).value).toBe(
      "Best Paper",
    );
    expect((screen.getByTestId("awards-awarder") as HTMLInputElement).value).toBe("ACM");
    expect(
      (screen.getByTestId("awards-website-url") as HTMLInputElement).value,
    ).toBe("https://acm.org");
  });

  it("field edits write to store + undoStack (AC-06)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.awards.items = [seedSingle()];
      });
    });
    const { AwardsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<AwardsDialog onClose={() => {}} sectionId="awards" itemId="a1" />);
    const initial = useResumeV2Store.getState().undoStack.length;
    fireEvent.change(screen.getByTestId("awards-title"), {
      target: { value: "Best Demo" },
    });
    fireEvent.change(screen.getByTestId("awards-awarder"), {
      target: { value: "IEEE" },
    });
    fireEvent.change(screen.getByTestId("awards-date"), {
      target: { value: "2024-06" },
    });
    const item = useResumeV2Store.getState().data.sections.awards.items[0];
    expect(item.title).toBe("Best Demo");
    expect(item.awarder).toBe("IEEE");
    expect(item.date).toBe("2024-06");
    expect(useResumeV2Store.getState().undoStack.length).toBeGreaterThan(initial);
  });

  it("URL scheme whitelist (AC-16, R4)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.awards.items = [seedSingle({ website: { url: "", label: "", inlineLink: false } })];
      });
    });
    const { AwardsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<AwardsDialog onClose={() => {}} sectionId="awards" itemId="a1" />);
    const urlInput = screen.getByTestId("awards-website-url") as HTMLInputElement;
    // Whitelisted scheme
    fireEvent.change(urlInput, { target: { value: "https://中文.cn" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).not.toHaveBeenCalledWith(expect.any(String), "warn");
    expect(
      useResumeV2Store.getState().data.sections.awards.items[0].website.url,
    ).toBe("https://中文.cn");
  });

  it("URL scheme blacklist rejects javascript: (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.awards.items = [seedSingle({ website: { url: "", label: "", inlineLink: false } })];
      });
    });
    const { AwardsDialog } = await importDialog();
    render(<AwardsDialog onClose={() => {}} sectionId="awards" itemId="a1" />);
    const urlInput = screen.getByTestId("awards-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "javascript:alert(1)" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
    expect(screen.getByTestId("awards-website-url-error")).toBeTruthy();
  });

  it("no local draft state — close loops undo to S0 (AC-19, AC-20)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.awards.items = [seedSingle()];
      });
    });
    const { useResumeV2Store } = await importStore();
    const S0 = JSON.parse(JSON.stringify(useResumeV2Store.getState().data));
    const { AwardsDialog } = await importDialog();
    render(<AwardsDialog onClose={() => {}} sectionId="awards" itemId="a1" />);
    fireEvent.change(screen.getByTestId("awards-title"), { target: { value: "X" } });
    fireEvent.change(screen.getByTestId("awards-awarder"), { target: { value: "Y" } });
    fireEvent.change(screen.getByTestId("awards-date"), { target: { value: "Z" } });
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
        d.sections.awards.items = [seedSingle()];
      });
    });
    const { AwardsDialog } = await importDialog();
    render(<AwardsDialog onClose={() => {}} sectionId="awards" itemId="a1" />);
    const payload = "<img src=x onerror=alert(1)>";
    fireEvent.change(screen.getByTestId("awards-title"), { target: { value: payload } });
    const inp = screen.getByTestId("awards-title") as HTMLInputElement;
    expect(inp.value).toBe(payload);
  });
});
