// REQ-034 US1 — PictureDialog unit tests.
//
// Covers AC-05, AC-05b, AC-06 + AC-06 extensions, AC-07, AC-08c, AC-09b.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
const uploadAvatarMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));
vi.mock("@/api/avatar", () => ({
  uploadAvatar: (...args: unknown[]) => uploadAvatarMock(...args),
}));

const importPicture = async () => {
  return await import("../PictureDialog");
};

const importStore = async () => await import("../../../store");

async function resetStoreWith() {
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
  }));
}

describe("PictureDialog (AC-05, AC-05b, AC-06, AC-07, AC-09b)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
    uploadAvatarMock.mockReset();
  });

  it("renders all 10 picture fields (AC-05)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    render(<PictureDialog onClose={() => {}} />);
    expect(screen.getByTestId("picture-hidden")).toBeTruthy();
    expect(screen.getByTestId("picture-file-input")).toBeTruthy();
    expect(screen.getByTestId("picture-url")).toBeTruthy();
    expect(screen.getByTestId("picture-size")).toBeTruthy();
    expect(screen.getByTestId("picture-rotation")).toBeTruthy();
    expect(screen.getByTestId("picture-aspect-ratio")).toBeTruthy();
    expect(screen.getByTestId("picture-border-radius")).toBeTruthy();
    expect(screen.getByTestId("picture-border-color")).toBeTruthy();
    expect(screen.getByTestId("picture-border-width")).toBeTruthy();
    expect(screen.getByTestId("picture-shadow-color")).toBeTruthy();
    expect(screen.getByTestId("picture-shadow-width")).toBeTruthy();
  });

  it("clamps size 1024 → 512 on blur (AC-06)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-size") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "1024" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.size).toBe(512);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("clamps rotation -10 → 0 on blur (AC-06)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-rotation") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "-10" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.rotation).toBe(0);
  });

  it("clamps aspectRatio 3.0 → 2.5 on blur (AC-06)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-aspect-ratio") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "3.0" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.aspectRatio).toBe(2.5);
  });

  it("clamps borderRadius 150 → 100 on blur (AC-06)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-border-radius") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "150" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.borderRadius).toBe(100);
  });

  it("clamps borderWidth -5 → 0 and 999 → 40 on blur (AC-06 extension)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-border-width") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "-5" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.borderWidth).toBe(0);
    fireEvent.change(input, { target: { value: "999" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.borderWidth).toBe(40);
  });

  it("clamps shadowWidth -1 → 0 and 100 → 40 on blur (AC-06 extension)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-shadow-width") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "-1" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.shadowWidth).toBe(0);
    fireEvent.change(input, { target: { value: "100" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.shadowWidth).toBe(40);
  });

  it("non-numeric input (NaN) does not write to store + toasts warn (AC-06 ext R5)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    const before = useResumeV2Store.getState().data.picture.size;
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-size") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.blur(input);
    // The clamp guards the write; store value is unchanged.
    expect(useResumeV2Store.getState().data.picture.size).toBe(before);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("Infinity input is rejected + toasts (AC-06 ext)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    const before = useResumeV2Store.getState().data.picture.aspectRatio;
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-aspect-ratio") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Infinity" } });
    fireEvent.blur(input);
    expect(useResumeV2Store.getState().data.picture.aspectRatio).toBe(before);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("upload rejects oversized file (5 MB cap) — no network call (AC-05b)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-file-input") as HTMLInputElement;
    const big = new File([new Uint8Array(6 * 1024 * 1024)], "big.png", {
      type: "image/png",
    });
    Object.defineProperty(input, "files", { value: [big] });
    fireEvent.change(input);
    expect(uploadAvatarMock).not.toHaveBeenCalled();
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "error");
  });

  it("upload rejects wrong mime type — no network call (AC-05b)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-file-input") as HTMLInputElement;
    const pdf = new File([new Uint8Array(1024)], "x.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(input, "files", { value: [pdf] });
    fireEvent.change(input);
    expect(uploadAvatarMock).not.toHaveBeenCalled();
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "error");
  });

  it("upload success writes returned url into store (AC-05)", async () => {
    await resetStoreWith();
    uploadAvatarMock.mockResolvedValue({
      avatar_id: "av-1",
      url: "https://cdn.example.com/x.png",
      content_type: "image/png",
      byte_size: 100,
      width: null,
      height: null,
      created_at: "2026-06-29T00:00:00Z",
    });
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-file-input") as HTMLInputElement;
    const png = new File([new Uint8Array(100)], "x.png", { type: "image/png" });
    Object.defineProperty(input, "files", { value: [png] });
    fireEvent.change(input);
    await new Promise((r) => setTimeout(r, 0));
    expect(uploadAvatarMock).toHaveBeenCalledTimes(1);
    expect(useResumeV2Store.getState().data.picture.url).toBe(
      "https://cdn.example.com/x.png",
    );
  });

  it("upload failure preserves original url (AC-07)", async () => {
    await resetStoreWith();
    uploadAvatarMock.mockRejectedValue(new Error("500 server"));
    const { PictureDialog } = await importPicture();
    const { useResumeV2Store } = await importStore();
    const original = useResumeV2Store.getState().data.picture.url;
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-file-input") as HTMLInputElement;
    const png = new File([new Uint8Array(100)], "x.png", { type: "image/png" });
    Object.defineProperty(input, "files", { value: [png] });
    fireEvent.change(input);
    await new Promise((r) => setTimeout(r, 0));
    expect(useResumeV2Store.getState().data.picture.url).toBe(original);
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "error");
  });

  it("rejects javascript: url on blur with toast (AC-09b)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-url") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "javascript:alert(1)" } });
    fireEvent.blur(input);
    expect(screen.getByTestId("picture-url-error")).toBeTruthy();
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("rejects url longer than 2048 chars on blur (AC-09b)", async () => {
    await resetStoreWith();
    const { PictureDialog } = await importPicture();
    render(<PictureDialog onClose={() => {}} />);
    const input = screen.getByTestId("picture-url") as HTMLInputElement;
    fireEvent.change(input, {
      target: { value: "https://example.com/" + "a".repeat(2050) },
    });
    fireEvent.blur(input);
    expect(screen.getByTestId("picture-url-error")).toBeTruthy();
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });
});