// Phosphor → lucide-react icon crosswalk (per spec research.md §3 C3).
// Reactive-resume v5 stores Phosphor icon names; eGGG renders with lucide-react.
// Mappings are best-effort; unknown Phosphor names fall back to `Circle`.

const phosphorToLucideMap: Record<string, string> = {
  // Section icons
  briefcase: "briefcase",
  "graduation-cap": "graduation-cap",
  "code-simple": "code",
  "compass-tool": "wrench",
  translate: "languages",
  football: "heart",
  trophy: "trophy",
  certificate: "award",
  books: "book-open",
  "hand-heart": "hand-heart",
  phone: "phone",
  "messenger-logo": "link",
  // UI icons
  article: "file-text",
  star: "star",
  square: "square",
  circle: "circle",
  heart: "heart",
  crown: "crown",
  // Misc
  user: "user",
  mail: "mail",
  "map-pin": "map-pin",
  github: "github",
  linkedin: "linkedin",
  twitter: "twitter",
  instagram: "instagram",
  globe: "globe",
  link: "link",
  image: "image",
  palette: "palette",
  type: "type",
  layout: "layout",
  settings: "settings",
};

const FALLBACK_ICON = "circle";

/**
 * Map a Phosphor icon name (e.g. `code-simple`) to a lucide-react name
 * (e.g. `code`). Returns `circle` when no mapping is found.
 */
export function phosphorToLucide(phosphorName: string | undefined | null): string {
  if (!phosphorName) return FALLBACK_ICON;
  return phosphorToLucideMap[phosphorName] ?? phosphorToLucideMap[normalize(phosphorName)] ?? FALLBACK_ICON;
}

function normalize(name: string): string {
  // Lowercase + strip non-alphanum to provide a forgiving fuzzy lookup.
  return name.toLowerCase().replace(/[^a-z0-9-]/g, "");
}

export const LUCIDE_FALLBACK_ICON = FALLBACK_ICON;
