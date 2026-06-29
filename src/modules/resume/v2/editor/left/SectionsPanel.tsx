// REQ-032 v2 Batch 2 — SectionsPanel (real implementation).
//
// Replaces the disabled 12-button stub with a click-to-expand row per
// section. Each row exposes:
//   - section id (read-only label, e.g. "experience")
//   - title (editable text input → `data.sections.{id}.title`)
//   - icon (editable text input → `data.sections.{id}.icon`)
//   - hidden (toggle → `data.sections.{id}.hidden`)
//
// Drag/reorder (US4) is deferred; this batch covers visibility + meta
// edits only. The 12 section keys mirror `Sections` in
// `schema/data.ts` and the defaults in `schema/defaults.ts`.
//
// Mutations route through `setDataMut` so the store's debounced-save +
// undo-stack pipeline picks them up automatically.
//
// E2E selectors: `section-row-{id}`, `section-title-{id}`,
// `section-icon-{id}`, `section-hidden-{id}`.

import { useState } from "react";
import { useResumeV2Store } from "../../store";
import { useDialogStore } from "../dialogs/DialogHost";
import type { Sections, SectionType } from "../../schema/data";

// ── constants ─────────────────────────────────────────────────────────────

// Order matches the Onyx template's main column (see schema/defaults.ts).
const SECTION_IDS: readonly SectionType[] = [
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

// ── helpers ───────────────────────────────────────────────────────────────

type SectionValue = Sections[SectionType];

function getSection(sections: Sections, id: SectionType): SectionValue {
  return sections[id];
}

// ── row component ─────────────────────────────────────────────────────────

interface SectionRowProps {
  id: SectionType;
  value: SectionValue;
}

function SectionRow({ id, value }: SectionRowProps): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const setDataMut = useResumeV2Store((s) => s.setDataMut);

  const patchSection = (mutator: (draft: SectionValue) => void) => {
    setDataMut((draft) => {
      mutator(draft.sections[id] as SectionValue);
    });
  };

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    patchSection((d) => {
      d.title = e.target.value;
    });
  };

  const handleIconChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    patchSection((d) => {
      d.icon = e.target.value;
    });
  };

  const handleHiddenChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    patchSection((d) => {
      d.hidden = e.target.checked;
    });
  };

  return (
    <div
      data-testid={`section-row-${id}`}
      data-section-id={id}
      data-expanded={expanded ? "true" : "false"}
      className="rounded border border-surface-border bg-surface-base"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left text-xs text-ink-1"
      >
        <span className="font-medium">{value.title || id}</span>
        <span className="flex items-center gap-2 text-ink-3">
          {value.hidden && (
            <span
              data-testid={`section-hidden-badge-${id}`}
              className="rounded bg-amber-100 px-1 text-[10px] text-amber-700"
            >
              hidden
            </span>
          )}
          <span aria-hidden="true">{expanded ? "−" : "+"}</span>
        </span>
      </button>

      {expanded && (
        <div className="space-y-2 border-t border-surface-border p-2">
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">
              Title
            </span>
            <input
              type="text"
              value={value.title}
              onChange={handleTitleChange}
              placeholder={id}
              data-testid={`section-title-${id}`}
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wide text-ink-3">
              Icon (lucide key)
            </span>
            <input
              type="text"
              value={value.icon}
              onChange={handleIconChange}
              placeholder="briefcase"
              data-testid={`section-icon-${id}`}
              className="w-full rounded border border-surface-border bg-surface-base px-2 py-1 text-xs text-ink-1"
            />
          </label>

          <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-1">
            <input
              type="checkbox"
              checked={value.hidden}
              onChange={handleHiddenChange}
              data-testid={`section-hidden-${id}`}
              className="accent-primary-500"
            />
            <span>Hide this section</span>
          </label>
        </div>
      )}
    </div>
  );
}

// ── main panel ────────────────────────────────────────────────────────────

export default function SectionsPanel(): JSX.Element {
  const sections = useResumeV2Store((s) => s.data.sections);
  const openDialog = useDialogStore((s) => s.openDialog);

  return (
    <div
      data-testid="sections-panel"
      className="flex h-full flex-col gap-1 overflow-y-auto p-2"
    >
      <div className="mb-2 text-xs font-semibold text-ink-3">Sections</div>
      {/* REQ-034 US1: Basics + Picture entries sit ABOVE the 12 section rows
          so the editor exposes the "metadata" block first. `data-section-group`
          is asserted by AC-01b (DOM order) and AC-01 (testid for clicks). */}
      <button
        type="button"
        data-section-group="metadata"
        data-testid="section-row-basics"
        data-section-id="basics"
        onClick={() => openDialog({ type: "basics" })}
        className="flex w-full items-center justify-between gap-2 rounded border border-surface-border bg-surface-base px-2 py-1.5 text-left text-xs text-ink-1"
      >
        <span className="font-medium">Basics</span>
        <span aria-hidden="true" className="text-ink-3">→</span>
      </button>
      <button
        type="button"
        data-section-group="metadata"
        data-testid="section-row-picture"
        data-section-id="picture"
        onClick={() => openDialog({ type: "picture" })}
        className="flex w-full items-center justify-between gap-2 rounded border border-surface-border bg-surface-base px-2 py-1.5 text-left text-xs text-ink-1"
      >
        <span className="font-medium">Picture</span>
        <span aria-hidden="true" className="text-ink-3">→</span>
      </button>
      {/* Summary placeholder hook (US3 will replace this row with the
          real SummaryDialog opener). Keep the DOM order explicit so AC-01b
          snapshot can assert its position. */}
      <div
        data-section-group="metadata"
        data-testid="section-row-summary"
        data-section-id="summary"
        className="hidden"
      >
        summary
      </div>
      {SECTION_IDS.map((id) => (
        <SectionRow key={id} id={id} value={getSection(sections, id)} />
      ))}
    </div>
  );
}