import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import { cn } from '@/lib/utils'

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme()
  return (
    <button
      onClick={toggleTheme}
      className={cn(
        'inline-flex items-center justify-center h-7 w-7 rounded text-ink-3',
        'hover:bg-surface-muted hover:text-ink-1 transition-colors',
        'dark:hover:bg-dark-surface-muted dark:hover:text-dark-ink-primary',
        className,
      )}
      aria-label={theme === 'light' ? '切换到深色模式' : '切换到浅色模式'}
    >
      {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </button>
  )
}
