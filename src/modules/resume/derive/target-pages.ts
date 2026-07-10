/** Client-side content budget helpers for target 1/2/3 pages (REQ-055). */
export function computeTargetPageBudget(targetPages: 1 | 2 | 3) {
  const perPage = 3200;
  return {
    targetPages,
    maxChars: perPage * targetPages,
    mustShow: ["basics", "summary"] as const,
    compressible: ["projects", "experience", "skills"] as const,
  };
}

export function pagesMatch(actual: number | null | undefined, target: number | null | undefined) {
  if (actual == null || target == null) return false;
  return Number(actual) === Number(target);
}
