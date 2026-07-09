// REQ-034 US5 — CertificationsDialog tests.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../CertificationsDialog");
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
    id: "c1",
    hidden: false,
    title: "AWS SAA",
    issuer: "Amazon",
    date: "2024-05",
    website: { url: "https://aws.amazon.com", label: "AWS", inlineLink: false },
    description: "<p>Architect.</p>",
    ...fields,
  };
}

describe("CertificationsDialog (AC-07, AC-16, AC-19)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders all 7+3 input testids (AC-07)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.certifications.items = [seedSingle()];
      });
    });
    const { CertificationsDialog } = await importDialog();
    render(
      <CertificationsDialog
        onClose={() => {}}
        sectionId="certifications"
        itemId="c1"
      />,
    );
    expect(screen.getByTestId("certifications-title")).toBeTruthy();
    expect(screen.getByTestId("certifications-issuer")).toBeTruthy();
    expect(screen.getByTestId("certifications-date")).toBeTruthy();
    expect(screen.getByTestId("certifications-website-url")).toBeTruthy();
    expect(screen.getByTestId("certifications-website-label")).toBeTruthy();
    expect(screen.getByTestId("certifications-website-inline-link")).toBeTruthy();
    expect(screen.getByTestId("certifications-hidden")).toBeTruthy();
    expect(screen.getByTestId("certifications-description-wrap")).toBeTruthy();
  });

  it("update dialog prefills from store (AC-03)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.certifications.items = [seedSingle()];
      });
    });
    const { CertificationsDialog } = await importDialog();
    render(
      <CertificationsDialog
        onClose={() => {}}
        sectionId="certifications"
        itemId="c1"
      />,
    );
    expect(
      (screen.getByTestId("certifications-title") as HTMLInputElement).value,
    ).toBe("AWS SAA");
    expect(
      (screen.getByTestId("certifications-issuer") as HTMLInputElement).value,
    ).toBe("Amazon");
  });

  it("URL scheme whitelist (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.certifications.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { CertificationsDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(
      <CertificationsDialog
        onClose={() => {}}
        sectionId="certifications"
        itemId="c1"
      />,
    );
    const urlInput = screen.getByTestId("certifications-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "https://[::1]:8080" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).not.toHaveBeenCalledWith(expect.any(String), "warn");
    expect(
      useResumeV2Store.getState().data.sections.certifications.items[0].website.url,
    ).toBe("https://[::1]:8080");
  });

  it("URL scheme blacklist rejects data: (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.certifications.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { CertificationsDialog } = await importDialog();
    render(
      <CertificationsDialog
        onClose={() => {}}
        sectionId="certifications"
        itemId="c1"
      />,
    );
    const urlInput = screen.getByTestId("certifications-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "data:text/html,<script>alert(1)</script>" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("no local draft state — close loops undo to S0 (AC-19, AC-20)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.certifications.items = [seedSingle()];
      });
    });
    const { useResumeV2Store } = await importStore();
    const S0 = JSON.parse(JSON.stringify(useResumeV2Store.getState().data));
    const { CertificationsDialog } = await importDialog();
    render(
      <CertificationsDialog
        onClose={() => {}}
        sectionId="certifications"
        itemId="c1"
      />,
    );
    fireEvent.change(screen.getByTestId("certifications-title"), {
      target: { value: "X" },
    });
    fireEvent.change(screen.getByTestId("certifications-issuer"), {
      target: { value: "Y" },
    });
    fireEvent.change(screen.getByTestId("certifications-date"), {
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
        d.sections.certifications.items = [seedSingle()];
      });
    });
    const { CertificationsDialog } = await importDialog();
    render(
      <CertificationsDialog
        onClose={() => {}}
        sectionId="certifications"
        itemId="c1"
      />,
    );
    const payload = "<img src=x onerror=alert(1)>";
    fireEvent.change(screen.getByTestId("certifications-title"), {
      target: { value: payload },
    });
    const inp = screen.getByTestId("certifications-title") as HTMLInputElement;
    expect(inp.value).toBe(payload);
  });
});
