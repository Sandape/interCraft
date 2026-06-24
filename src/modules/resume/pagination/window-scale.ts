/**
 * A4 preview auto-scale on narrow windows.
 * Ported from 木及简历 (D:\Project\react-resume-site\src\utils\window-event.ts).
 *
 * Single resize listener: scales the `.rs-view-inner` A4 preview (794px wide)
 * to fit smaller windows. When 1000 < windowWidth < 1250, applies a transform
 * scale; when ≥ 1250, resets to scale(1).
 */
const SELECTOR = '.rs-view-inner'
const MIN_WIDTH = 1000
const MAX_WIDTH = 1250
const EDITOR_MIN = 450 // split-pane left min width
const A4_WIDTH = 794

export function applyWindowScale(): void {
  const windowWidth = document.body.clientWidth
  const el = document.querySelector<HTMLElement>(SELECTOR)
  if (!el) return
  if (windowWidth < MAX_WIDTH && windowWidth > MIN_WIDTH) {
    const resetWidth = windowWidth - EDITOR_MIN
    const marginWidth = resetWidth * 0.2
    const ratio = Math.round((resetWidth * 0.8) / A4_WIDTH * 100) / 100
    el.style.transform = `scale(${ratio})`
    el.style.marginLeft = `${marginWidth / 2}px`
  } else if (windowWidth >= MAX_WIDTH) {
    el.style.transform = 'scale(1)'
    el.style.marginLeft = 'auto'
  }
}

let listenerAttached = false

/** Attach the resize listener. Idempotent — safe to call multiple times. */
export function attachWindowScaleListener(): () => void {
  if (listenerAttached) return () => {}
  listenerAttached = true
  const handler = () => applyWindowScale()
  window.addEventListener('resize', handler)
  // Apply once on attach
  applyWindowScale()
  return () => {
    window.removeEventListener('resize', handler)
    listenerAttached = false
  }
}
