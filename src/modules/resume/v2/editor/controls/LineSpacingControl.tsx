import {
  LINE_HEIGHT_PRESETS,
  type LineHeightPreset,
} from "@/modules/resume/pagination/line-height";

export interface LineSpacingControlProps {
  value: LineHeightPreset;
  disabled: boolean;
  onChange: (lineHeight: LineHeightPreset) => void;
}

export function LineSpacingControl({ value, disabled, onChange }: LineSpacingControlProps) {
  return (
    <label className="flex items-center gap-2 text-xs text-ink-2">
      <span className="font-medium">行距</span>
      <select
        data-testid="line-spacing-control"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value) as LineHeightPreset)}
        className="h-8 rounded border border-surface-border bg-white px-2 text-xs text-ink-1 disabled:cursor-not-allowed disabled:opacity-60"
        aria-label="选择行距"
      >
        {LINE_HEIGHT_PRESETS.map((preset) => (
          <option key={preset} value={preset}>
            {preset}
          </option>
        ))}
      </select>
    </label>
  );
}
