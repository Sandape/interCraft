import type { MujiThemeId } from "@/modules/resume/renderer/types";
import { listV3Themes } from "@/modules/resume/themes";

export interface ThemeMenuProps {
  value: MujiThemeId;
  onChange: (themeId: MujiThemeId) => void;
}

export function ThemeMenu({ value, onChange }: ThemeMenuProps) {
  return (
    <label className="flex items-center gap-2 text-xs text-ink-2">
      <span className="font-medium">主题</span>
      <select
        data-testid="theme-menu"
        value={value}
        onChange={(event) => onChange(event.target.value as MujiThemeId)}
        className="h-8 rounded border border-surface-border bg-white px-2 text-xs text-ink-1"
        aria-label="选择简历主题"
      >
        {listV3Themes().map((theme) => (
          <option key={theme.id} value={theme.id}>
            {theme.name}
          </option>
        ))}
      </select>
    </label>
  );
}
