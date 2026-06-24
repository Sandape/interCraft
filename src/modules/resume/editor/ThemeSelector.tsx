/**
 * Theme selector — 4 木及风格主题缩略图选择器.
 * Spec 027 US3.
 */
import { useEffect, useState } from 'react'
import { Palette, Check } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { listThemes, loadTheme, type ThemeId } from '@/modules/resume/themes'
import { cn } from '@/lib/utils'

interface ThemeSelectorProps {
  currentThemeId: string
  onSelect: (themeId: ThemeId) => void | Promise<void>
  className?: string
}

export default function ThemeSelector({
  currentThemeId,
  onSelect,
  className = '',
}: ThemeSelectorProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const themes = listThemes()

  async function handleSelect(themeId: ThemeId) {
    setLoading(true)
    try {
      await loadTheme(themeId)
      await onSelect(themeId)
    } catch (err) {
      console.error('Failed to load theme:', err)
    } finally {
      setLoading(false)
      setOpen(false)
    }
  }

  // Preload current theme on mount
  useEffect(() => {
    loadTheme(currentThemeId).catch(console.error)
  }, [currentThemeId])

  return (
    <>
      <Button
        variant="ghost"
        leftIcon={<Palette className="h-3.5 w-3.5" />}
        onClick={() => setOpen(true)}
        data-testid="theme-selector-button"
        className={className}
      >
        主题
      </Button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="选择主题"
        description="4 套木及风格主题，切换即时生效"
        size="md"
      >
        <div className="grid grid-cols-2 gap-3" data-testid="theme-grid">
          {themes.map((theme) => {
            const isActive = theme.id === currentThemeId
            return (
              <button
                key={theme.id}
                onClick={() => handleSelect(theme.id)}
                disabled={loading}
                data-testid={`theme-option-${theme.id}`}
                className={cn(
                  'relative p-3 rounded-lg border-2 transition-all text-left',
                  isActive
                    ? 'border-brand-500 bg-brand-50/50 dark:bg-brand-500/10'
                    : 'border-surface-border dark:border-dark-surface-border hover:border-brand-300',
                )}
              >
                {/* Theme preview swatch */}
                <div
                  className="h-16 rounded-md mb-2 flex items-end p-2"
                  style={{
                    background: theme.defaultColor === '#39393a' ? '#f5f5f5' : theme.defaultColor + '22',
                  }}
                >
                  <div
                    className="flex-1 h-1.5 rounded-full"
                    style={{ background: theme.defaultColor }}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-ink-1">{theme.name}</div>
                    <div className="text-2xs text-ink-3 font-mono">{theme.defaultColor}</div>
                  </div>
                  {isActive && (
                    <Check className="h-3.5 w-3.5 text-brand-600" data-testid={`theme-active-${theme.id}`} />
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </Modal>
    </>
  )
}
