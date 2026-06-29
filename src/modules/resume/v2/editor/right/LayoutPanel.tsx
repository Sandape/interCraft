// REQ-032 v2 MVP stub — LayoutPanel.
//
// The Layout tab is part of the right-side Settings panel. The real
// implementation (sidebar width, page main/sidebar assignments) ships
// in a later US phase. For the MVP we render a TODO placeholder so
// the editor doesn't crash when the user clicks the "Layout" tab.

export default function LayoutPanel(): JSX.Element {
  return (
    <div data-testid="layout-panel-stub" className="p-4 text-sm text-ink-3">
      TODO: LayoutPanel (sidebar width + page main/sidebar) ships in a later US phase.
    </div>
  );
}