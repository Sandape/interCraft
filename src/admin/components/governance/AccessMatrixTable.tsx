/**
 * AccessMatrixTable — REQ-044 FR-031 / AC-31.2.
 *
 * Renders the 5x8 RBAC matrix (role × workspace) where each cell
 * encodes "READ/WRITE/CHANGE/EXPORT/REVEAL/AUDIT" capability grants.
 *
 * Layout:
 * - Top header: workspace names (8 cols).
 * - Left header: role names (5 rows).
 * - Cell: 6-dot chip with allowed/denied per capability, with a
 *   tooltip listing the missing capabilities.
 */
import { useMemo } from 'react'
import type {
  AccessMatrixResponse,
  CapabilityToken,
  ConsoleRole,
  WorkspaceId,
} from '@/types/admin-governance'

interface Props {
  matrix: AccessMatrixResponse | undefined
  isLoading?: boolean
  error?: Error | null
}

const ROLES: ConsoleRole[] = [
  'pm',
  'operations',
  'maintainer',
  'reviewer',
  'owner',
]
const WORKSPACES: WorkspaceId[] = [
  'command-center',
  'product-analytics',
  'ai-operations',
  'incidents-badcases',
  'logs-and-traces',
  'users-accounts',
  'reports',
  'governance',
]
const CAPS: CapabilityToken[] = [
  'READ',
  'WRITE',
  'CHANGE',
  'EXPORT',
  'REVEAL',
  'AUDIT',
]

function buildLookups(matrix: AccessMatrixResponse | undefined) {
  const map = new Map<string, boolean>()
  if (!matrix) return map
  for (const entry of matrix.entries) {
    map.set(
      `${entry.role}|${entry.workspace}|${entry.capability}`,
      entry.allowed,
    )
  }
  return map
}

export function AccessMatrixTable({ matrix, isLoading, error }: Props) {
  const lookups = useMemo(() => buildLookups(matrix), [matrix])

  if (isLoading) {
    return (
      <div className="ac-gov-matrix" data-testid="access-matrix-loading">
        Loading access matrix…
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="ac-error-banner"
        data-testid="access-matrix-error"
        role="alert"
      >
        Failed to load access matrix.
      </div>
    )
  }

  if (!matrix) {
    return (
      <div className="ac-gov-matrix" data-testid="access-matrix-empty">
        No access matrix data.
      </div>
    )
  }

  return (
    <div className="ac-gov-matrix" data-testid="access-matrix-table">
      <table>
        <thead>
          <tr>
            <th>role \\ workspace</th>
            {WORKSPACES.map((ws) => (
              <th key={ws} data-testid={`workspace-col-${ws}`}>
                {ws}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROLES.map((role) => (
            <tr key={role} data-testid={`role-row-${role}`}>
              <td className="ac-gov-matrix__role-cell">{role}</td>
              {WORKSPACES.map((ws) => {
                const granted = CAPS.filter(
                  (cap) => lookups.get(`${role}|${ws}|${cap}`) === true,
                )
                const denied = CAPS.filter(
                  (cap) => lookups.get(`${role}|${ws}|${cap}`) !== true,
                )
                const allowedAll = denied.length === 0
                const allowedNone = granted.length === 0
                return (
                  <td
                    key={ws}
                    data-testid={`cell-${role}-${ws}`}
                    data-granted={granted.join(',')}
                    data-denied={denied.join(',')}
                    className={
                      allowedAll
                        ? 'ac-gov-matrix__cell-allowed'
                        : allowedNone
                          ? 'ac-gov-matrix__cell-denied'
                          : ''
                    }
                    title={`granted: ${granted.join(', ') || '(none)'}; denied: ${denied.join(', ')}`}
                  >
                    <span aria-label={`granted ${granted.length}/6`}>
                      {granted.length}/{CAPS.length}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default AccessMatrixTable
