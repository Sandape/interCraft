import { Link } from 'react-router-dom'
import { ArrowLeft, Save, History, Download, Upload, Palette, Code, List, PanelRight } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { EditorMode } from './useModeToggle'

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
}: UnifiedToolbarProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface sticky top-0 z-10">
      {/* Back + Title */}
      <Link
        to="/resume"
        className="flex items-center gap-1 text-xs text-ink-3 hover:text-ink-1 flex-shrink-0 mr-1"
      >
        <ArrowLeft className="h-3 w-3" />
        <span className="hidden sm:inline">简历中心</span>
      </Link>

      <div className="flex-1 min-w-0">
        <h2 className="text-sm font-semibold text-ink-1 truncate">{branchName}</h2>
      </div>

      {/* Mode Toggle */}
      <div className="flex rounded-md border border-surface-border dark:border-dark-surface-border overflow-hidden flex-shrink-0">
        <button
          onClick={() => onModeChange('quick')}
          className={`px-2.5 py-1.5 text-xs flex items-center gap-1 transition-colors ${
            mode === 'quick'
              ? 'bg-brand-500 text-white'
              : 'bg-surface dark:bg-dark-surface text-ink-2 hover:bg-surface-muted'
          }`}
          aria-label="快捷模式"
        >
          <List className="h-3 w-3" />
          <span className="hidden sm:inline">快捷</span>
        </button>
        <button
          onClick={() => onModeChange('code')}
          className={`px-2.5 py-1.5 text-xs flex items-center gap-1 transition-colors ${
            mode === 'code'
              ? 'bg-brand-500 text-white'
              : 'bg-surface dark:bg-dark-surface text-ink-2 hover:bg-surface-muted'
          }`}
          aria-label="代码模式"
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
          <span className="hidden sm:inline">样式</span>
        </Button>
      )}

      {/* Export button placeholder */}
      {onExport && (
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<Download className="h-3.5 w-3.5" />}
          onClick={onExport}
          className="flex-shrink-0"
        >
          <span className="hidden sm:inline">导出</span>
        </Button>
      )}

      {/* Import button placeholder */}
      <Button
        variant="ghost"
        size="sm"
        leftIcon={<Upload className="h-3.5 w-3.5" />}
        className="flex-shrink-0 hidden"
      />

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
        <span className="hidden sm:inline">版本</span>
        <span className="text-2xs text-ink-3 ml-1">({versionCount})</span>
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
