// Shared type alias for the 7 level display types per data-model.md §6.
// Kept separate from the Zod schema so non-React consumers (PDF renderer,
// future CLI tooling) can import this without pulling in zod.
export type LevelType =
  | "hidden"
  | "circle"
  | "square"
  | "rectangle"
  | "rectangle-full"
  | "progress-bar"
  | "icon";

export const LEVEL_TYPES: readonly LevelType[] = [
  "hidden",
  "circle",
  "square",
  "rectangle",
  "rectangle-full",
  "progress-bar",
  "icon",
] as const;
