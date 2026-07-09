// T020 — Style-rule resolver tests.
//
// Covers `resolveStyleIntentForSlot` from `src/modules/resume/v2/schema/style-rules.ts`.
// Specificity: global < sectionType < sectionId. Multiple matching rules
// merge via Object.assign (later-specificity wins per property).
//
// These tests pin the resolver contract so a future drift in style-rules.ts
// is caught immediately. They should PASS as soon as T008 lands (the
// resolver file is shipped in Wave 1, foundation phase).
//
// T020 — authored in Wave 2 to lock the resolver contract.

import { describe, it, expect } from "vitest";

import type { ResumeDataV2, StyleRule } from "../schema/data";
import { resolveStyleIntentForSlot } from "../schema/style-rules";
import { defaultResumeDataV2 } from "../schema/defaults";

const makeData = (): ResumeDataV2 =>
  JSON.parse(JSON.stringify(defaultResumeDataV2));

const baseRule = (overrides: Partial<StyleRule> = {}): StyleRule => ({
  id: "rule-test",
  label: "test",
  enabled: true,
  target: { scope: "global" },
  slots: { heading: { color: "rgba(255,0,0,1)" } },
  ...overrides,
});

// ── 1. Empty rules ────────────────────────────────────────────────────────

describe("resolveStyleIntentForSlot — empty rules", () => {
  it("returns {} when no rules and any slot", () => {
    const data = makeData();
    data.metadata.styleRules = [];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(intent).toEqual({});
  });
});

// ── 2. Global only ───────────────────────────────────────────────────────

describe("resolveStyleIntentForSlot — global rule", () => {
  it("applies the global rule's intent to a querying slot", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({ slots: { heading: { color: "rgba(255,0,0,1)" } } }),
    ];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(intent).toEqual({ color: "rgba(255,0,0,1)" });
  });
});

// ── 3. sectionType overrides global ─────────────────────────────────────

describe("resolveStyleIntentForSlot — sectionType beats global", () => {
  it("returns the sectionType intent when both global and sectionType match", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({
        id: "g",
        slots: { heading: { color: "rgba(255,0,0,1)" } },
      }),
      baseRule({
        id: "st",
        target: { scope: "sectionType", sectionType: "experience" },
        slots: { heading: { color: "rgba(0,0,255,1)" } },
      }),
    ];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(intent).toEqual({ color: "rgba(0,0,255,1)" });
  });
});

// ── 4. sectionId beats both ──────────────────────────────────────────────

describe("resolveStyleIntentForSlot — sectionId beats sectionType", () => {
  it("returns the sectionId intent when all three match", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({
        id: "g",
        slots: { heading: { color: "rgba(255,0,0,1)" } },
      }),
      baseRule({
        id: "st",
        target: { scope: "sectionType", sectionType: "experience" },
        slots: { heading: { color: "rgba(0,0,255,1)" } },
      }),
      baseRule({
        id: "si",
        target: { scope: "sectionId", sectionId: "experience" },
        slots: { heading: { color: "rgba(0,255,0,1)" } },
      }),
    ];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(intent).toEqual({ color: "rgba(0,255,0,1)" });
  });
});

// ── 5. Object.assign merge per slot ──────────────────────────────────────

describe("resolveStyleIntentForSlot — Object.assign merge", () => {
  it("merges properties across rules via Object.assign (later-specificity wins per property)", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({
        id: "g",
        slots: {
          heading: {
            color: "rgba(255,0,0,1)",
            fontSize: 18,
          },
        },
      }),
      baseRule({
        id: "st",
        target: { scope: "sectionType", sectionType: "experience" },
        slots: {
          heading: {
            // Doesn't redefine `color` — global should survive on that prop
            fontSize: 24,
            fontWeight: "700",
          },
        },
      }),
    ];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    // color from global (255,0,0), fontSize overridden by sectionType (24),
    // fontWeight added by sectionType.
    expect(intent).toEqual({
      color: "rgba(255,0,0,1)",
      fontSize: 24,
      fontWeight: "700",
    });
  });
});

// ── 6. enabled: false rules are ignored ─────────────────────────────────

describe("resolveStyleIntentForSlot — disabled rules", () => {
  it("ignores rules with enabled: false", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({
        id: "off",
        enabled: false,
        slots: { heading: { color: "rgba(0,0,0,1)" } },
      }),
    ];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(intent).toEqual({});
  });
});

// ── 7. target.scope mismatch ────────────────────────────────────────────

describe("resolveStyleIntentForSlot — scope mismatch", () => {
  it("does not match a sectionType=skills rule when querying sectionType=experience", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({
        id: "skills-rule",
        target: { scope: "sectionType", sectionType: "skills" },
        slots: { heading: { color: "rgba(255,255,0,1)" } },
      }),
    ];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(intent).toEqual({});
  });

  it("does not match a sectionId=skills rule when querying sectionId=experience", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({
        id: "skills-id",
        target: { scope: "sectionId", sectionId: "skills" },
        slots: { heading: { color: "rgba(255,255,0,1)" } },
      }),
    ];
    const intent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(intent).toEqual({});
  });
});

// ── 8. Different slots return different intents ──────────────────────────

describe("resolveStyleIntentForSlot — slot isolation", () => {
  it("returns the link intent when querying slot=link, not slot=heading", () => {
    const data = makeData();
    data.metadata.styleRules = [
      baseRule({
        id: "multi",
        slots: {
          heading: { color: "rgba(255,0,0,1)" },
          link: { color: "rgba(0,255,0,1)", textDecoration: "underline" },
        },
      }),
    ];
    const linkIntent = resolveStyleIntentForSlot(data, {
      slot: "link",
      sectionId: "experience",
      sectionType: "experience",
    });
    const headingIntent = resolveStyleIntentForSlot(data, {
      slot: "heading",
      sectionId: "experience",
      sectionType: "experience",
    });
    expect(linkIntent).toEqual({
      color: "rgba(0,255,0,1)",
      textDecoration: "underline",
    });
    expect(headingIntent).toEqual({ color: "rgba(255,0,0,1)" });
  });
});
