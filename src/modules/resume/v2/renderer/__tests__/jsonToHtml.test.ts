// Vitest smoke for `jsonToHtml` (T123).
//
// Validates the US15 contract on the renderer side:
//   1. `jsonToHtml` returns a valid HTML document (starts with `<!DOCTYPE html>`).
//   2. The output includes the resolved CSS variables in a `<style>` tag.
//   3. The template's root `<div data-template="...">` is present.
//   4. The output is data-immutable: calling `jsonToHtml` with a `data`
//      object does not mutate it.
//   5. Switching `data.metadata.template` changes the rendered root
//      template (pikachu vs onyx) — proves the dispatcher is wired.
//   6. Unknown template ids fall back to Onyx.
//   7. Renders within 200ms (perf smoke; PDF gateway budget is 30s,
//      preview budget is 1s, so 200ms is comfortable).

import { describe, it, expect } from "vitest";

import { defaultResumeDataV2 } from "../../schema/defaults";
import type { ResumeDataV2 } from "../../schema/data";
import { jsonToHtml, generateCssVars } from "../jsonToHtml";

const makeData = (template?: string): ResumeDataV2 => {
  const d = JSON.parse(JSON.stringify(defaultResumeDataV2)) as ResumeDataV2;
  if (template) {
    d.metadata.template = template as ResumeDataV2["metadata"]["template"];
  }
  return d;
};

describe("T123 — jsonToHtml (US15 / FR-073)", () => {
  it("returns a full <!DOCTYPE html> document", () => {
    const html = jsonToHtml(makeData("pikachu"));
    expect(html).toMatch(/^<!DOCTYPE html>/i);
    expect(html).toContain("<html");
    expect(html).toContain("<head>");
    expect(html).toContain("<body>");
    expect(html).toContain("</html>");
  });

  it("inlines resolved CSS variables in a <style> tag", () => {
    const html = jsonToHtml(makeData("pikachu"));
    expect(html).toContain("<style>");
    expect(html).toContain("--color-primary:");
    // The default primary color in defaults.ts is rgba(0, 132, 209, 1).
    expect(html).toContain("rgba(0, 132, 209, 1)");
  });

  it("renders the template root with data-template attribute", () => {
    const html = jsonToHtml(makeData("pikachu"));
    expect(html).toContain('data-template="pikachu"');
  });

  it("switches template root when data.metadata.template changes", () => {
    const pikachu = jsonToHtml(makeData("pikachu"));
    const onyx = jsonToHtml(makeData("onyx"));
    expect(pikachu).toContain('data-template="pikachu"');
    expect(onyx).toContain('data-template="onyx"');
    expect(pikachu).not.toContain('data-template="onyx"');
  });

  it("falls back to Onyx for unknown template ids", () => {
    const html = jsonToHtml(makeData("definitely-not-a-template"));
    expect(html).toContain('data-template="onyx"');
  });

  it("does NOT mutate the input data", () => {
    const data = makeData("pikachu");
    const snapshot = JSON.parse(JSON.stringify(data));
    jsonToHtml(data);
    jsonToHtml(data);
    expect(data).toEqual(snapshot);
  });

  it("renders the basics.name in the output body", () => {
    const data = makeData("pikachu");
    data.basics.name = "Grace Hopper";
    const html = jsonToHtml(data);
    expect(html).toContain("Grace Hopper");
  });

  it("escapes HTML in basics.name to prevent injection", () => {
    const data = makeData("pikachu");
    data.basics.name = "<script>alert(1)</script>";
    const html = jsonToHtml(data);
    expect(html).not.toContain("<script>alert(1)</script>");
    // The escaped version is in the document <title> at minimum.
    expect(html).toContain("&lt;script&gt;");
  });

  it("renders within 200ms (perf smoke)", () => {
    const t0 = performance.now();
    jsonToHtml(makeData("pikachu"));
    const elapsed = performance.now() - t0;
    expect(elapsed).toBeLessThan(200);
  });

  it("handles a partial data shape without throwing", () => {
    const partial = { metadata: { template: "pikachu" } } as unknown as ResumeDataV2;
    expect(() => jsonToHtml(partial)).not.toThrow();
    const html = jsonToHtml(partial);
    expect(html).toContain('data-template="pikachu"');
  });
});

describe("generateCssVars", () => {
  it("emits a :root { ... } block", () => {
    const out = generateCssVars(makeData("pikachu"));
    expect(out).toMatch(/^:root\s*\{/);
    expect(out).toMatch(/\}$/);
  });

  it("includes the hide-link-underline toggle", () => {
    const data = makeData("pikachu");
    data.metadata.page.hideLinkUnderline = true;
    const out = generateCssVars(data);
    expect(out).toContain("--rs-hide-link-underline: none;");
  });
});
