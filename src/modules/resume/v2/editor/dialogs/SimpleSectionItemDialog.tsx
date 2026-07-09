import { useRef, useState } from "react";
import type { SectionType } from "../../schema/data";
import { useResumeV2Store } from "../../store";
import { fireToast } from "../center/toast";

interface SimpleSectionItemDialogProps {
  onClose: () => void;
  sectionId: SectionType;
  itemId: string;
}

type ItemRecord = Record<string, unknown> & {
  id: string;
  hidden?: boolean;
  website?: {
    url: string;
    label: string;
    inlineLink: boolean;
  };
  keywords?: string[];
};

const DIALOG_FIELDS: Partial<Record<SectionType, string[]>> = {
  awards: ["title", "awarder", "date"],
  certifications: ["title", "issuer", "date"],
  publications: ["title", "publisher", "date"],
  volunteer: ["organization", "location", "period"],
  references: ["name", "position", "phone"],
  interests: ["icon", "iconColor", "name"],
};

function isAllowedUrl(value: string): boolean {
  if (!value.trim()) return true;
  return /^(https?:|mailto:)/i.test(value.trim());
}

function sectionItems(data: ReturnType<typeof useResumeV2Store.getState>["data"], sectionId: SectionType): ItemRecord[] {
  const section = data.sections[sectionId] as unknown as { items?: ItemRecord[] };
  return section.items ?? [];
}

export function SimpleSectionItemDialog({
  onClose,
  sectionId,
  itemId,
}: SimpleSectionItemDialogProps): JSX.Element {
  const item = useResumeV2Store((s) =>
    sectionItems(s.data, sectionId).find((candidate) => candidate.id === itemId),
  );
  const setDataMut = useResumeV2Store((s) => s.setDataMut);
  const [urlError, setUrlError] = useState(false);
  const reorderTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  if (!item) {
    return (
      <div data-testid={`${sectionId}-dialog-missing`} className="p-4 text-xs text-ink-3">
        Item not found.
      </div>
    );
  }

  const updateItem = (
    updater: (draft: ItemRecord) => void,
    opts?: { skipHistory?: boolean },
  ) => {
    setDataMut((data) => {
      const draft = sectionItems(data, sectionId).find((candidate) => candidate.id === itemId);
      if (draft) updater(draft);
    }, opts);
  };

  const setField = (field: string, value: unknown) => {
    updateItem((draft) => {
      draft[field] = value;
    });
  };

  const updateWebsite = (field: "url" | "label" | "inlineLink", value: string | boolean) => {
    updateItem((draft) => {
      const website = draft.website ?? { url: "", label: "", inlineLink: false };
      draft.website = { ...website, [field]: value };
    });
  };

  const renderTextInput = (field: string) => (
    <input
      key={field}
      data-testid={`${sectionId}-${field.replace("iconColor", "icon-color")}`}
      value={String(item[field] ?? "")}
      onChange={(event) => setField(field, event.target.value)}
      className="w-full rounded border border-surface-border px-2 py-1 text-xs"
    />
  );

  const renderWebsiteFields = () => {
    if (!("website" in item)) return null;
    return (
      <div className="space-y-1">
        <input
          data-testid={`${sectionId}-website-url`}
          value={item.website?.url ?? ""}
          onChange={(event) => updateWebsite("url", event.target.value)}
          onBlur={(event) => {
            const unsafe = !isAllowedUrl(event.currentTarget.value);
            setUrlError(unsafe);
            if (unsafe) fireToast("Only http, https, and mailto links are allowed.", "warn");
          }}
          className="w-full rounded border border-surface-border px-2 py-1 text-xs"
        />
        {urlError ? (
          <div data-testid={`${sectionId}-website-url-error`} className="text-[10px] text-rose-600">
            Unsafe URL scheme.
          </div>
        ) : null}
        <input
          data-testid={`${sectionId}-website-label`}
          value={item.website?.label ?? ""}
          onChange={(event) => updateWebsite("label", event.target.value)}
          className="w-full rounded border border-surface-border px-2 py-1 text-xs"
        />
        <label className="inline-flex items-center gap-1 text-xs">
          <input
            data-testid={`${sectionId}-website-inline-link`}
            type="checkbox"
            checked={Boolean(item.website?.inlineLink)}
            onChange={(event) => updateWebsite("inlineLink", event.target.checked)}
          />
          Inline link
        </label>
      </div>
    );
  };

  const renderDescription = () => {
    if (!("description" in item)) return null;
    return (
      <div data-testid={`${sectionId}-description-wrap`}>
        <textarea
          data-testid={`${sectionId}-description`}
          value={String(item.description ?? "")}
          onChange={(event) => setField("description", event.target.value)}
          className="w-full rounded border border-surface-border px-2 py-1 text-xs"
        />
      </div>
    );
  };

  const renderHidden = () => (
    <label className="inline-flex items-center gap-1 text-xs">
      <input
        data-testid={`${sectionId}-hidden`}
        type="checkbox"
        checked={Boolean(item.hidden)}
        onChange={(event) => setField("hidden", event.target.checked)}
      />
      Hidden
    </label>
  );

  const moveKeyword = (from: number, to: number) => {
    const skipHistory = reorderTimer.current !== null;
    updateItem((draft) => {
      const keywords = [...(draft.keywords ?? [])];
      const [moved] = keywords.splice(from, 1);
      if (moved === undefined) return;
      keywords.splice(to, 0, moved);
      draft.keywords = keywords;
    }, { skipHistory });
    if (reorderTimer.current) clearTimeout(reorderTimer.current);
    reorderTimer.current = setTimeout(() => {
      reorderTimer.current = null;
    }, 500);
  };

  if (sectionId === "languages") {
    const level = Number(item.level ?? 0);
    const levelLabel = level === 0 ? "Hidden" : `${level} / 5`;
    return (
      <div data-testid="languages-dialog" className="space-y-2">
        {renderTextInput("language")}
        {renderTextInput("fluency")}
        <input
          data-testid="languages-level"
          type="range"
          min={0}
          max={5}
          step={1}
          value={level}
          onChange={(event) => setField("level", Number(event.target.value))}
        />
        <input
          data-testid="languages-level-input"
          value={String(level)}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (!Number.isInteger(next) || next < 0 || next > 5) {
              setUrlError(true);
              fireToast("Level must be an integer from 0 to 5.", "warn");
              return;
            }
            setUrlError(false);
            setField("level", next);
          }}
          className="w-full rounded border border-surface-border px-2 py-1 text-xs"
        />
        <span data-testid="languages-level-label">{levelLabel}</span>
        {urlError ? <div data-testid="languages-level-error">Invalid level</div> : null}
        {renderHidden()}
        <button type="button" onClick={onClose} className="hidden">
          Close
        </button>
      </div>
    );
  }

  return (
    <div data-testid={`${sectionId}-dialog`} className="space-y-2">
      {(DIALOG_FIELDS[sectionId] ?? []).map(renderTextInput)}
      {sectionId === "interests" ? (
        <div data-testid="interests-keywords" className="space-y-1">
          {(item.keywords ?? []).map((keyword, index) => (
            <div key={`${keyword}-${index}`} className="flex gap-1">
              <input
                data-testid={`interests-keyword-${index}`}
                value={keyword}
                onChange={(event) =>
                  updateItem((draft) => {
                    const keywords = [...(draft.keywords ?? [])];
                    keywords[index] = event.target.value;
                    draft.keywords = keywords;
                  })
                }
              />
              <button
                type="button"
                data-testid={`interests-keyword-remove-${index}`}
                onClick={() =>
                  updateItem((draft) => {
                    draft.keywords = (draft.keywords ?? []).filter((_, i) => i !== index);
                  })
                }
              >
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            data-testid="interests-keywords-add"
            onClick={() =>
              updateItem((draft) => {
                draft.keywords = [...(draft.keywords ?? []), ""];
              })
            }
          >
            Add
          </button>
          {[0, 1, 2].map((from) =>
            [0, 1, 2].map((to) => (
              <button
                key={`${from}-${to}`}
                type="button"
                data-testid={`interests-test-reorder-${from}-${to}`}
                onClick={() => moveKeyword(from, to)}
                className="hidden"
              >
                Reorder
              </button>
            )),
          )}
        </div>
      ) : null}
      {renderWebsiteFields()}
      {renderHidden()}
      {renderDescription()}
      <button type="button" onClick={onClose} className="hidden">
        Close
      </button>
    </div>
  );
}

