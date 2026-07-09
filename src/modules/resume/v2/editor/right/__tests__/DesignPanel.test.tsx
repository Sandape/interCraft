// Wave 6 authored — awaiting US3+US5+US6+US7 implementation.
//
// T058 — DesignPanel (3 color pickers + level type + level icon) — Vitest.
//
// Validates:
// - 3 color pickers bind to metadata.design.colors.{primary,text,background}
// - 22 quick swatches per picker
// - Click swatch → onChange(nextData) where nextData updates design.colors.X
// - Manual hex/rgba input on change → updates the field
// - Level type combobox has 7 options (hidden/circle/square/rectangle/
//   rectangle-full/progress-bar/icon)
// - Select level type → updates metadata.design.level.type
// - Level icon picker filters lucide icons by typing
// - Select icon → updates metadata.design.level.icon

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import React from "react";

import { defaultResumeDataV2 } from "../../../schema/defaults";
import type { ResumeDataV2 } from "../../../schema/data";
import { DesignPanel } from "../DesignPanel";

// 22-color curated palette — the panel MUST render exactly this many swatches
// per picker per spec. We assert count, not identity, so the dev agent can tweak.
const SWATCH_COUNT = 22;

beforeEach(() => {
  // jsdom lacks matchMedia; DesignPanel may use it for its own responsive popovers.
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

// Helper — render DesignPanel inside a data-state holder so we can capture onChange.
function renderPanel(initialData: ResumeDataV2) {
  let lastData: ResumeDataV2 = initialData;
  const onChange = vi.fn((next: ResumeDataV2) => {
    lastData = next;
  });
  const utils = render(<DesignPanel data={initialData} onChange={onChange} />);
  return {
    ...utils,
    onChange,
    getLastData: () => lastData,
  };
}

describe("T058 — DesignPanel (colors + level)", () => {
  it("renders 3 color pickers bound to design.colors.{primary,text,background}", () => {
    renderPanel(defaultResumeDataV2);
    expect(screen.getByTestId("color-picker-primary")).toBeInTheDocument();
    expect(screen.getByTestId("color-picker-text")).toBeInTheDocument();
    expect(screen.getByTestId("color-picker-background")).toBeInTheDocument();
  });

  it("renders 22 quick swatches per color picker (curated palette)", () => {
    renderPanel(defaultResumeDataV2);
    for (const slot of ["primary", "text", "background"] as const) {
      const picker = screen.getByTestId(`color-picker-${slot}`);
      const swatches = within(picker).getAllByTestId(/^swatch-/);
      expect(swatches, `${slot} swatches`).toHaveLength(SWATCH_COUNT);
    }
  });

  it("clicking a primary-color swatch updates metadata.design.colors.primary via onChange", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const picker = screen.getByTestId("color-picker-primary");
    const firstSwatch = within(picker).getAllByTestId(/^swatch-/)[0];
    const expected = firstSwatch.getAttribute("data-color");
    expect(expected).toMatch(/^rgba?\(/);
    fireEvent.click(firstSwatch);
    expect(onChange).toHaveBeenCalled();
    const next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.design.colors.primary).toBe(expected);
  });

  it("manual rgba input updates the field on change", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const input = screen.getByTestId("color-input-text");
    fireEvent.change(input, { target: { value: "rgba(10, 20, 30, 1)" } });
    expect(onChange).toHaveBeenCalled();
    const next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.design.colors.text).toBe("rgba(10, 20, 30, 1)");
  });

  it("level type combobox has the 7 options from the schema", () => {
    renderPanel(defaultResumeDataV2);
    const select = screen.getByTestId("level-type-select");
    const expected = [
      "hidden",
      "circle",
      "square",
      "rectangle",
      "rectangle-full",
      "progress-bar",
      "icon",
    ];
    for (const t of expected) {
      expect(
        within(select).getByRole("option", { name: t }),
        `expected level type "${t}"`,
      ).toBeInTheDocument();
    }
  });

  it("selecting level type 'progress-bar' updates metadata.design.level.type", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const select = screen.getByTestId("level-type-select");
    fireEvent.change(select, { target: { value: "progress-bar" } });
    expect(onChange).toHaveBeenCalled();
    const next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.design.level.type).toBe("progress-bar");
  });

  it("level icon picker filters lucide icons by typing into the search box", () => {
    renderPanel(defaultResumeDataV2);
    const search = screen.getByTestId("level-icon-search");
    fireEvent.change(search, { target: { value: "heart" } });
    const options = screen.getAllByTestId(/^level-icon-option-/);
    expect(options.length).toBeGreaterThan(0);
    for (const opt of options) {
      expect(opt.textContent?.toLowerCase()).toContain("heart");
    }
  });

  it("selecting a level icon updates metadata.design.level.icon", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    const search = screen.getByTestId("level-icon-search");
    fireEvent.change(search, { target: { value: "star" } });
    const option = screen.getByTestId("level-icon-option-star");
    fireEvent.click(option);
    expect(onChange).toHaveBeenCalled();
    const next = onChange.mock.calls.at(-1)![0] as ResumeDataV2;
    expect(next.metadata.design.level.icon).toBe("star");
  });
});