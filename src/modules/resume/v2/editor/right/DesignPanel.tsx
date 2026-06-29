// REQ-032 v2 MVP stub — DesignPanel.
//
// The Design tab is part of the right-side Settings panel. The real
// implementation (color pickers, level design, page format) ships in
// a later US phase. For the MVP we render a TODO placeholder so the
// editor doesn't crash when the user clicks the "Design" tab.

export default function DesignPanel(): JSX.Element {
  return (
    <div data-testid="design-panel-stub" className="p-4 text-sm text-ink-3">
      TODO: DesignPanel (color pickers + level design) ships in a later US phase.
    </div>
  );
}