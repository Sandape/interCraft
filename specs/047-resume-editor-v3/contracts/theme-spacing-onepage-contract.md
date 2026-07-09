# Contract: Theme, Line Spacing, and Smart One-Page

## Theme Contract

```ts
type MujiThemeId =
  | 'muji-default-autumn'
  | 'muji-minimal-color'
  | 'muji-flat-atmospheric'

interface ThemeOption {
  id: MujiThemeId
  displayName: '默认（秋风同款）' | '极简色' | '平面大气主题'
  renderPattern:
    | 'dark-header-centered-section'
    | 'minimal-line'
    | 'accent-band'
}
```

## Theme Requirements

- Theme switching must not mutate `sourceMarkdown`.
- Each theme must render the same supported Markdown content.
- Visual acceptance should compare against the captured Muji evidence:
  - 默认（秋风同款）: dark title/header area and centered gray section labels.
  - 极简色: black title and blue underlined left section headings.
  - 平面大气主题: blue title band and blue section labels with long rules.

## Line Spacing Contract

```ts
type LineHeightPreset = 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25

interface LineSpacingState {
  manualLineHeight: LineHeightPreset
  effectiveLineHeight: LineHeightPreset
}
```

## Line Spacing Requirements

- UI exposes integer presets 12-25.
- Body text, lists, and tables visibly compress/expand when changed.
- Theme section decorations remain readable.
- Manual line height persists while smart one-page is off.

## Smart One-Page Contract

```ts
interface SmartOnePageState {
  enabled: boolean
  previousManualLineHeight: LineHeightPreset
  selectedLineHeight: LineHeightPreset | null
  status: 'idle' | 'fit' | 'already-fit' | 'infeasible'
}
```

## Smart One-Page Requirements

- Enabling smart one-page temporarily overrides manual line spacing.
- Disabling smart one-page restores the previous manual line spacing.
- Smart one-page must never hide or delete content.
- If content cannot fit one page within safe line-height/layout bounds, status is `infeasible` and the user sees a clear message.

## Acceptance Tests

- Switch all three themes over the same Markdown and verify source unchanged.
- Select line-height 12, 19, and 25 and verify effective preview class/style changes.
- Enable smart one-page from line-height 12 and verify manual value is restored after disabling.
- Use a too-long fixture and verify smart one-page reports infeasible without deleting content.

