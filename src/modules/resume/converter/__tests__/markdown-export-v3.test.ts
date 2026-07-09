import { describe, expect, it, vi } from "vitest";
import { downloadSourceMarkdown } from "../markdown-export";

describe("v3 Markdown export", () => {
  it("downloads the preserved Markdown source", () => {
    const appendChild = vi.spyOn(document.body, "appendChild");
    const removeChild = vi.spyOn(document.body, "removeChild");
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    const click = vi.fn();
    const originalCreateElement = document.createElement.bind(document);

    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectURL,
    });
    vi.spyOn(document, "createElement").mockImplementation(((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName === "a") {
        Object.defineProperty(element, "click", { value: click });
      }
      return element;
    }) as typeof document.createElement);

    const markdown = "# 林溪\n\n::: left\nicon:phone 13800000000\n:::\n\n![图](https://placehold.co/80x40/png)";
    downloadSourceMarkdown(markdown, "linxi.md");

    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(click).toHaveBeenCalled();
    expect(appendChild).toHaveBeenCalled();
    expect(removeChild).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });
});
