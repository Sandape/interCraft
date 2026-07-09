/**
 * SettingsPanel — right-side tab container for the v2 editor.
 *
 * 036 Phase A.2 rehydrate: previously referenced by BuilderShell but
 * the file was deleted in an earlier commit. Rebuilds as a tab
 * container that mounts the existing right/* panel stubs:
 *   - DesignPanel     (color pickers, page format)
 *   - TypographyPanel (font controls, real impl)
 *   - StylesPanel
 *   - PagePanel
 *   - LayoutPanel
 *   - AnalysisPanel   (AI analysis)
 *
 * The panel uses the same props signature BuilderShell already passes
 * (data + onChange + resumeId + slug/owner/public metadata). Slug /
 * owner / public flags are forwarded to TypographyPanel where relevant
 * (sharing copy); other panels ignore them.
 */
import { useState } from 'react'
import type { ResumeDataV2 } from '../../schema/data'
import DesignPanel from './DesignPanel'
import TypographyPanel from './TypographyPanel'
import StylesPanel from './StylesPanel'
import PagePanel from './PagePanel'
import LayoutPanel from './LayoutPanel'
import { AnalysisPanel } from './AnalysisPanel'

export interface SettingsPanelProps {
  data: ResumeDataV2
  onChange: (next: ResumeDataV2) => void
  resumeId: string
  resumeSlug?: string
  ownerUsername?: string
  isPublic?: boolean
  passwordSet?: boolean
}

type Tab = 'design' | 'typography' | 'styles' | 'page' | 'layout' | 'analysis'

const TABS: { id: Tab; label: string }[] = [
  { id: 'design', label: '设计' },
  { id: 'typography', label: '字体' },
  { id: 'styles', label: '样式' },
  { id: 'page', label: '页面' },
  { id: 'layout', label: '布局' },
  { id: 'analysis', label: 'AI 分析' },
]

export function SettingsPanel(props: SettingsPanelProps) {
  const [tab, setTab] = useState<Tab>('design')

  return (
    <div
      data-testid="v2-settings-panel"
      className="flex h-full w-full flex-col bg-surface"
    >
      <div
        role="tablist"
        className="flex items-center gap-1 border-b border-surface-border dark:border-dark-surface-border px-2 py-1.5 overflow-x-auto"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            data-testid={`v2-settings-tab-${t.id}`}
            onClick={() => setTab(t.id)}
            className={
              'px-2 h-7 text-xs rounded transition-colors ' +
              (tab === t.id
                ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300 font-medium'
                : 'text-ink-3 hover:bg-surface-muted hover:text-ink-1')
            }
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto" data-testid={`v2-settings-pane-${tab}`}>
        {tab === 'design' && <DesignPanel data={props.data} onChange={props.onChange} />}
        {tab === 'typography' && <TypographyPanel data={props.data} onChange={props.onChange} />}
        {tab === 'styles' && <StylesPanel data={props.data} onChange={props.onChange} />}
        {tab === 'page' && <PagePanel data={props.data} onChange={props.onChange} />}
        {tab === 'layout' && <LayoutPanel data={props.data} onChange={props.onChange} />}
        {tab === 'analysis' && <AnalysisPanel resumeId={props.resumeId} />}
      </div>
    </div>
  )
}

export default SettingsPanel
