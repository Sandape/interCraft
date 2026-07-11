import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { CommandPalette } from './CommandPalette'

interface AppShellProps {
  children: ReactNode
}

const PUBLIC_PATHS = new Set(['/login', '/register'])

export function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(max-width: 640px)').matches : false,
  )
  const [paletteOpen, setPaletteOpen] = useState(false)
  const location = useLocation()

  const openPalette = useCallback(() => setPaletteOpen(true), [])
  const closePalette = useCallback(() => setPaletteOpen(false), [])
  const togglePalette = useCallback(() => setPaletteOpen((v) => !v), [])

  // Global shortcut: Ctrl/Cmd+K toggles the palette, suppressed on public pages.
  useEffect(() => {
    const isPublic = PUBLIC_PATHS.has(location.pathname)
    if (isPublic) return
    function handleKeyDown(event: KeyboardEvent) {
      const mod = event.ctrlKey || event.metaKey
      if (mod && (event.key === 'k' || event.key === 'K')) {
        event.preventDefault()
        togglePalette()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [location.pathname, togglePalette])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 640px)')
    const syncCollapsed = () => {
      if (media.matches) setCollapsed(true)
    }
    syncCollapsed()
    media.addEventListener('change', syncCollapsed)
    return () => media.removeEventListener('change', syncCollapsed)
  }, [])

  return (
    <div className="h-screen w-screen flex bg-surface-subtle dark:bg-dark-surface-subtle overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} onOpenSearch={openPalette} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar onOpenSearch={openPalette} />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  )
}
