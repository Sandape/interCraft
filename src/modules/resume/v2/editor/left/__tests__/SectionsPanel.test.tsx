// REQ-034 US1 — SectionsPanel metadata-entry tests.
//
// Covers AC-01, AC-01b:
//   - Basics row click opens basics dialog via DialogHost dispatcher.
//   - Picture row click opens picture dialog via DialogHost dispatcher.
//   - DOM order: basics → picture → summary placeholder → sections.*.
//   - `data-section-group="metadata"` tag is on basics/picture rows.
//   - Mobile < 640px does not overflow horizontally.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

vi.mock("../../center/toast", () => ({
  fireToast: vi.fn(),
}));

describe("SectionsPanel metadata entries (AC-01, AC-01b)", () => {
  beforeEach(async () => {
    // Reset DialogStore + store between tests. We re-import each module
    // inside beforeEach to share the singleton across all tests in this
    // file (vitest caches dynamic imports).
    const SectionsPanelMod = await import("../SectionsPanel");
    const DialogHostMod = await import("../../dialogs/DialogHost");
    const storeMod = await import("../../../store");
    const defaultsMod = await import("../../../schema/defaults");
    void SectionsPanelMod;
    DialogHostMod.useDialogStore.setState({ active: null });
    storeMod.useResumeV2Store.setState((s) => ({
      ...s,
      data: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
      version: 1,
      id: "r1",
      hydrated: true,
      original: JSON.parse(JSON.stringify(defaultsMod.defaultResumeDataV2)),
      undoStack: [],
      redoStack: [],
      historyTTLTimer: null,
      debounceTimer: null,
      lastEditAt: null,
    }));
  });

  it("clicking basics row opens basics dialog (AC-01)", async () => {
    const SectionsPanelMod = await import("../SectionsPanel");
    const DialogHostMod = await import("../../dialogs/DialogHost");
    render(<SectionsPanelMod.default />);
    act(() => {
      fireEvent.click(screen.getByTestId("section-row-basics"));
    });
    const active = DialogHostMod.useDialogStore.getState().active;
    expect(active?.type).toBe("basics");
  });

  it("clicking picture row opens picture dialog (AC-01)", async () => {
    const SectionsPanelMod = await import("../SectionsPanel");
    const DialogHostMod = await import("../../dialogs/DialogHost");
    render(<SectionsPanelMod.default />);
    act(() => {
      fireEvent.click(screen.getByTestId("section-row-picture"));
    });
    const active = DialogHostMod.useDialogStore.getState().active;
    expect(active?.type).toBe("picture");
  });

  it("DOM order: basics, picture, summary placeholder, then sections (AC-01b)", async () => {
    const SectionsPanelMod = await import("../SectionsPanel");
    const { container } = render(<SectionsPanelMod.default />);
    const metadata = container.querySelectorAll(
      '[data-section-group="metadata"]',
    );
    expect(metadata.length).toBeGreaterThanOrEqual(3);
    const testIds = Array.from(metadata).map((el) =>
      el.getAttribute("data-testid"),
    );
    // First two MUST be basics + picture.
    expect(testIds[0]).toBe("section-row-basics");
    expect(testIds[1]).toBe("section-row-picture");
    // Snapshot includes a `summary` placeholder per spec (US3 hook).
    expect(testIds).toContain("section-row-summary");
  });

  it("metadata rows do not overflow at 375px viewport (AC-01b)", async () => {
    const SectionsPanelMod = await import("../SectionsPanel");
    // jsdom doesn't enforce layout, but we can assert the rows have
    // `w-full` and no explicit horizontal widths that would overflow.
    render(<SectionsPanelMod.default />);
    const basics = screen.getByTestId("section-row-basics") as HTMLElement;
    const picture = screen.getByTestId("section-row-picture") as HTMLElement;
    expect(basics.className).toContain("w-full");
    expect(picture.className).toContain("w-full");
  });
});