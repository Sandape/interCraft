// Style rule resolver — ported verbatim from reactive-resume v5
// (packages/schema/src/resume/style-rules.ts:42-64).
//
// Specificity: global < sectionType < sectionId.
// When multiple rules match, the slot's intent is the Object.assign merge in
// ascending specificity order (i.e. later entries override earlier ones).

import type {
  CustomSectionType,
  ResumeDataV2,
  SectionType,
  StyleIntent,
  StyleSlot,
} from "./data";

export type SectionStyleRuleContext = {
  sectionId: string;
  sectionType?: CustomSectionType | undefined;
};

export type ResolveStyleRuleSlotOptions = {
  slot: StyleSlot;
  sectionId?: string | undefined;
  sectionType?: CustomSectionType | undefined;
};

const builtInSectionTypes = new Set<SectionType>([
  "profiles",
  "experience",
  "education",
  "projects",
  "skills",
  "languages",
  "interests",
  "awards",
  "certifications",
  "publications",
  "volunteer",
  "references",
]);

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

/**
 * Derive the (sectionId, sectionType) pair for a given section id in a resume.
 * - "summary" → sectionType "summary" (not in sectionTypeSchema but valid context)
 * - Built-in section types (experience, education, …) → sectionId === sectionType
 * - Custom sections → look up in `data.customSections`
 */
export const getSectionStyleRuleContext = (
  data: ResumeDataV2,
  sectionId: string,
): SectionStyleRuleContext => {
  if (sectionId === "summary") return { sectionId, sectionType: "summary" as CustomSectionType };
  if (builtInSectionTypes.has(sectionId as SectionType)) {
    return { sectionId, sectionType: sectionId as SectionType };
  }
  const customSection = data.customSections.find(
    (section) => section.id === sectionId,
  );
  return { sectionId, sectionType: customSection?.type };
};

export const resolveStyleIntentForSlot = (
  data: ResumeDataV2,
  options: ResolveStyleRuleSlotOptions,
): StyleIntent => {
  const matchingRules = (data.metadata.styleRules ?? []).filter((rule) => {
    if (!rule.enabled) return false;
    if (!rule.slots[options.slot]) return false;
    if (rule.target.scope === "global") return true;
    if (rule.target.scope === "sectionType")
      return rule.target.sectionType === options.sectionType;
    if (rule.target.scope === "sectionId")
      return rule.target.sectionId === options.sectionId;
    return false;
  });

  const specificity = {
    global: 0,
    sectionType: 1,
    sectionId: 2,
  } as const;

  const bySpecificity = [...matchingRules].sort((a, b) => {
    return specificity[a.target.scope] - specificity[b.target.scope];
  });

  return Object.assign(
    {},
    ...bySpecificity.map((rule) => rule.slots[options.slot]),
  );
};

export const resolveStyleRuleFontSize = (
  data: ResumeDataV2,
  options: ResolveStyleRuleSlotOptions,
): number | undefined => {
  const fontSize = resolveStyleIntentForSlot(data, options).fontSize;
  if (fontSize === undefined) return undefined;
  return clamp(fontSize, 6, 48);
};
