import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  User,
  CreditCard,
  Bell,
  Lock,
  Download,
  Smartphone,
  ChevronRight,
  FileText,
  Check,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Progress } from '@/components/ui/Progress'
import { ProfileTab } from '@/components/settings/ProfileTab'
import SubscriptionTab from '@/components/settings/SubscriptionTab'
import DevicesTab from '@/components/settings/DevicesTab'
import SecurityTab from '@/components/settings/SecurityTab'
import ExportTab from '@/components/settings/ExportTab'
import { cn } from '@/lib/utils'

const SETTINGS_TABS = ['profile', 'devices', 'subscription', 'security', 'export', 'notifications', 'privacy'] as const
type SettingsTab = typeof SETTINGS_TABS[number]

function normalizeSettingsTab(value: string | null): SettingsTab {
  return SETTINGS_TABS.includes(value as SettingsTab) ? (value as SettingsTab) : 'profile'
}

export default function Settings() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = normalizeSettingsTab(searchParams.get('tab'))

  function setTab(next: SettingsTab) {
    setSearchParams({ tab: next })
  }

  return (
    <div className="px-8 py-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">设置</h1>
        <p className="text-sm text-ink-3 mt-1">管理你的账户、订阅、通知偏好与数据</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* 左侧导航 */}
        <div className="lg:col-span-1">
          <Card padding="sm">
            <nav className="space-y-0.5">
              <NavItem testId="settings-nav-profile" icon={<User className="h-4 w-4" />} label="个人资料" active={tab === 'profile'} onClick={() => setTab('profile')} />
              <NavItem testId="settings-nav-devices" icon={<Smartphone className="h-4 w-4" />} label="设备管理" active={tab === 'devices'} onClick={() => setTab('devices')} />
              <NavItem testId="settings-nav-subscription" icon={<CreditCard className="h-4 w-4" />} label="订阅与用量" active={tab === 'subscription'} onClick={() => setTab('subscription')} />
              <NavItem testId="settings-nav-security" icon={<Lock className="h-4 w-4" />} label="账号安全" active={tab === 'security'} onClick={() => setTab('security')} />
              <NavItem testId="settings-nav-export" icon={<Download className="h-4 w-4" />} label="数据导出" active={tab === 'export'} onClick={() => setTab('export')} />
              <NavItem testId="settings-nav-notifications" icon={<Bell className="h-4 w-4" />} label="通知设置" active={tab === 'notifications'} onClick={() => setTab('notifications')} />
              <NavItem testId="settings-nav-privacy" icon={<FileText className="h-4 w-4" />} label="数据隐私" active={tab === 'privacy'} onClick={() => setTab('privacy')} />
            </nav>
          </Card>
        </div>

        {/* 右侧内容 */}
        <div className="lg:col-span-3 space-y-4">
          {tab === 'profile' && <div data-testid="settings-panel-profile"><ProfileTab /></div>}
          {tab === 'devices' && <div data-testid="settings-panel-devices"><DevicesTab /></div>}
          {tab === 'subscription' && <div data-testid="settings-panel-subscription"><SubscriptionTab /></div>}
          {tab === 'security' && <div data-testid="settings-panel-security"><SecurityTab /></div>}
          {tab === 'export' && <div data-testid="settings-panel-export"><ExportTab /></div>}
          {tab === 'notifications' && <div data-testid="settings-panel-notifications"><NotificationsTab /></div>}
          {tab === 'privacy' && <div data-testid="settings-panel-privacy"><PrivacyTab /></div>}
        </div>
      </div>
    </div>
  )
}

// ---- Sub-tabs (inline for now, no complex backend integration needed) ----

function NotificationsTab() {
  const [emailNotif, setEmailNotif] = useState(true)
  const [pushNotif, setPushNotif] = useState(false)
  const [weeklyReport, setWeeklyReport] = useState(true)
  const [interviewReminder, setInterviewReminder] = useState(true)

  return (
    <Card className="p-5">
      <CardHeader title="通知偏好" />
      <div className="space-y-3">
        <ToggleRow title="邮件通知" desc="面试报告、简历优化结果通过邮件发送" checked={emailNotif} onChange={setEmailNotif} />
        <div className="divider" />
        <ToggleRow title="浏览器推送" desc="新面试提醒、错题复习提醒" checked={pushNotif} onChange={setPushNotif} />
        <div className="divider" />
        <ToggleRow title="每周能力报告" desc="每周一发送上周能力成长摘要" checked={weeklyReport} onChange={setWeeklyReport} />
        <div className="divider" />
        <ToggleRow title="面试预约提醒" desc="预约面试前 15 分钟提醒" checked={interviewReminder} onChange={setInterviewReminder} />
      </div>
    </Card>
  )
}

function PrivacyTab() {
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <CardHeader title="数据存储" description="了解我们如何保护你的数据" />
        <div className="space-y-2">
          <InfoRow label="数据存储位置" value="阿里云 · 北京" />
          <InfoRow label="数据加密" value="AES-256（传输 + 存储）" />
          <InfoRow label="备份频率" value="每日增量 + 每周全量" />
          <InfoRow label="合规认证" value="ISO 27001 · 等保三级" />
        </div>
        <div className="mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border text-xs text-ink-3">
          我们承诺：你的数据仅用于 AI 优化你的求职准备，不会用于任何模型训练或第三方共享。
        </div>
      </Card>
    </div>
  )
}

function NavItem({
  icon,
  label,
  active,
  onClick,
  testId,
}: {
  icon: React.ReactNode
  label: string
  active?: boolean
  onClick?: () => void
  testId?: string
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 px-2.5 h-8 rounded text-sm transition-colors',
        active
          ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-700 dark:text-brand-300 font-medium'
          : 'text-ink-2 dark:text-dark-ink-secondary hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:text-ink-1 dark:hover:text-dark-ink-primary',
      )}
    >
      {icon}
      <span className="flex-1 text-left">{label}</span>
      {active && <ChevronRight className="h-3.5 w-3.5" />}
    </button>
  )
}

function Field({
  label,
  type = 'text',
  defaultValue,
  placeholder,
}: {
  label: string
  type?: string
  defaultValue?: string
  placeholder?: string
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-ink-2 mb-1.5">{label}</label>
      <Input type={type} defaultValue={defaultValue} placeholder={placeholder} />
    </div>
  )
}

function ThirdPartyItem({
  icon,
  name,
  desc,
  connected,
}: {
  icon: React.ReactNode
  name: string
  desc: string
  connected?: boolean
}) {
  return (
    <div className="flex items-center justify-between p-3 rounded-md border border-surface-border dark:border-dark-surface-border">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-md bg-surface-muted dark:bg-dark-surface-muted flex items-center justify-center">
          {icon}
        </div>
        <div>
          <div className="text-sm font-medium text-ink-1">{name}</div>
          <div className="text-2xs text-ink-3 mt-0.5">{desc}</div>
        </div>
      </div>
      {connected ? (
        <Badge variant="success" leftIcon={<Check className="h-2.5 w-2.5" />}>
          已绑定
        </Badge>
      ) : (
        <Button size="sm" variant="secondary">
          绑定
        </Button>
      )}
    </div>
  )
}

function ToggleRow({
  title,
  desc,
  checked,
  onChange,
}: {
  title: string
  desc: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-sm font-medium text-ink-1">{title}</div>
        <div className="text-2xs text-ink-3 mt-0.5">{desc}</div>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-5 w-9 rounded-full transition-colors',
          checked ? 'bg-brand-500' : 'bg-ink-muted/40',
        )}
        role="switch"
        aria-checked={checked}
      >
        <span
          className={cn(
            'absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-notion-sm transition-transform',
            checked ? 'left-[18px]' : 'left-0.5',
          )}
        />
      </button>
    </div>
  )
}

function PlanFeature({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-2xs text-ink-3">{label}</div>
      <div className="text-base font-semibold text-ink-1 mt-0.5">{value}</div>
    </div>
  )
}

function UsageBar({ label, used, total }: { label: string; used: number; total: number }) {
  const pct = (used / total) * 100
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-2">{label}</span>
        <span className="text-ink-3 tabular-nums">
          {used} <span className="text-ink-muted">/ {total}</span>
        </span>
      </div>
      <Progress value={pct} size="sm" variant={pct > 80 ? 'warning' : 'brand'} />
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-ink-3">{label}</span>
      <span className="text-sm text-ink-1 font-medium">{value}</span>
    </div>
  )
}
