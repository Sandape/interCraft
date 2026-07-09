// REQ-034 US5 — PublicationsDialog tests.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../PublicationsDialog");
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
    id: "p1",
    hidden: false,
    title: "A Study of Resumes",
    publisher: "arXiv",
    date: "2024-05",
    website: { url: "https://arxiv.org/abs/...", label: "arXiv", inlineLink: true },
    description: "<p>Paper.</p>",
    ...fields,
  };
}

describe("PublicationsDialog (AC-08, R2: date field, AC-16, AC-19)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders all 7+3 input testids (AC-08) — uses `date` field (R2)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.publications.items = [seedSingle()];
      });
    });
    const { PublicationsDialog } = await importDialog();
    render(
      <PublicationsDialog
        onClose={() => {}}
        sectionId="publications"
        itemId="p1"
      />,
    );
    expect(screen.getByTestId("publications-title")).toBeTruthy();
    expect(screen.getByTestId("publications-publisher")).toBeTruthy();
    expect(screen.getByTestId("publications-date")).toBeTruthy();
    expect(screen.getByTestId("publications-website-url")).toBeTruthy();
    expect(screen.getByTestId("publications-website-label")).toBeTruthy();
    expect(screen.getByTestId("publications-website-inline-link")).toBeTruthy();
    expect(screen.getByTestId("publications-hidden")).toBeTruthy();
    expect(screen.getByTestId("publications-description-wrap")).toBeTruthy();
    // R2: NO release-date field (use `date`)
    expect(screen.queryByTestId("publications-release-date")).toBeNull();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.publications.items = [seedSingle()];
      });
    });
    const { PublicationsDialog } = await importDialog();
    render(
      <PublicationsDialog
        onClose={() => {}}
        sectionId="publications"
        itemId="p1"
      />,
    );
    expect(
      (screen.getByTestId("publications-title") as HTMLInputElement).value,
    ).toBe("A Study of Resumes");
    expect((screen.getByTestId("publications-date") as HTMLInputElement).value).toBe(
      "2024-05",
    );
  });

  it("URL scheme whitelist (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.publications.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { PublicationsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(
      <PublicationsDialog
        onClose={() => {}}
        sectionId="publications"
        itemId="p1"
      />,
    );
    const urlInput = screen.getByTestId("publications-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "tel:+86-010-1234" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).not.toHaveBeenCalledWith(expect.any(String), "warn");
    expect(
      useResumeV2Store.getState().data.sections.publications.items[0].website.url,
    ).toBe("tel:+86-010-1234");
  });

  it("URL scheme blacklist rejects file: (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.publications.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { PublicationsDialog } = await importDialog();
    render(
      <PublicationsDialog
        onClose={() => {}}
        sectionId="publications"
        itemId="p1"
      />,
    );
    const urlInput = screen.getByTestId("publications-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "file:///etc/passwd" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("no local draft state — close loops undo to S0 (AC-19, AC-20)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.publications.items = [seedSingle()];
      });
    });
    const { useResumeV2Store } = await importStore();
    const S0 = JSON.parse(JSON.stringify(useResumeV2Store.getState().data));
    const { PublicationsDialog } = await importDialog();
    render(
      <PublicationsDialog
        onClose={() => {}}
        sectionId="publications"
        itemId="p1"
      />,
    );
    fireEvent.change(screen.getByTestId("publications-title"), {
      target: { value: "X" },
    });
    fireEvent.change(screen.getByTestId("publications-publisher"), {
      target: { value: "Y" },
    });
    fireEvent.change(screen.getByTestId("publications-date"), {
      target: { value: "Z" },
    });
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
        d.sections.publications.items = [seedSingle()];
      });
    });
    const { PublicationsDialog } = await importDialog();
    render(
      <PublicationsDialog
        onClose={() => {}}
        sectionId="publications"
        itemId="p1"
      />,
    );
    const payload = "<img src=x onerror=alert(1)>";
    fireEvent.change(screen.getByTestId("publications-title"), {
      target: { value: payload },
    });
    const inp = screen.getByTestId("publications-title") as HTMLInputElement;
    expect(inp.value).toBe(payload);
  });
});
