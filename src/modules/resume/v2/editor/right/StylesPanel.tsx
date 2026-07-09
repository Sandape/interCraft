import { useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import type { ResumeDataV2, SectionType, StyleIntent, StyleRule } from "../../schema/data";
import { useResumeV2Store } from "../../store";

export interface StylesPanelProps {
  data?: ResumeDataV2;
  onChange?: (next: ResumeDataV2) => void;
}

type IntentTab = "color" | "text" | "spacing" | "border";
type TargetScope = StyleRule["target"]["scope"];

const SLOT_IDS = [
  "section",
  "heading",
  "item",
  "text",
  "secondaryText",
  "link",
  "icon",
  "level",
  "richParagraph",
  "richList",
  "richListItemRow",
  "richListItemContent",
  "richLink",
  "richBold",
  "richMark",
] as const;

const SECTION_TYPES: SectionType[] = [
  "profiles",
  "experience",
  "education",
  "projects",
  "skills",
  "languages",
  "interests",
  "awards",
  "certifications",
  "publications",
  "volunteer",
  "references",
];

const DEFAULT_INTENT: StyleIntent = {
  color: "rgba(15, 23, 42, 1)",
};

function cloneData(data: ResumeDataV2): ResumeDataV2 {
  return JSON.parse(JSON.stringify(data)) as ResumeDataV2;
}

function createRuleId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `rule-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function summarizeRule(rule: StyleRule): string {
  const slots = Object.keys(rule.slots);
  const target =
    rule.target.scope === "global"
      ? "global"
      : rule.target.scope === "sectionType"
        ? rule.target.sectionType
        : rule.target.sectionId;
  return `${target} / ${slots.join(", ") || "no slots"}`;
}

export function StylesPanel(props: StylesPanelProps = {}): JSX.Element {
  const storeData = useResumeV2Store((s) => s.data);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const data = props.data ?? storeData;
  const rules = data.metadata.styleRules ?? [];

  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [scope, setScope] = useState<TargetScope>("global");
  const [sectionType, setSectionType] = useState<SectionType>("experience");
  const [sectionId, setSectionId] = useState("summary");
  const [selectedSlots, setSelectedSlots] = useState<string[]>([]);
  const [tab, setTab] = useState<IntentTab>("color");
  const [intent, setIntent] = useState<StyleIntent>(DEFAULT_INTENT);

  const commit = (mutator: (draft: ResumeDataV2) => void) => {
    if (props.data && props.onChange) {
      const next = cloneData(props.data);
      mutator(next);
      props.onChange(next);
      return;
    }
    setDataMut(mutator);
  };

  const resetDialog = () => {
    setEditingId(null);
    setLabel("");
    setScope("global");
    setSectionType("experience");
    setSectionId("summary");
    setSelectedSlots([]);
    setTab("color");
    setIntent(DEFAULT_INTENT);
  };

  const openCreate = () => {
    resetDialog();
    setOpen(true);
  };

  const openEdit = (rule: StyleRule) => {
    setEditingId(rule.id);
    setLabel(rule.label ?? "");
    setScope(rule.target.scope);
    if (rule.target.scope === "sectionType") setSectionType(rule.target.sectionType);
    if (rule.target.scope === "sectionId") setSectionId(rule.target.sectionId);
    const slots = Object.keys(rule.slots);
    setSelectedSlots(slots);
    setIntent((rule.slots[slots[0]] as StyleIntent | undefined) ?? DEFAULT_INTENT);
    setTab("color");
    setOpen(true);
  };

  const closeDialog = () => {
    setOpen(false);
    resetDialog();
  };

  const toggleSlot = (slot: string) => {
    setSelectedSlots((current) =>
      current.includes(slot) ? current.filter((item) => item !== slot) : [...current, slot],
    );
  };

  const patchIntent = (patch: Partial<StyleIntent>) => {
    setIntent((current) => ({ ...current, ...patch }));
  };

  const saveRule = () => {
    const slotsToSave = selectedSlots.length > 0 ? selectedSlots : ["section"];
    const target: StyleRule["target"] =
      scope === "global"
        ? { scope: "global" }
        : scope === "sectionType"
          ? { scope: "sectionType", sectionType }
          : { scope: "sectionId", sectionId: sectionId.trim() || "summary" };
    const nextRule: StyleRule = {
      id: editingId ?? createRuleId(),
      label: label.trim() || undefined,
      enabled: true,
      target,
      slots: Object.fromEntries(slotsToSave.map((slotId) => [slotId, intent])),
    };

    commit((draft) => {
      const existing = draft.metadata.styleRules.findIndex((rule) => rule.id === nextRule.id);
      if (existing >= 0) {
        draft.metadata.styleRules[existing] = {
          ...draft.metadata.styleRules[existing],
          ...nextRule,
          enabled: draft.metadata.styleRules[existing].enabled,
        };
      } else {
        draft.metadata.styleRules.push(nextRule);
      }
    });
    closeDialog();
  };

  const toggleRule = (ruleId: string) => {
    commit((draft) => {
      const rule = draft.metadata.styleRules.find((item) => item.id === ruleId);
      if (rule) rule.enabled = !rule.enabled;
    });
  };

  const deleteRule = (ruleId: string) => {
    commit((draft) => {
      draft.metadata.styleRules = draft.metadata.styleRules.filter((rule) => rule.id !== ruleId);
    });
  };

  return (
    <div data-testid="styles-panel" className="flex h-full flex-col gap-3 overflow-y-auto p-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-3">Style Rules</div>
        <button
          type="button"
          data-testid="styles-add-rule"
          onClick={openCreate}
          disabled={rules.length >= 50}
          className="inline-flex h-7 items-center gap-1 rounded border border-surface-border bg-surface px-2 text-xs text-ink-1 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
          <span>Add Rule</span>
        </button>
      </div>

      {rules.length === 0 ? (
        <div
          data-testid="styles-empty"
          className="rounded border border-dashed border-surface-border bg-surface-base p-4 text-xs text-ink-3"
        >
          No style rules yet.
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <div
              key={rule.id}
              data-testid={`styles-rule-${rule.id}`}
              className="rounded border border-surface-border bg-surface-base p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-xs font-medium text-ink-1">{rule.label || "Untitled rule"}</div>
                  <div className="mt-0.5 truncate text-[11px] text-ink-3">{summarizeRule(rule)}</div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    data-testid={`styles-rule-${rule.id}-toggle`}
                    aria-pressed={rule.enabled}
                    onClick={() => toggleRule(rule.id)}
                    className={[
                      "h-6 rounded border px-2 text-[11px]",
                      rule.enabled
                        ? "border-primary-300 bg-primary-50 text-primary-700"
                        : "border-surface-border bg-surface text-ink-3",
                    ].join(" ")}
                  >
                    {rule.enabled ? "On" : "Off"}
                  </button>
                  <button
                    type="button"
                    data-testid={`styles-rule-${rule.id}-edit`}
                    onClick={() => openEdit(rule)}
                    className="h-6 rounded border border-surface-border bg-surface px-2 text-[11px] text-ink-2 hover:bg-surface-muted"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    data-testid={`styles-rule-${rule.id}-delete`}
                    aria-label="Delete rule"
                    onClick={() => deleteRule(rule.id)}
                    className="inline-flex h-6 w-6 items-center justify-center rounded border border-surface-border bg-surface text-ink-2 hover:bg-surface-muted"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div
          data-testid="style-rule-dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4"
          role="dialog"
          aria-modal="true"
        >
          <div
            data-testid="style-rule-dialog-body"
            className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded bg-surface p-4 shadow-xl"
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink-1">{editingId ? "Edit Rule" : "Add Rule"}</h2>
              <button
                type="button"
                onClick={closeDialog}
                className="inline-flex h-7 w-7 items-center justify-center rounded border border-surface-border text-ink-2 hover:bg-surface-muted"
                aria-label="Close"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>

            <div className="grid gap-3 md:grid-cols-[1fr_1fr]">
              <label className="block space-y-1 md:col-span-2">
                <span className="text-xs text-ink-2">Label</span>
                <input
                  data-testid="style-rule-label"
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                />
              </label>

              <fieldset className="space-y-2 rounded border border-surface-border p-3">
                <legend className="px-1 text-xs text-ink-2">Target</legend>
                {(["global", "sectionType", "sectionId"] as TargetScope[]).map((nextScope) => (
                  <label key={nextScope} className="flex items-center gap-2 text-xs text-ink-1">
                    <input
                      type="radio"
                      name="style-rule-scope"
                      data-testid={`style-rule-scope-${nextScope}`}
                      checked={scope === nextScope}
                      onChange={() => setScope(nextScope)}
                    />
                    <span>{nextScope}</span>
                  </label>
                ))}
                {scope === "sectionType" && (
                  <select
                    value={sectionType}
                    onChange={(event) => setSectionType(event.target.value as SectionType)}
                    className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                  >
                    {SECTION_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                )}
                {scope === "sectionId" && (
                  <input
                    value={sectionId}
                    onChange={(event) => setSectionId(event.target.value)}
                    className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                  />
                )}
              </fieldset>

              <fieldset className="space-y-2 rounded border border-surface-border p-3">
                <legend className="px-1 text-xs text-ink-2">Slots</legend>
                <div className="grid grid-cols-2 gap-1">
                  {SLOT_IDS.map((slotId) => (
                    <label key={slotId} className="flex items-center gap-1 text-[11px] text-ink-1">
                      <input
                        type="checkbox"
                        data-testid={`style-rule-slot-${slotId}`}
                        checked={selectedSlots.includes(slotId)}
                        onChange={() => toggleSlot(slotId)}
                      />
                      <span>{slotId}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="space-y-3 md:col-span-2">
                <div className="flex flex-wrap gap-1">
                  {(["color", "text", "spacing", "border"] as IntentTab[]).map((intentTab) => (
                    <button
                      key={intentTab}
                      type="button"
                      data-testid={`style-rule-tab-${intentTab}`}
                      onClick={() => setTab(intentTab)}
                      className={[
                        "h-7 rounded border px-2 text-xs capitalize",
                        tab === intentTab
                          ? "border-primary-300 bg-primary-50 text-primary-700"
                          : "border-surface-border bg-surface-base text-ink-2 hover:bg-surface-muted",
                      ].join(" ")}
                    >
                      {intentTab}
                    </button>
                  ))}
                </div>

                {tab === "color" && (
                  <div className="grid gap-2 md:grid-cols-3">
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Color</span>
                      <input
                        data-testid="intent-color"
                        value={intent.color ?? ""}
                        onChange={(event) => patchIntent({ color: event.target.value })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Background</span>
                      <input
                        value={intent.backgroundColor ?? ""}
                        onChange={(event) => patchIntent({ backgroundColor: event.target.value })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Border</span>
                      <input
                        value={intent.borderColor ?? ""}
                        onChange={(event) => patchIntent({ borderColor: event.target.value })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      />
                    </label>
                  </div>
                )}

                {tab === "text" && (
                  <div className="grid gap-2 md:grid-cols-3">
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Font size</span>
                      <input
                        type="number"
                        min={6}
                        max={48}
                        value={intent.fontSize ?? ""}
                        onChange={(event) => patchIntent({ fontSize: Number(event.target.value) || undefined })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Weight</span>
                      <select
                        value={intent.fontWeight ?? ""}
                        onChange={(event) => patchIntent({ fontWeight: (event.target.value || undefined) as StyleIntent["fontWeight"] })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      >
                        <option value="">inherit</option>
                        {["300", "400", "500", "600", "700", "800"].map((weight) => (
                          <option key={weight} value={weight}>
                            {weight}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Align</span>
                      <select
                        value={intent.textAlign ?? ""}
                        onChange={(event) => patchIntent({ textAlign: (event.target.value || undefined) as StyleIntent["textAlign"] })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      >
                        <option value="">inherit</option>
                        {["left", "center", "right", "justify"].map((align) => (
                          <option key={align} value={align}>
                            {align}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}

                {tab === "spacing" && (
                  <div className="grid gap-2 md:grid-cols-4">
                    {(["paddingTop", "paddingRight", "paddingBottom", "paddingLeft"] as const).map((field) => (
                      <label key={field} className="block space-y-1">
                        <span className="text-xs text-ink-2">{field}</span>
                        <input
                          type="number"
                          value={(intent[field] as number | undefined) ?? ""}
                          onChange={(event) => patchIntent({ [field]: Number(event.target.value) || undefined })}
                          className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                        />
                      </label>
                    ))}
                  </div>
                )}

                {tab === "border" && (
                  <div className="grid gap-2 md:grid-cols-3">
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Width</span>
                      <input
                        type="number"
                        min={0}
                        value={intent.borderWidth ?? ""}
                        onChange={(event) => patchIntent({ borderWidth: Number(event.target.value) || undefined })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Radius</span>
                      <input
                        type="number"
                        min={0}
                        value={intent.borderRadius ?? ""}
                        onChange={(event) => patchIntent({ borderRadius: Number(event.target.value) || undefined })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-xs text-ink-2">Style</span>
                      <select
                        value={intent.borderStyle ?? ""}
                        onChange={(event) => patchIntent({ borderStyle: (event.target.value || undefined) as StyleIntent["borderStyle"] })}
                        className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
                      >
                        <option value="">inherit</option>
                        {["solid", "dashed", "dotted"].map((style) => (
                          <option key={style} value={style}>
                            {style}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeDialog}
                className="h-8 rounded border border-surface-border bg-surface px-3 text-xs text-ink-2 hover:bg-surface-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="style-rule-save"
                onClick={saveRule}
                className="h-8 rounded bg-primary-600 px-3 text-xs font-medium text-white hover:bg-primary-700"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StylesPanel;
