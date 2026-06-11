import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

interface AppShellProps {
  children: ReactNode
  onNewResume?: () => void
}

export function AppShell({ children, onNewResume }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <div className="h-screen w-screen flex bg-surface-subtle dark:bg-dark-surface-subtle overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar onNewResume={onNewResume} />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
