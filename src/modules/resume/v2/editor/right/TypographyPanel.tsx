// REQ-032 v2 MVP stub — TypographyPanel.
//
// The Typography tab is part of the right-side Settings panel. The
// real implementation (font family pickers, weight selectors, line
// height) ships in a later US phase. For the MVP we render a TODO
// placeholder so the editor doesn't crash when the user clicks the
// "Typography" tab.

export default function TypographyPanel(): JSX.Element {
  return (
    <div data-testid="typography-panel-stub" className="p-4 text-sm text-ink-3">
      TODO: TypographyPanel (font family + weight + size) ships in a later US phase.
    </div>
  );
}