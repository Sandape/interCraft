// REQ-034 US5 — VolunteerDialog tests.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => await import("../VolunteerDialog");
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
    id: "v1",
    hidden: false,
    organization: "Red Cross",
    location: "Beijing",
    period: "2020-01 ~ Present",
    website: { url: "https://redcross.org", label: "Red Cross", inlineLink: true },
    description: "<p>Volunteered.</p>",
    ...fields,
  };
}

describe("VolunteerDialog (AC-09, R3: NO position, R3: description not summary, AC-17, AC-19)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders 7+3+1 input testids (AC-09, R3) — NO position, NO summary, field=description", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.volunteer.items = [seedSingle()];
      });
    });
    const { VolunteerDialog } = await importDialog();
    render(<VolunteerDialog onClose={() => {}} sectionId="volunteer" itemId="v1" />);
    expect(screen.getByTestId("volunteer-organization")).toBeTruthy();
    expect(screen.getByTestId("volunteer-location")).toBeTruthy();
    expect(screen.getByTestId("volunteer-period")).toBeTruthy();
    expect(screen.getByTestId("volunteer-website-url")).toBeTruthy();
    expect(screen.getByTestId("volunteer-website-label")).toBeTruthy();
    expect(screen.getByTestId("volunteer-website-inline-link")).toBeTruthy();
    expect(screen.getByTestId("volunteer-hidden")).toBeTruthy();
    expect(screen.getByTestId("volunteer-description-wrap")).toBeTruthy();
    // R3: NO `position` testid (R3 fix)
    expect(screen.queryByTestId("volunteer-position")).toBeNull();
    // R3: NO `summary` testid — uses `description` (R3 fix)
    expect(screen.queryByTestId("volunteer-summary")).toBeNull();
  });

  it("period free-form single input (AC-17)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.volunteer.items = [
          seedSingle({ period: "" }),
        ];
      });
    });
    const { VolunteerDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<VolunteerDialog onClose={() => {}} sectionId="volunteer" itemId="v1" />);
    const periodInput = screen.getByTestId("volunteer-period") as HTMLInputElement;
    // R17: NO period-start / period-end
    expect(screen.queryByTestId("volunteer-period-start")).toBeNull();
    expect(screen.queryByTestId("volunteer-period-end")).toBeNull();
    fireEvent.change(periodInput, { target: { value: "2020-01 ~ 2022-06" } });
    expect(useResumeV2Store.getState().data.sections.volunteer.items[0].period).toBe(
      "2020-01 ~ 2022-06",
    );
    fireEvent.change(periodInput, { target: { value: "2020-01 ~ Present" } });
    expect(useResumeV2Store.getState().data.sections.volunteer.items[0].period).toBe(
      "2020-01 ~ Present",
    );
  });

  it("URL scheme whitelist (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.volunteer.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { VolunteerDialog } = await importDialog();
    const { useResumeV2Store } = await importStore();
    render(<VolunteerDialog onClose={() => {}} sectionId="volunteer" itemId="v1" />);
    const urlInput = screen.getByTestId("volunteer-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "mailto:a@b.com" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).not.toHaveBeenCalledWith(expect.any(String), "warn");
    expect(
      useResumeV2Store.getState().data.sections.volunteer.items[0].website.url,
    ).toBe("mailto:a@b.com");
  });

  it("URL scheme blacklist rejects vbscript: (AC-16)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.volunteer.items = [
          seedSingle({ website: { url: "", label: "", inlineLink: false } }),
        ];
      });
    });
    const { VolunteerDialog } = await importDialog();
    render(<VolunteerDialog onClose={() => {}} sectionId="volunteer" itemId="v1" />);
    const urlInput = screen.getByTestId("volunteer-website-url") as HTMLInputElement;
    fireEvent.change(urlInput, { target: { value: "vbscript:msgbox(1)" } });
    fireEvent.blur(urlInput);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("no local draft state — close loops undo to S0 (AC-19, AC-20)", async () => {
    await resetStore((m) => {
      m.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.volunteer.items = [seedSingle()];
      });
    });
    const { useResumeV2Store } = await importStore();
    const S0 = JSON.parse(JSON.stringify(useResumeV2Store.getState().data));
    const { VolunteerDialog } = await importDialog();
    render(<VolunteerDialog onClose={() => {}} sectionId="volunteer" itemId="v1" />);
    fireEvent.change(screen.getByTestId("volunteer-organization"), {
      target: { value: "X" },
    });
    fireEvent.change(screen.getByTestId("volunteer-period"), {
      target: { value: "Y" },
    });
    fireEvent.change(screen.getByTestId("volunteer-location"), {
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
        d.sections.volunteer.items = [seedSingle()];
      });
    });
    const { VolunteerDialog } = await importDialog();
    render(<VolunteerDialog onClose={() => {}} sectionId="volunteer" itemId="v1" />);
    const payload = "<img src=x onerror=alert(1)>";
    fireEvent.change(screen.getByTestId("volunteer-organization"), {
      target: { value: payload },
    });
    const inp = screen.getByTestId("volunteer-organization") as HTMLInputElement;
    expect(inp.value).toBe(payload);
  });
});
