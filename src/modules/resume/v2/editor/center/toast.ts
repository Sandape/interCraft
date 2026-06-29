// REQ-032 v2 MVP stub — fireToast.
//
// Toast system for the v2 editor. The real implementation will wire
// to Mantine notifications (or the existing toast store). For the
// MVP we surface toasts via console.warn so they appear in dev tools
// without crashing the editor if the toast provider is not yet
// mounted in the test harness.

export function fireToast(
  message: string,
  kind: "info" | "warn" | "error" = "info",
): void {
  // TODO: wire to actual toast system (Mantine notifications or similar)
  // For MVP, console.warn only.
  console.warn(`[toast:${kind}]`, message);
}