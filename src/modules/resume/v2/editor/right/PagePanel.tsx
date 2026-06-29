// REQ-032 v2 MVP stub — PagePanel.
//
// The Page tab is part of the right-side Settings panel. The real
// implementation (margins, gaps, page format) ships in a later US
// phase. For the MVP we render a TODO placeholder so the editor
// doesn't crash when the user clicks the "Page" tab.

export default function PagePanel(): JSX.Element {
  return (
    <div data-testid="page-panel-stub" className="p-4 text-sm text-ink-3">
      TODO: PagePanel (margins / gaps / format) ships in a later US phase.
    </div>
  );
}