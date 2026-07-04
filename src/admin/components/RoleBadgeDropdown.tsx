/**
 * RoleBadgeDropdown — REQ-044 CROSS FR-002 role-aware test switcher.
 *
 * Upgrades the US1 (IA) role-badge from a static label into a
 * clickable dropdown that lets the dev / tester switch between the
 * 5 console roles without manually editing localStorage. This is
 * the same role string the ``AdminShell.resolveRole`` 4-layer
 * fallback understands, so the sidebar nav items + saved-view
 * filters update instantly.
 *
 * [CROSS-TEAM-DEBT] In production the role comes from the JWT
 * claims; the dropdown is a dev/test convenience. The component
 * still renders the dropdown in production builds because it is
 * gated behind ``import.meta.env.DEV`` — Phase 3 may move it
 * behind a feature flag instead.
 */
import { useState, useRef, useEffect } from 'react'
import type { ConsoleRole } from '../../types/admin-console'

const ROLES: ConsoleRole[] = [
  'pm',
  'operations',
  'maintainer',
  'reviewer',
  'owner',
]

const LABELS: Record<ConsoleRole, string> = {
  pm: 'PM',
  operations: 'Operations',
  maintainer: 'Maintainer',
  reviewer: 'Reviewer',
  owner: 'Owner',
  unknown: 'Unknown',
}

const STORAGE_KEY = 'auth-user'

interface RoleBadgeDropdownProps {
  /** The currently resolved role (from resolveRole()). */
  role: ConsoleRole
  /** Called when the tester picks a new role. */
  onRoleChange?: (role: ConsoleRole) => void
}

export function RoleBadgeDropdown({
  role,
  onRoleChange,
}: RoleBadgeDropdownProps) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  const handleSelect = (next: ConsoleRole) => {
    setOpen(false)
    if (typeof window !== 'undefined') {
      try {
        const raw = window.localStorage.getItem(STORAGE_KEY)
        const existing = raw ? JSON.parse(raw) : {}
        existing.role = next
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(existing))
      } catch {
        /* ignore */
      }
    }
    onRoleChange?.(next)
    // Trigger AdminShell re-render by dispatching a storage event.
    window.dispatchEvent(new StorageEvent('storage', { key: STORAGE_KEY }))
  }

  return (
    <div
      ref={wrapperRef}
      style={{ position: 'relative', display: 'inline-block' }}
      data-testid="topbar-role-badge-dropdown"
    >
      <button
        type="button"
        data-testid="topbar-role-badge"
        onClick={() => setOpen((v) => !v)}
        style={{
          background: 'transparent',
          border: '1px solid var(--ac-border-subtle)',
          color: 'var(--ac-ink)',
          padding: '2px 8px',
          borderRadius: 4,
          cursor: 'pointer',
          fontSize: 12,
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {LABELS[role] ?? 'Unknown'} ▾
      </button>
      {open && (
        <ul
          role="listbox"
          data-testid="topbar-role-badge-options"
          style={{
            position: 'absolute',
            right: 0,
            top: '100%',
            marginTop: 4,
            padding: 4,
            background: 'var(--ac-bg, #fff)',
            border: '1px solid var(--ac-border-subtle)',
            borderRadius: 4,
            listStyle: 'none',
            zIndex: 1000,
            minWidth: 160,
          }}
        >
          {ROLES.map((r) => (
            <li key={r}>
              <button
                type="button"
                data-testid={`topbar-role-option-${r}`}
                onClick={() => handleSelect(r)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  padding: '4px 8px',
                  background:
                    r === role
                      ? 'var(--ac-bg-selected, #eef2ff)'
                      : 'transparent',
                  border: 0,
                  borderRadius: 2,
                  cursor: 'pointer',
                  fontSize: 12,
                }}
              >
                {LABELS[r]}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default RoleBadgeDropdown