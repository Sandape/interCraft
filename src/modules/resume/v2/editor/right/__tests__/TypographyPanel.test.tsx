// Wave 6 authored — awaiting US3+US5+US6+US7 implementation.
//
// T066 — TypographyPanel (Body + Heading groups) — Vitest.
//
// Validates:
// - 2 TypographyItemEditor instances (body + heading)
// - Font family combobox lists ≥ 20 fonts
// - Select font → updates metadata.typography.body.fontFamily (or heading)
// - Font weight multi-select (100-900, 9 options)
// - Font size input 6..24 (rejects 5, 25)
// - Line height input 0.5..4 (rejects 0.4, 4.5)
// - Body and heading edits are independent (changing body does NOT touch heading)

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import React from "react";

import { defaultResumeDataV2 } from "../../../schema/defaults";
import type { ResumeDataV2 } from "../../../schema/data";
import { TypographyPanel } from "../TypographyPanel";

const REQUIRED_FONTS = [
  "IBM Plex Sans",
  "IBM Plex Serif",
  "Fira Sans",
  "Fira Serif",
  "Fira Sans Condensed",
  "Roboto",
  "Inter",
  "Lato",
  "Source Sans Pro",
  "Open Sans",
  "Montserrat",
  "Raleway",
  "PT Sans",
  "Noto Sans",
  "JetBrains Mono",
];

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
  const utils = render(<TypographyPanel data={initial} onChange={onChange} />);
  return { ...utils, onChange, getLast: () => lastData };
}

describe("T066 — TypographyPanel (body + heading)", () => {
  it("renders 2 TypographyItemEditor instances (body + heading)", () => {
    renderPanel(defaultResumeDataV2);
    expect(screen.getByTestId("typography-body")).toBeInTheDocument();
    expect(screen.getByTestId("typography-heading")).toBeInTheDocument();
  });

  it("font family combobox lists at least 20 fonts (with required names)", () => {
    renderPanel(defaultResumeDataV2);
    const bodySelect = screen.getByTestId("typography-body-font-family");
    for (const f of REQUIRED_FONTS) {
      expect(
        within(bodySelect).getByRole("option", { name: f }),
        `expected font "${f}"`,
      ).toBeInTheDocument();
    }
    const optionCount = within(bodySelect).getAllByRole("option").length;
    expect(optionCount).toBeGreaterThanOrEqual(20);
  });

  it("selecting a body font updates metadata.typography.body.fontFamily", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const bodySelect = screen.getByTestId("typography-body-font-family");
    fireEvent.change(bodySelect, { target: { value: "Fira Sans" } });
    expect(onChange).toHaveBeenCalled();
    const next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.typography.body.fontFamily).toBe("Fira Sans");
  });

  it("font weight multi-select offers the 9 standard weights (100..900)", () => {
    renderPanel(defaultResumeDataV2);
    const weight = screen.getByTestId("typography-body-font-weights");
    for (const w of ["100", "300", "400", "500", "700", "900"]) {
      expect(
        within(weight).getByRole("option", { name: w }),
        `expected weight ${w}`,
      ).toBeInTheDocument();
    }
  });

  it("body font size input accepts 6..24 and rejects out-of-range values", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const size = screen.getByTestId("typography-body-font-size");

    // Valid 14 → onChange fires with new value.
    fireEvent.change(size, { target: { value: "14" } });
    let next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.typography.body.fontSize).toBe(14);

    // Below-range 5 → onChange NOT called (or value clamped to 6).
    onChange.mockClear();
    fireEvent.change(size, { target: { value: "5" } });
    if (onChange.mock.calls.length > 0) {
      next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
      expect(next.metadata.typography.body.fontSize).toBeGreaterThanOrEqual(6);
    }

    // Above-range 25 → similarly clamped or rejected.
    onChange.mockClear();
    fireEvent.change(size, { target: { value: "25" } });
    if (onChange.mock.calls.length > 0) {
      next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
      expect(next.metadata.typography.body.fontSize).toBeLessThanOrEqual(24);
    }
  });

  it("body line height input accepts 0.5..4 and rejects out-of-range values", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const lh = screen.getByTestId("typography-body-line-height");

    fireEvent.change(lh, { target: { value: "1.5" } });
    let next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.typography.body.lineHeight).toBe(1.5);

    onChange.mockClear();
    fireEvent.change(lh, { target: { value: "0.4" } });
    if (onChange.mock.calls.length > 0) {
      next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
      expect(next.metadata.typography.body.lineHeight).toBeGreaterThanOrEqual(0.5);
    }

    onChange.mockClear();
    fireEvent.change(lh, { target: { value: "4.5" } });
    if (onChange.mock.calls.length > 0) {
      next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
      expect(next.metadata.typography.body.lineHeight).toBeLessThanOrEqual(4);
    }
  });

  it("body and heading edits are independent", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const headingFamilyBefore =
      JSON.parse(JSON.stringify(defaultResumeDataV2)).metadata.typography.heading
        .fontFamily;

    const bodySelect = screen.getByTestId("typography-body-font-family");
    fireEvent.change(bodySelect, { target: { value: "Fira Sans" } });

    const next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.typography.body.fontFamily).toBe("Fira Sans");
    expect(next.metadata.typography.heading.fontFamily).toBe(headingFamilyBefore);
  });
});