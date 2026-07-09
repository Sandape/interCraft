// T128 — Vitest smoke test for StylesPanel (US8).
//
// Asserts (per FR-045 + spec.md US8 acceptance scenarios):
//   - Styles panel renders
//   - Empty state shows the "Add Rule" button (always; until cap)
//   - Clicking "Add Rule" opens the rule editor dialog
//   - Dialog exposes a target scope selector with the 3 expected options
//   - Dialog exposes 15 slot checkboxes
//   - Dialog exposes 4 intent tabs (Color / Text / Spacing / Border)
//   - Saving a rule with target=global + slot=section + color intent
//     propagates into metadata.styleRules
//   - Toggling a rule's enabled flag is reflected in metadata.styleRules
//   - Deleting a rule removes it from metadata.styleRules
//
// Specificity (T133), the cap of 50 (T135), and the disabled rule filter
// (T134) are already covered by the resolver tests under
// `__tests__/style-rules.test.ts` and `schema/data.ts` schema tests — this
// file is the UI smoke test only.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import React from "react";

import { defaultResumeDataV2 } from "../../../schema/defaults";
import type { ResumeDataV2 } from "../../../schema/data";
import { StylesPanel } from "../StylesPanel";

afterEach(() => cleanup());

function renderPanel(initial: ResumeDataV2) {
  let lastData = initial;
  const onChange = vi.fn((next: ResumeDataV2) => {
    lastData = next;
  });
  const utils = render(<StylesPanel data={initial} onChange={onChange} />);
  return {
    ...utils,
    onChange,
    getLast: () => lastData,
  };
}

describe("T128 — StylesPanel (US8 smoke test)", () => {
  it("renders the panel with the 'Add Rule' button and an empty-state message", () => {
    renderPanel(defaultResumeDataV2);
    expect(screen.getByTestId("styles-panel")).toBeInTheDocument();
    expect(screen.getByTestId("styles-add-rule")).toBeInTheDocument();
    expect(screen.getByTestId("styles-empty")).toBeInTheDocument();
  });

  it("clicking 'Add Rule' opens the rule editor dialog", () => {
    renderPanel(defaultResumeDataV2);
    fireEvent.click(screen.getByTestId("styles-add-rule"));
    expect(screen.getByTestId("style-rule-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("style-rule-dialog-body")).toBeInTheDocument();
  });

  it("dialog exposes target scope selector with the 3 expected options", () => {
    renderPanel(defaultResumeDataV2);
    fireEvent.click(screen.getByTestId("styles-add-rule"));
    expect(screen.getByTestId("style-rule-scope-global")).toBeInTheDocument();
    expect(screen.getByTestId("style-rule-scope-sectionType")).toBeInTheDocument();
    expect(screen.getByTestId("style-rule-scope-sectionId")).toBeInTheDocument();
  });

  it("dialog exposes 15 slot checkboxes", () => {
    renderPanel(defaultResumeDataV2);
    fireEvent.click(screen.getByTestId("styles-add-rule"));
    const slotIds = [
      "section",
      "heading",
      "item",
      "text",
      "secondaryText",
      "link",
      "icon",
      "level",
      "richParagraph",
      "richList",
      "richListItemRow",
      "richListItemContent",
      "richLink",
      "richBold",
      "richMark",
    ];
    for (const s of slotIds) {
      expect(screen.getByTestId(`style-rule-slot-${s}`)).toBeInTheDocument();
    }
  });

  it("dialog exposes 4 intent tabs (color / text / spacing / border)", () => {
    renderPanel(defaultResumeDataV2);
    fireEvent.click(screen.getByTestId("styles-add-rule"));
    expect(screen.getByTestId("style-rule-tab-color")).toBeInTheDocument();
    expect(screen.getByTestId("style-rule-tab-text")).toBeInTheDocument();
    expect(screen.getByTestId("style-rule-tab-spacing")).toBeInTheDocument();
    expect(screen.getByTestId("style-rule-tab-border")).toBeInTheDocument();
  });

  it("saving a rule with global target + section slot + color intent adds it to metadata.styleRules", () => {
    const { onChange } = renderPanel(defaultResumeDataV2);
    fireEvent.click(screen.getByTestId("styles-add-rule"));

    // Set label.
    fireEvent.change(screen.getByTestId("style-rule-label"), {
      target: { value: "Orange headings" },
    });

    // Pick a slot (section).
    fireEvent.click(screen.getByTestId("style-rule-slot-section"));

    // Pick the Color tab + fill the color input.
    fireEvent.click(screen.getByTestId("style-rule-tab-color"));
    fireEvent.change(screen.getByTestId("intent-color"), {
      target: { value: "rgba(255, 140, 0, 1)" },
    });

    // Save.
    fireEvent.click(screen.getByTestId("style-rule-save"));

    expect(onChange).toHaveBeenCalled();
    const calls = onChange.mock.calls as Array<[ResumeDataV2]>;
    const next = calls[calls.length - 1][0];
    expect(next.metadata.styleRules).toHaveLength(1);
    const rule = next.metadata.styleRules[0];
    expect(rule.target).toEqual({ scope: "global" });
    expect(rule.slots.section).toMatchObject({
      color: "rgba(255, 140, 0, 1)",
    });
    expect(rule.label).toBe("Orange headings");
  });

  it("listing existing rules: each rule has an enable/disable, edit, and delete affordance", () => {
    // Seed: 1 rule.
    const seed: ResumeDataV2 = JSON.parse(JSON.stringify(defaultResumeDataV2));
    seed.metadata.styleRules = [
      {
        id: "rule-1",
        label: "Test",
        enabled: true,
        target: { scope: "global" },
        slots: { heading: { color: "rgba(0,0,0,1)" } },
      },
    ];
    renderPanel(seed);

    const item = screen.getByTestId("styles-rule-rule-1");
    expect(item).toBeInTheDocument();
    expect(within(item).getByTestId("styles-rule-rule-1-edit")).toBeInTheDocument();
    expect(within(item).getByTestId("styles-rule-rule-1-delete")).toBeInTheDocument();
    expect(within(item).getByTestId("styles-rule-rule-1-toggle")).toBeInTheDocument();
  });

  it("toggling a rule's enabled flag is reflected in onChange", () => {
    const seed: ResumeDataV2 = JSON.parse(JSON.stringify(defaultResumeDataV2));
    seed.metadata.styleRules = [
      {
        id: "rule-1",
        label: "Test",
        enabled: true,
        target: { scope: "global" },
        slots: { heading: { color: "rgba(0,0,0,1)" } },
      },
    ];
    const { onChange } = renderPanel(seed);

    onChange.mockClear();
    fireEvent.click(screen.getByTestId("styles-rule-rule-1-toggle"));
    const calls = onChange.mock.calls as Array<[ResumeDataV2]>;
    const next = calls[calls.length - 1][0];
    expect(next.metadata.styleRules[0].enabled).toBe(false);
  });

  it("deleting a rule removes it from onChange", () => {
    const seed: ResumeDataV2 = JSON.parse(JSON.stringify(defaultResumeDataV2));
    seed.metadata.styleRules = [
      {
        id: "rule-1",
        label: "Test",
        enabled: true,
        target: { scope: "global" },
        slots: { heading: { color: "rgba(0,0,0,1)" } },
      },
    ];
    const { onChange } = renderPanel(seed);

    onChange.mockClear();
    fireEvent.click(screen.getByTestId("styles-rule-rule-1-delete"));
    const calls = onChange.mock.calls as Array<[ResumeDataV2]>;
    const next = calls[calls.length - 1][0];
    expect(next.metadata.styleRules).toHaveLength(0);
  });

  it("'Add Rule' button is disabled when 50 rules already exist (T135 cap)", () => {
    const seed: ResumeDataV2 = JSON.parse(JSON.stringify(defaultResumeDataV2));
    seed.metadata.styleRules = Array.from({ length: 50 }, (_, i) => ({
      id: `rule-${i}`,
      label: `r${i}`,
      enabled: true,
      target: { scope: "global" as const },
      slots: { heading: { color: "rgba(0,0,0,1)" } },
    }));
    renderPanel(seed);
    const btn = screen.getByTestId("styles-add-rule") as HTMLButtonElement;
    expect(btn).toBeDisabled();
  });
});