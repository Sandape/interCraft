// REQ-032 v2 MVP stub — StylesPanel.
//
// The Styles tab is part of the right-side Settings panel. The real
// implementation (StyleRule editor: target + slots + enabled toggle)
// ships in a later US phase. For the MVP we render a TODO placeholder
// so the editor doesn't crash when the user clicks the "Styles" tab.

export default function StylesPanel(): JSX.Element {
  return (
    <div data-testid="styles-panel-stub" className="p-4 text-sm text-ink-3">
      TODO: StylesPanel (StyleRule editor) ships in a later US phase.
    </div>
  );
}