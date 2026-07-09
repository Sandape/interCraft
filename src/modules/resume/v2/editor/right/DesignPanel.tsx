import { useMemo, useState } from "react";
import type { LevelType, ResumeDataV2 } from "../../schema/data";
import { useResumeV2Store } from "../../store";

export interface DesignPanelProps {
  data?: ResumeDataV2;
  onChange?: (next: ResumeDataV2) => void;
}

const COLOR_SLOTS = [
  { id: "primary", label: "Primary" },
  { id: "text", label: "Text" },
  { id: "background", label: "Background" },
] as const;

const SWATCHES = [
  "rgba(15, 23, 42, 1)",
  "rgba(51, 65, 85, 1)",
  "rgba(100, 116, 139, 1)",
  "rgba(239, 68, 68, 1)",
  "rgba(249, 115, 22, 1)",
  "rgba(245, 158, 11, 1)",
  "rgba(234, 179, 8, 1)",
  "rgba(132, 204, 22, 1)",
  "rgba(34, 197, 94, 1)",
  "rgba(20, 184, 166, 1)",
  "rgba(6, 182, 212, 1)",
  "rgba(14, 165, 233, 1)",
  "rgba(59, 130, 246, 1)",
  "rgba(99, 102, 241, 1)",
  "rgba(139, 92, 246, 1)",
  "rgba(168, 85, 247, 1)",
  "rgba(217, 70, 239, 1)",
  "rgba(236, 72, 153, 1)",
  "rgba(244, 63, 94, 1)",
  "rgba(120, 113, 108, 1)",
  "rgba(255, 255, 255, 1)",
  "rgba(0, 0, 0, 1)",
] as const;

const LEVEL_TYPES: LevelType[] = [
  "hidden",
  "circle",
  "square",
  "rectangle",
  "rectangle-full",
  "progress-bar",
  "icon",
];

const ICON_OPTIONS = [
  "circle",
  "square",
  "star",
  "heart",
  "check",
  "badge-check",
  "sparkles",
  "zap",
  "award",
  "trophy",
  "target",
  "wrench",
  "book",
  "briefcase",
  "graduation-cap",
  "languages",
  "users",
  "user",
  "code",
  "palette",
] as const;

function cloneData(data: ResumeDataV2): ResumeDataV2 {
  return JSON.parse(JSON.stringify(data)) as ResumeDataV2;
}

function rgbaToCssInput(value: string): string {
  return value;
}

export function DesignPanel(props: DesignPanelProps = {}): JSX.Element {
  const storeData = useResumeV2Store((s) => s.data);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const data = props.data ?? storeData;
  const [iconQuery, setIconQuery] = useState("");

  const iconOptions = useMemo(() => {
    const q = iconQuery.trim().toLowerCase();
    return q ? ICON_OPTIONS.filter((icon) => icon.includes(q)) : ICON_OPTIONS;
  }, [iconQuery]);

  const commit = (mutator: (draft: ResumeDataV2) => void) => {
    if (props.data && props.onChange) {
      const next = cloneData(props.data);
      mutator(next);
      props.onChange(next);
      return;
    }
    setDataMut(mutator);
  };

  const setColor = (slot: (typeof COLOR_SLOTS)[number]["id"], value: string) => {
    commit((draft) => {
      draft.metadata.design.colors[slot] = value;
    });
  };

  const setLevelType = (value: LevelType) => {
    commit((draft) => {
      draft.metadata.design.level.type = value;
    });
  };

  const setLevelIcon = (value: string) => {
    commit((draft) => {
      draft.metadata.design.level.icon = value;
    });
  };

  return (
    <div data-testid="design-panel" className="flex h-full flex-col gap-4 overflow-y-auto p-3">
      <section className="space-y-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-3">Colors</div>
        {COLOR_SLOTS.map((slot) => (
          <div
            key={slot.id}
            data-testid={`color-picker-${slot.id}`}
            className="rounded border border-surface-border bg-surface-base p-3"
          >
            <label className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium text-ink-2">{slot.label}</span>
              <input
                data-testid={`color-input-${slot.id}`}
                value={rgbaToCssInput(data.metadata.design.colors[slot.id])}
                onChange={(event) => setColor(slot.id, event.target.value)}
                className="h-7 min-w-0 flex-1 rounded border border-surface-border bg-surface px-2 text-xs text-ink-1"
              />
            </label>
            <div className="mt-3 grid grid-cols-11 gap-1">
              {SWATCHES.map((color, index) => (
                <button
                  key={`${slot.id}-${color}`}
                  type="button"
                  data-testid={`swatch-${slot.id}-${index}`}
                  data-color={color}
                  aria-label={`${slot.label} ${color}`}
                  onClick={() => setColor(slot.id, color)}
                  className="h-5 rounded border border-surface-border shadow-sm transition hover:scale-105 focus:outline-none focus:ring-2 focus:ring-primary-400"
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className="space-y-3 rounded border border-surface-border bg-surface-base p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-3">Level</div>
        <label className="block space-y-1">
          <span className="text-xs text-ink-2">Type</span>
          <select
            data-testid="level-type-select"
            value={data.metadata.design.level.type}
            onChange={(event) => setLevelType(event.target.value as LevelType)}
            className="w-full rounded border border-surface-border bg-surface px-2 py-1 text-xs text-ink-1"
          >
            {LEVEL_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-ink-2">Icon</span>
          <input
            data-testid="level-icon-search"
            value={iconQuery}
            onChange={(event) => setIconQuery(event.target.value)}
            placeholder={data.metadata.design.level.icon}
            className="w-full rounded border border-surface-border bg-surface px-2 py-1 text-xs text-ink-1"
          />
        </label>
        <div className="grid grid-cols-2 gap-1">
          {iconOptions.map((icon) => (
            <button
              key={icon}
              type="button"
              data-testid={`level-icon-option-${icon}`}
              aria-pressed={data.metadata.design.level.icon === icon}
              onClick={() => setLevelIcon(icon)}
              className={[
                "rounded border px-2 py-1 text-left text-xs transition",
                data.metadata.design.level.icon === icon
                  ? "border-primary-300 bg-primary-50 text-primary-700"
                  : "border-surface-border bg-surface text-ink-2 hover:bg-surface-muted",
              ].join(" ")}
            >
              {icon}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

export default DesignPanel;
