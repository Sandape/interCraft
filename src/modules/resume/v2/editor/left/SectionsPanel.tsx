// REQ-032 v2 MVP stub — SectionsPanel.
//
// The left panel normally renders a draggable list of the resume's
// 12 section types so users can add / reorder / hide them. The real
// implementation (drag-drop + per-item visibility + add/remove UI)
// ships in a later US phase. For the MVP we render the 12 sections
// as disabled buttons so the editor's left rail has the right shape
// for E2E selectors and visual regression baselines.
//
// The 12 section types mirror `backend/app/modules/resumes_v2/schemas.py`
// `SectionType`. We deliberately show all of them so the test
// selectors (`data-testid="section-button-{id}"`) can be exercised.

const SECTION_TYPES: { id: string; label: string }[] = [
  { id: "profiles", label: "Profiles" },
  { id: "experience", label: "Experience" },
  { id: "education", label: "Education" },
  { id: "projects", label: "Projects" },
  { id: "skills", label: "Skills" },
  { id: "languages", label: "Languages" },
  { id: "interests", label: "Interests" },
  { id: "awards", label: "Awards" },
  { id: "certifications", label: "Certifications" },
  { id: "publications", label: "Publications" },
  { id: "volunteer", label: "Volunteer" },
  { id: "references", label: "References" },
];

export default function SectionsPanel(): JSX.Element {
  return (
    <div
      data-testid="sections-panel-stub"
      className="flex h-full flex-col gap-1 overflow-y-auto p-2"
    >
      <div className="mb-2 text-xs font-semibold text-ink-3">Sections</div>
      {SECTION_TYPES.map((s) => (
        <button
          key={s.id}
          type="button"
          disabled
          data-testid={`section-button-${s.id}`}
          className="cursor-not-allowed rounded border border-surface-border bg-surface-muted px-2 py-1.5 text-left text-xs text-ink-3"
          title={`TODO: ${s.label} drag/reorder UI ships in a later US phase`}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}