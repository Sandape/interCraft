/**
 * Ambient declarations for `markdown-it-emoji@3`.
 *
 * The installed `@types/markdown-it-emoji@2.0.5` package targets the v2 API
 * (single CommonJS export) and does not declare the v3 named exports
 * (`bare`, `light`, `full`) that the runtime `index.mjs` provides. This
 * mismatch causes `import { full as emoji } from 'markdown-it-emoji'` in
 * `src/lib/resume-renderer/parser.ts` to fail typecheck with TS2305.
 *
 * Fixing here rather than in the render library because spec 027 US1
 * declares the library frozen (built in Phase 2). Declaring the module
 * ambient lets TypeScript merge these named exports over the @types
 * package's default export.
 *
 * Spec: 027-resume-center-muji-alignment US1 (render engine integration).
 */
declare module 'markdown-it-emoji' {
  import type { PluginWithOptions } from 'markdown-it'

  export interface EmojiOptions {
    defs?: Record<string, string>
    enabled?: string[]
    shortcuts?: Record<string, string | string[]>
  }

  export const bare: PluginWithOptions<EmojiOptions>
  export const light: PluginWithOptions<EmojiOptions>
  export const full: PluginWithOptions<EmojiOptions>

  // Default export kept for backward compatibility with @types v2.
  const markdownitEmoji: PluginWithOptions<EmojiOptions>
  export default markdownitEmoji
}

// Force TypeScript to prefer this ambient declaration over @types/markdown-it-emoji.
declare module 'markdown-it-emoji/full' {
  import type { PluginWithOptions } from 'markdown-it'
  import type { EmojiOptions } from 'markdown-it-emoji'
  export const full: PluginWithOptions<EmojiOptions>
  export default full
}
