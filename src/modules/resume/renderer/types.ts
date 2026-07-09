export type MujiThemeId =
  | "muji-default-autumn"
  | "muji-minimal-color"
  | "muji-flat-atmospheric";

export type MujiThemePattern =
  | "dark-header-centered-section"
  | "minimal-line"
  | "accent-band";

export type LineHeightPreset =
  | 12
  | 13
  | 14
  | 15
  | 16
  | 17
  | 18
  | 19
  | 20
  | 21
  | 22
  | 23
  | 24
  | 25;

export type SmartOnePageStatus = "idle" | "fit" | "already-fit" | "infeasible";

export type MarkdownPaginationState =
  | "idle"
  | "measuring"
  | "paginated"
  | "warning"
  | "failed";

export type LegacyConversionStatus =
  | "not_needed"
  | "pending"
  | "converted"
  | "warning"
  | "failed";

export interface ResumeMarkdownSettings {
  sourceMarkdown: string;
  themeId: MujiThemeId;
  manualLineHeight: LineHeightPreset;
  smartOnePageEnabled: boolean;
  smartLineHeight: LineHeightPreset | null;
  previousManualLineHeight: LineHeightPreset | null;
  smartStatus: SmartOnePageStatus;
  paginationState: MarkdownPaginationState;
  pageCount: number;
  legacyConversionStatus: LegacyConversionStatus;
  legacyConversionWarnings: string[];
}

export type MarkdownRenderWarningCode =
  | "unsupported_syntax"
  | "unsafe_url"
  | "broken_image"
  | "fallback";

export interface MarkdownRenderWarning {
  code: MarkdownRenderWarningCode;
  message: string;
  sourceExcerpt?: string;
}

export interface MarkdownRenderInput {
  sourceMarkdown: string;
  themeId: MujiThemeId;
  lineHeight: LineHeightPreset;
}

export interface MarkdownRenderOutput {
  html: string;
  warnings: MarkdownRenderWarning[];
}

export const MUJI_THEME_IDS: readonly MujiThemeId[] = [
  "muji-default-autumn",
  "muji-minimal-color",
  "muji-flat-atmospheric",
];

export const LINE_HEIGHT_PRESETS: readonly LineHeightPreset[] = [
  12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
];

export const DEFAULT_LINE_HEIGHT: LineHeightPreset = 19;

export const DEFAULT_MARKDOWN_SOURCE = `# 林溪 - AI 应用工程师

::: left
icon:phone 13800000000
icon:email linxi@example.com
:::

::: right
[icon:github GitHub](https://github.com/example-linxi)
:::

## 个人总结

5 年 AI 应用与全栈工程经验，专注 **RAG、Agent 工作流、企业知识库、评测体系**。

## 技能

- RAG / Agent / Prompt Engineering
- TypeScript / React / Vite / Playwright
`;

export const DEFAULT_MARKDOWN_SETTINGS: ResumeMarkdownSettings = {
  sourceMarkdown: DEFAULT_MARKDOWN_SOURCE,
  themeId: "muji-default-autumn",
  manualLineHeight: DEFAULT_LINE_HEIGHT,
  smartOnePageEnabled: false,
  smartLineHeight: null,
  previousManualLineHeight: null,
  smartStatus: "idle",
  paginationState: "idle",
  pageCount: 1,
  legacyConversionStatus: "not_needed",
  legacyConversionWarnings: [],
};

export function isMujiThemeId(value: string): value is MujiThemeId {
  return (MUJI_THEME_IDS as readonly string[]).includes(value);
}

export function isLineHeightPreset(value: number): value is LineHeightPreset {
  return (LINE_HEIGHT_PRESETS as readonly number[]).includes(value);
}
