/**
 * LogsAndTraces — REQ-044 FR-005 + US5.
 *
 * Re-export of the existing LogCenter business logic under the new
 * 8-workspace IA shell. The internal `LogCenter*` component names
 * remain so existing test snapshots / deep imports keep resolving.
 *
 * The legacy `LogCenter` page (REQ-039 B2) is preserved as an alias
 * for backward compatibility, but the active route / sidebar now
 * points at this `LogsAndTraces` symbol.
 */
import { LogCenter as _LogsAndTraces } from './LogCenter'

export function LogsAndTraces() {
  return <_LogsAndTraces />
}
export { LogCenter } from './LogCenter'