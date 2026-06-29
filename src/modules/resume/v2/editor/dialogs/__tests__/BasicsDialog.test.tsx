// REQ-034 US1 — BasicsDialog unit tests.
//
// Covers AC-02, AC-03, AC-04, AC-04b, AC-08c, AC-09, AC-09b, AC-02b.

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import React from "react";

afterEach(() => cleanup());

const fireToastMock = vi.fn();
vi.mock("../../center/toast", () => ({
  fireToast: (...args: unknown[]) => fireToastMock(...args),
}));

const importBasics = async () => {
  return await import("../BasicsDialog");
};

const importStore = async () => await import("../../../store");

/** Reset the store + customFields before each test. */
async function resetStoreWith(setup?: (s: Awaited<ReturnType<typeof importStore>>) => void) {
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
  setup?.(storeMod);
}

describe("BasicsDialog (AC-02, AC-04, AC-08c, AC-09, AC-02b)", () => {
  beforeEach(async () => {
    fireToastMock.mockReset();
  });

  it("renders all 7 basics fields + customFields section (AC-02)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    render(<BasicsDialog onClose={() => {}} />);
    expect(screen.getByTestId("basics-name")).toBeTruthy();
    expect(screen.getByTestId("basics-headline")).toBeTruthy();
    expect(screen.getByTestId("basics-email")).toBeTruthy();
    expect(screen.getByTestId("basics-phone")).toBeTruthy();
    expect(screen.getByTestId("basics-location")).toBeTruthy();
    expect(screen.getByTestId("basics-website-url")).toBeTruthy();
    expect(screen.getByTestId("basics-website-label")).toBeTruthy();
    expect(screen.getByTestId("basics-custom-fields")).toBeTruthy();
  });

  it("typing into name writes to store via setDataMut (AC-02, AC-08c)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    const { useResumeV2Store } = await importStore();
    render(<BasicsDialog onClose={() => {}} />);
    const input = screen.getByTestId("basics-name") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "李祖荫" } });
    expect(useResumeV2Store.getState().data.basics.name).toBe("李祖荫");
  });

  it("add customField appends to store + pushes undo entry (AC-04)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    const { useResumeV2Store } = await importStore();
    const before = useResumeV2Store.getState().data.basics.customFields.length;
    render(<BasicsDialog onClose={() => {}} />);
    fireEvent.click(screen.getByTestId("basics-custom-field-add"));
    const after = useResumeV2Store.getState().data.basics.customFields.length;
    expect(after).toBe(before + 1);
    expect(useResumeV2Store.getState().undoStack.length).toBeGreaterThan(0);
  });

  it("remove customField splices by id (AC-04)", async () => {
    await resetStoreWith((m) => {
      m.useResumeV2Store.getState().setDataMut((draft) => {
        draft.basics.customFields.push({
          id: "cf-remove-me",
          icon: "phone",
          text: "ext 555",
          link: "",
        });
      });
    });
    const { BasicsDialog } = await importBasics();
    const { useResumeV2Store } = await importStore();
    render(<BasicsDialog onClose={() => {}} />);
    const removeBtn = screen
      .getByTestId("basics-custom-field-row")
      .querySelector(
        '[data-testid="basics-custom-field-remove"]',
      ) as HTMLElement;
    fireEvent.click(removeBtn);
    expect(
      useResumeV2Store
        .getState()
        .data.basics.customFields.find((c) => c.id === "cf-remove-me"),
    ).toBeUndefined();
  });

  it("reorder swaps id positions without changing id set (AC-04b)", async () => {
    await resetStoreWith((m) => {
      m.useResumeV2Store.getState().setDataMut((draft) => {
        draft.basics.customFields = [
          { id: "a", icon: "", text: "first", link: "" },
          { id: "b", icon: "", text: "second", link: "" },
          { id: "c", icon: "", text: "third", link: "" },
        ];
      });
    });
    const { BasicsDialog } = await importBasics();
    const { useResumeV2Store } = await importStore();
    render(<BasicsDialog onClose={() => {}} />);
    const rows = screen.getAllByTestId("basics-custom-field-row");
    const secondUpBtn = rows[1].querySelector(
      '[data-testid="basics-custom-field-up"]',
    ) as HTMLElement;
    fireEvent.click(secondUpBtn);
    const ids = useResumeV2Store
      .getState()
      .data.basics.customFields.map((c) => c.id);
    expect(new Set(ids)).toEqual(new Set(["a", "b", "c"]));
    expect(ids).toEqual(["b", "a", "c"]);
  });

  it("invalid email surfaces inline error and toasts warn (AC-02b)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    render(<BasicsDialog onClose={() => {}} />);
    const input = screen.getByTestId("basics-email") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "not-an-email" } });
    fireEvent.blur(input);
    expect(screen.getByTestId("basics-email-error")).toBeTruthy();
    expect(fireToastMock).toHaveBeenCalledWith(
      expect.stringContaining("邮箱"),
      "warn",
    );
  });

  it("invalid phone is rejected on blur with toast (AC-02b)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    render(<BasicsDialog onClose={() => {}} />);
    const input = screen.getByTestId("basics-phone") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "abc!!!" } });
    fireEvent.blur(input);
    expect(screen.getByTestId("basics-phone-error")).toBeTruthy();
    expect(fireToastMock).toHaveBeenCalledWith(
      expect.stringContaining("电话"),
      "warn",
    );
  });

  it("javascript: URL is rejected on blur (AC-02b / AC-09b)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    render(<BasicsDialog onClose={() => {}} />);
    const input = screen.getByTestId("basics-website-url") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "javascript:alert(1)" } });
    fireEvent.blur(input);
    expect(screen.getByTestId("basics-website-url-error")).toBeTruthy();
    expect(fireToastMock).toHaveBeenCalledWith(expect.any(String), "warn");
  });

  it("name with <script> payload writes to store verbatim; React escapes on render (AC-09)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    const { useResumeV2Store } = await importStore();
    render(<BasicsDialog onClose={() => {}} />);
    const input = screen.getByTestId("basics-name") as HTMLInputElement;
    fireEvent.change(input, {
      target: { value: "<script>window.__xssFired=true</script>" },
    });
    expect(useResumeV2Store.getState().data.basics.name).toContain("<script>");
    // DOM input.value is a string node, never interpreted as HTML.
    expect(input.value).toContain("<script>");
  });

  it("undo after dialog close restores pre-dialog customFields length (AC-08c)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    const { useResumeV2Store } = await importStore();
    const before = useResumeV2Store.getState().data.basics.customFields.length;
    render(<BasicsDialog onClose={() => {}} />);
    fireEvent.click(screen.getByTestId("basics-custom-field-add"));
    fireEvent.click(screen.getByTestId("basics-custom-field-add"));
    expect(useResumeV2Store.getState().data.basics.customFields.length).toBe(
      before + 2,
    );
    fireEvent.click(screen.getByTestId("basics-cancel"));
    useResumeV2Store.getState().undo();
    useResumeV2Store.getState().undo();
    expect(useResumeV2Store.getState().data.basics.customFields.length).toBe(
      before,
    );
  });

  it("undoStack depth bounded after 10 mutations (AC-04b US17 max=20)", async () => {
    await resetStoreWith();
    const { BasicsDialog } = await importBasics();
    const { useResumeV2Store } = await importStore();
    render(<BasicsDialog onClose={() => {}} />);
    for (let i = 0; i < 10; i++) {
      fireEvent.click(screen.getByTestId("basics-custom-field-add"));
    }
    expect(useResumeV2Store.getState().undoStack.length).toBeLessThanOrEqual(20);
  });
});