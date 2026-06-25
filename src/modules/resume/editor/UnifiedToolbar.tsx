import { Link } from 'react-router-dom'
import { ArrowLeft, Save, History, Download, Palette, Code, List, PanelRight, UserCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import type { EditorMode } from './useModeToggle'
import type { ThemeId } from '@/modules/resume/themes'
import ThemeSelector from './ThemeSelector'
import ColorPicker from './ColorPicker'

interface UnifiedToolbarProps {
  branchName: string
  branchId: string
  mode: EditorMode
  onModeChange: (mode: EditorMode) => void
  versionCount: number
  onSaveVersion: () => void
  onOpenVersions: () => void
  onExport?: () => void
  onStyleSelect?: () => void
  onToggleSidebar?: () => void
  lockStatus?: React.ReactNode
  /** Current theme id (spec 027 US3). */
  themeId?: string
  /** Called when user selects a new theme. */
  onThemeSelect?: (themeId: ThemeId) => void | Promise<void>
  /** Current accent color HEX (spec 027 US3). */
  accentColor?: string
  /** Called when user picks a new accent color. */
  onAccentColorChange?: (hex: string) => void | Promise<void>
  /** Whether the branch has an avatar (spec 027 US9). */
  hasAvatar?: boolean
  /** Called when user clicks the avatar button. */
  onOpenAvatar?: () => void
}

export default function UnifiedToolbar({
  branchName,
  branchId,
  mode,
  onModeChange,
  versionCount,
  onSaveVersion,
  onOpenVersions,
  onExport,
  onStyleSelect,
  onToggleSidebar,
  lockStatus,
  themeId,
  onThemeSelect,
  accentColor,
  onAccentColorChange,
  hasAvatar,
  onOpenAvatar,
}: UnifiedToolbarProps) {
  return (
    <div className="h-12 flex items-center gap-1 px-4 bg-surface dark:bg-dark-surface border-b border-surface-border dark:border-dark-surface-border shadow-notion-sm">
      {/* Back + Title */}
      <Link
        to="/resume"
        className="btn-base btn-ghost btn-sm flex-shrink-0 gap-1"
        data-testid="toolbar-back"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        <span className="hidden sm:inline text-xs">简历中心</span>
      </Link>

      <div className="text-sm font-semibold text-ink-1 dark:text-dark-ink-primary truncate flex-1 min-w-0 px-2">
        {branchName}
      </div>

      {/* Mode Toggle — Tabs style */}
      <div className="flex items-center gap-0.5 bg-surface-muted dark:bg-dark-surface-muted rounded-md p-0.5 flex-shrink-0">
        <button
          onClick={() => onModeChange('quick')}
          aria-pressed={mode === 'quick'}
          aria-label="快捷模式"
          className={cn(
            'inline-flex items-center gap-1.5 h-7 px-2.5 rounded text-xs font-medium transition-colors',
            mode === 'quick'
              ? 'bg-surface dark:bg-dark-surface text-ink-1 dark:text-dark-ink-primary shadow-notion-sm'
              : 'text-ink-3 dark:text-dark-ink-tertiary hover:text-ink-1 dark:hover:text-dark-ink-primary',
          )}
        >
          <List className="h-3 w-3" />
          <span className="hidden sm:inline">快捷</span>
        </button>
        <button
          onClick={() => onModeChange('code')}
          aria-pressed={mode === 'code'}
          aria-label="代码模式"
          className={cn(
            'inline-flex items-center gap-1.5 h-7 px-2.5 rounded text-xs font-medium transition-colors',
            mode === 'code'
              ? 'bg-surface dark:bg-dark-surface text-ink-1 dark:text-dark-ink-primary shadow-notion-sm'
              : 'text-ink-3 dark:text-dark-ink-tertiary hover:text-ink-1 dark:hover:text-dark-ink-primary',
          )}
        >
          <Code className="h-3 w-3" />
          <span className="hidden sm:inline">代码</span>
        </button>
      </div>

      {/* Style Selector placeholder */}
      {onStyleSelect && (
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<Palette className="h-3.5 w-3.5" />}
          onClick={onStyleSelect}
          className="flex-shrink-0"
        >
          <span className="hidden sm:inline">选择模板</span>
        </Button>
      )}

      {/* Theme selector (spec 027 US3) */}
      {onThemeSelect && themeId && (
        <ThemeSelector
          currentThemeId={themeId}
          onSelect={onThemeSelect}
        />
      )}

      {/* Color picker (spec 027 US3) */}
      {onAccentColorChange && accentColor && (
        <ColorPicker
          currentColor={accentColor}
          onColorChange={onAccentColorChange}
        />
      )}

      {/* Avatar button (spec 027 US9) */}
      {onOpenAvatar && (
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<UserCircle2 className={cn('h-3.5 w-3.5', hasAvatar && 'text-brand-500')} />}
          onClick={onOpenAvatar}
          data-testid="open-avatar-dialog"
          className="flex-shrink-0"
        >
          <span className="hidden sm:inline">头像</span>
        </Button>
      )}

      {/* Export button placeholder */}
      {onExport && (
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<Download className="h-3.5 w-3.5" />}
          onClick={onExport}
          data-testid="open-export-menu"
          className="flex-shrink-0"
        >
          <span className="hidden sm:inline">导出 pdf</span>
        </Button>
      )}

      {/* Sidebar toggle */}
      {onToggleSidebar && (
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<PanelRight className="h-3.5 w-3.5" />}
          onClick={onToggleSidebar}
          className="flex-shrink-0"
          aria-label="信息面板"
        >
          <span className="hidden sm:inline">面板</span>
        </Button>
      )}

      {/* Version controls */}
      <Button
        variant="secondary"
        size="sm"
        leftIcon={<History className="h-3.5 w-3.5" />}
        onClick={onOpenVersions}
        data-testid="open-versions"
        className="flex-shrink-0"
      >
        <span className="hidden sm:inline">历史</span>
        <span className="text-2xs text-ink-3 dark:text-dark-ink-tertiary ml-1 tabular-nums">({versionCount})</span>
      </Button>

      <Button
        variant="primary"
        size="sm"
        leftIcon={<Save className="h-3.5 w-3.5" />}
        onClick={onSaveVersion}
        data-testid="save-version"
        className="flex-shrink-0"
      >
        <span className="hidden sm:inline">保存版本</span>
      </Button>

      {/* Lock indicator */}
      {lockStatus}
    </div>
  )
}
