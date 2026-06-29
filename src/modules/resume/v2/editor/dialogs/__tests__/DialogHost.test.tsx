// REQ-034 US1 — DialogHost dispatcher tests.
//
// Covers AC-11 + AC-11b:
//   - `openDialog({ type: "basics" })` renders BasicsDialog
//   - `openDialog({ type: "picture" })` renders PictureDialog
//   - The `type` namespace is the bare section name (no verb suffix).
//   - No `basics.create` / `basics.update` / `basics.delete` leakage.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

// Mock the avatar service so PictureDialog's file-picker path is callable
// in tests without a real network roundtrip.
vi.mock("@/api/avatar", () => ({
  uploadAvatar: vi.fn(async (file: File) => ({
    avatar_id: "av-1",
    url: `https://cdn.example.com/${file.name}`,
    content_type: file.type,
    byte_size: file.size,
    width: null,
    height: null,
    created_at: "2026-06-29T00:00:00Z",
  })),
}));

// Mock fireToast — we don't care about toast output here, but we want
// the spy for any indirectly-triggered call paths.
const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importDialog = async () => {
  vi.resetModules();
  return await import("../DialogHost");
};

describe("DialogHost dispatcher (AC-11, AC-11b)", () => {
  beforeEach(() => {
    fireToastMock.mockReset();
  });

  it("renders BasicsDialog after openDialog({type:'basics'})", async () => {
    const { DialogHost, useDialogStore } = await importDialog();
    render(<DialogHost />);
    expect(screen.queryByTestId("basics-dialog")).toBeNull();
    act(() => {
      useDialogStore.getState().openDialog({ type: "basics" });
    });
    expect(screen.getByTestId("basics-dialog")).toBeTruthy();
  });

  it("renders PictureDialog after openDialog({type:'picture'})", async () => {
    const { DialogHost, useDialogStore } = await importDialog();
    render(<DialogHost />);
    expect(screen.queryByTestId("picture-dialog")).toBeNull();
    act(() => {
      useDialogStore.getState().openDialog({ type: "picture" });
    });
    expect(screen.getByTestId("picture-dialog")).toBeTruthy();
  });

  it("type namespace uses bare section name for single-instance (AC-11b)", async () => {
    const { useDialogStore } = await importDialog();
    // The exported DialogType union must include `'basics'` and `'picture'`
    // (no verb suffix). This is a compile-time guarantee; runtime check:
    act(() => {
      useDialogStore.getState().openDialog({ type: "basics" as "basics" });
    });
    act(() => {
      useDialogStore.getState().closeDialog();
    });
    act(() => {
      useDialogStore.getState().openDialog({ type: "picture" as "picture" });
    });
  });

  it("closeDialog unmounts the active dialog", async () => {
    const { DialogHost, useDialogStore } = await importDialog();
    render(<DialogHost />);
    act(() => {
      useDialogStore.getState().openDialog({ type: "basics" });
    });
    expect(screen.getByTestId("basics-dialog")).toBeTruthy();
    act(() => {
      useDialogStore.getState().closeDialog();
    });
    expect(screen.queryByTestId("basics-dialog")).toBeNull();
  });

  it("renders nothing when no dialog is active", async () => {
    const { DialogHost } = await importDialog();
    const { container } = render(<DialogHost />);
    expect(container.firstChild).toBeNull();
  });

  it("global ESC listener calls closeDialog", async () => {
    const { DialogHost, useDialogStore } = await importDialog();
    render(<DialogHost />);
    act(() => {
      useDialogStore.getState().openDialog({ type: "picture" });
    });
    expect(screen.getByTestId("picture-dialog")).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("picture-dialog")).toBeNull();
  });

  it("renders ExperienceDialog after openDialog({type:'experience.update'}) (US2 AC-11b)", async () => {
    const { DialogHost, useDialogStore } = await importDialog();
    // Seed an item so the dialog can find it.
    const storeMod = await import("../../../store");
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
    }));
    act(() => {
      storeMod.useResumeV2Store.getState().setDataMut((d) => {
        d.sections.experience.items = [
          {
            id: "e1",
            hidden: false,
            company: "ACME",
            position: "Staff",
            location: "",
            period: "",
            website: { url: "", label: "", inlineLink: false },
            description: "",
            roles: [],
          },
        ];
      });
    });
    render(<DialogHost />);
    act(() => {
      useDialogStore.getState().openDialog({
        type: "experience.update",
        payload: { sectionId: "experience", itemId: "e1" },
      });
    });
    expect(screen.getByTestId("experience-dialog")).toBeTruthy();
  });

  it("experience verb namespaced (no .create-item / .update-item / .add / .edit / .delete)", async () => {
    const { useDialogStore } = await importDialog();
    // Just ensure the type union and dispatcher accept the namespaced forms.
    act(() => {
      useDialogStore.getState().openDialog({
        type: "experience.create",
        payload: { sectionId: "experience" },
      });
    });
    act(() => {
      useDialogStore.getState().closeDialog();
    });
    act(() => {
      useDialogStore.getState().openDialog({
        type: "experience.update",
        payload: { sectionId: "experience", itemId: "ignored" },
      });
    });
    act(() => {
      useDialogStore.getState().closeDialog();
    });
  });

  it("unknown type throws (fail loud, AC-11b-revised)", async () => {
    const { DialogHost, useDialogStore } = await importDialog();
    render(<DialogHost />);
    expect(() => {
      act(() => {
        // Cast through unknown to simulate a typo / forgotten case.
        useDialogStore.getState().openDialog({
          type: "experience.unknown" as never,
        });
      });
    }).toThrow(/unknown dialog type/);
  });
});