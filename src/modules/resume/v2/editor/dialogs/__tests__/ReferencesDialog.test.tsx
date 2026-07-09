// REQ-034 US5 — ReferencesDialog tests.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../ReferencesDialog");
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
    id: "ref1",
    hidden: false,
    name: "Dr. Smith",
    position: "Director of Engineering",
    website: { url: "https://smith.io", label: "Smith.io", inlineLink: true },
    phone: "+86-138-0013-8000",
    description: "<p>Reference.</p>",
    ...fields,
  };
}

describe("ReferencesDialog (AC-10, R4: NO email, R10: phone free-form, AC-19)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders 7+3 input testids (AC-10) — NO email (R4)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.references.items = [seedSingle()];
      });
    });
    const { ReferencesDialog } = await importDialog();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    expect(screen.getByTestId("references-name")).toBeTruthy();
    expect(screen.getByTestId("references-position")).toBeTruthy();
    expect(screen.getByTestId("references-website-url")).toBeTruthy();
    expect(screen.getByTestId("references-website-label")).toBeTruthy();
    expect(screen.getByTestId("references-website-inline-link")).toBeTruthy();
    expect(screen.getByTestId("references-phone")).toBeTruthy();
    expect(screen.getByTestId("references-hidden")).toBeTruthy();
    expect(screen.getByTestId("references-description-wrap")).toBeTruthy();
    // R4: NO `email` testid
    expect(screen.queryByTestId("references-email")).toBeNull();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.references.items = [seedSingle()];
      });
    });
    const { ReferencesDialog } = await importDialog();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    expect((screen.getByTestId("references-name") as HTMLInputElement).value).toBe(
      "Dr. Smith",
    );
    expect(
      (screen.getByTestId("references-position") as HTMLInputElement).value,
    ).toBe("Director of Engineering");
    expect(
      (screen.getByTestId("references-phone") as HTMLInputElement).value,
    ).toBe("+86-138-0013-8000");
  });

  it("field edits write to store + undoStack (AC-10)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.references.items = [seedSingle()];
      });
    });
    const { ReferencesDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    const initial = useResumeV2Store.getState().undoStack.length;
    fireEvent.change(screen.getByTestId("references-name"), {
      target: { value: "Dr. Jane Doe" },
    });
    fireEvent.change(screen.getByTestId("references-position"), {
      target: { value: "VP Engineering" },
    });
    fireEvent.change(screen.getByTestId("references-phone"), {
      target: { value: "+1-555-0100" },
    });
    const item = useResumeV2Store.getState().data.sections.references.items[0];
    expect(item.name).toBe("Dr. Jane Doe");
    expect(item.position).toBe("VP Engineering");
    expect(item.phone).toBe("+1-555-0100");
    expect(useResumeV2Store.getState().undoStack.length).toBeGreaterThan(initial);
  });

  it("phone is free-form (R10/AC-10) — accepts arbitrary text", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.references.items = [
          seedSingle({ phone: "" }),
        ];
      });
    });
    const { ReferencesDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    const phoneInput = screen.getByTestId("references-phone") as HTMLInputElement;
    // R10: phone free-form — accept phone, intl, internal, ext, label
    fireEvent.change(phoneInput, { target: { value: "010-12345 ext 678" } });
    expect(useResumeV2Store.getState().data.sections.references.items[0].phone).toBe(
      "010-12345 ext 678",
    );
    fireEvent.change(phoneInput, { target: { value: "wechat: ref-12345" } });
    expect(useResumeV2Store.getState().data.sections.references.items[0].phone).toBe(
      "wechat: ref-12345",
    );
  });

  it("URL scheme whitelist (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.references.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { ReferencesDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    const urlInput = screen.getByTestId("references-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "sms:+86-138-0013-8000" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).not.toHaveBeenCalledWith(expect.any(String), "warn");
    expect(
      useResumeV2Store.getState().data.sections.references.items[0].website.url,
    ).toBe("sms:+86-138-0013-8000");
  });

  it("URL scheme blacklist rejects javascript: (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.references.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { ReferencesDialog } = await importDialog();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    const urlInput = screen.getByTestId("references-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "javascript:alert(1)" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
    expect(screen.getByTestId("references-website-url-error")).toBeTruthy();
  });

  it("no local draft state — close loops undo to S0 (AC-19, AC-20)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.references.items = [seedSingle()];
      });
    });
    const { useResumeV2Store } = await importStore();
    const S0 = JSON.parse(JSON.stringify(useResumeV2Store.getState().data));
    const { ReferencesDialog } = await importDialog();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    fireEvent.change(screen.getByTestId("references-name"), {
      target: { value: "X" },
    });
    fireEvent.change(screen.getByTestId("references-position"), {
      target: { value: "Y" },
    });
    fireEvent.change(screen.getByTestId("references-phone"), {
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
        d.sections.references.items = [seedSingle()];
      });
    });
    const { ReferencesDialog } = await importDialog();
    render(
      <ReferencesDialog
        onClose={() => {}}
        sectionId="references"
        itemId="ref1"
      />,
    );
    const payload = "<img src=x onerror=alert(1)>";
    fireEvent.change(screen.getByTestId("references-name"), {
      target: { value: payload },
    });
    const inp = screen.getByTestId("references-name") as HTMLInputElement;
    expect(inp.value).toBe(payload);
  });
});
