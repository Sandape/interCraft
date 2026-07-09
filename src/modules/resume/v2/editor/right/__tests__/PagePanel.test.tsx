// Wave 6 authored — awaiting US3+US5+US6+US7 implementation.
//
// T073 — PagePanel (Format + Language + marginX/Y + gapX/Y + hide* switches) — Vitest.
//
// Validates:
// - Renders all 9 fields
// - Format combobox has 3 options: a4 / letter / free-form
// - Select format → updates metadata.page.format
// - marginX/Y inputs accept 0..200 (rejects -1, 201)
// - gapX/Y inputs accept 0..200
// - hideLinkUnderline / hideIcons / hideSectionIcons switches toggle booleans
// - hideSectionIcons default = true (per spec)
// - Language combobox lists BCP-47 locales (en-US, zh-CN, ja-JP, ...)

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import React from "react";

import { defaultResumeDataV2 } from "../../../schema/defaults";
import type { ResumeDataV2 } from "../../../schema/data";
import { PagePanel } from "../PagePanel";

const REQUIRED_LOCALES = ["en-US", "zh-CN", "ja-JP", "ko-KR", "fr-FR", "de-DE", "es-ES"];

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((q: string) => ({
      matches: false,
      media: q,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => cleanup());

function renderPanel(initial: ResumeDataV2) {
  let lastData = initial;
  const onChange = vi.fn((next: ResumeDataV2) => {
    lastData = next;
  });
  const utils = render(<PagePanel data={initial} onChange={onChange} />);
  return { ...utils, onChange, getLast: () => lastData };
}

describe("T073 — PagePanel (format + language + margins + switches)", () => {
  it("renders all 9 fields", () => {
    renderPanel(defaultResumeDataV2);
    expect(screen.getByTestId("page-language")).toBeInTheDocument();
    expect(screen.getByTestId("page-format")).toBeInTheDocument();
    expect(screen.getByTestId("page-margin-x")).toBeInTheDocument();
    expect(screen.getByTestId("page-margin-y")).toBeInTheDocument();
    expect(screen.getByTestId("page-gap-x")).toBeInTheDocument();
    expect(screen.getByTestId("page-gap-y")).toBeInTheDocument();
    expect(screen.getByTestId("page-hide-link-underline")).toBeInTheDocument();
    expect(screen.getByTestId("page-hide-icons")).toBeInTheDocument();
    expect(screen.getByTestId("page-hide-section-icons")).toBeInTheDocument();
  });

  it("format combobox has the 3 schema options", () => {
    renderPanel(defaultResumeDataV2);
    const fmt = screen.getByTestId("page-format");
    for (const v of ["a4", "letter", "free-form"]) {
      expect(
        within(fmt).getByRole("option", { name: v }),
        `expected format "${v}"`,
      ).toBeInTheDocument();
    }
  });

  it("selecting format 'letter' updates metadata.page.format", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    fireEvent.change(screen.getByTestId("page-format"), {
      target: { value: "letter" },
    });
    expect(onChange).toHaveBeenCalled();
    const next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.page.format).toBe("letter");
  });

  it("marginX / marginY inputs accept 0..200 and reject -1 / 201", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const mx = screen.getByTestId("page-margin-x");
    fireEvent.change(mx, { target: { value: "14" } });
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.marginX).toBe(14);

    onChange.mockClear();
    fireEvent.change(mx, { target: { value: "-1" } });
    if (onChange.mock.calls.length > 0) {
      expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.marginX).toBeGreaterThanOrEqual(0);
    }

    onChange.mockClear();
    fireEvent.change(mx, { target: { value: "201" } });
    if (onChange.mock.calls.length > 0) {
      expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.marginX).toBeLessThanOrEqual(200);
    }

    const my = screen.getByTestId("page-margin-y");
    fireEvent.change(my, { target: { value: "30" } });
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.marginY).toBe(30);
  });

  it("gapX / gapY inputs accept 0..200", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    fireEvent.change(screen.getByTestId("page-gap-x"), { target: { value: "8" } });
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.gapX).toBe(8);
    fireEvent.change(screen.getByTestId("page-gap-y"), { target: { value: "12" } });
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.gapY).toBe(12);
  });

  it("hideLinkUnderline / hideIcons / hideSectionIcons switches toggle booleans", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const s1 = screen.getByTestId("page-hide-link-underline");
    fireEvent.click(s1);
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.hideLinkUnderline).toBe(true);
    fireEvent.click(s1);
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.hideLinkUnderline).toBe(false);

    const s2 = screen.getByTestId("page-hide-icons");
    fireEvent.click(s2);
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.hideIcons).toBe(true);

    const s3 = screen.getByTestId("page-hide-section-icons");
    fireEvent.click(s3);
    expect((onChange.mock.calls.at(-1)![0] as ResumeDataV2).metadata.page.hideSectionIcons).toBe(false);
  });

  it("hideSectionIcons defaults to true per spec", () => {
    renderPanel(defaultResumeDataV2);
    const sw = screen.getByTestId("page-hide-section-icons") as HTMLInputElement;
    // Switch may render as input[type=checkbox] OR as a button with aria-checked.
    if (sw instanceof HTMLInputElement && sw.type === "checkbox") {
      expect(sw.checked).toBe(true);
    } else {
      expect(sw.getAttribute("aria-checked")).toBe("true");
    }
  });

  it("language combobox lists the required BCP-47 locales", () => {
    renderPanel(defaultResumeDataV2);
    const lang = screen.getByTestId("page-language");
    for (const code of REQUIRED_LOCALES) {
      expect(
        within(lang).getByRole("option", { name: code }),
        `expected locale ${code}`,
      ).toBeInTheDocument();
    }
  });
});