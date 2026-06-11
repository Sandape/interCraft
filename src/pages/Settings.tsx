import { useState } from 'react'
import {
  User,
  CreditCard,
  Bell,
  Lock,
  Download,
  Trash2,
  Check,
  Mail,
  Github,
  Linkedin,
  Sparkles,
  Crown,
  Calendar,
  ChevronRight,
  Shield,
  AlertTriangle,
  FileText,
  Settings as SettingsIcon,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Tabs } from '@/components/ui/Tabs'
import { Avatar } from '@/components/ui/Avatar'
import { Input, Textarea } from '@/components/ui/Input'
import { Progress } from '@/components/ui/Progress'
import { currentUser } from '@/data/mockData'
import { cn } from '@/lib/utils'

export default function Settings() {
  const [tab, setTab] = useState('profile')
  const [emailNotif, setEmailNotif] = useState(true)
  const [pushNotif, setPushNotif] = useState(false)
  const [weeklyReport, setWeeklyReport] = useState(true)
  const [interviewReminder, setInterviewReminder] = useState(true)

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
              <NavItem icon={<User className="h-4 w-4" />} label="个人资料" active={tab === 'profile'} onClick={() => setTab('profile')} />
              <NavItem icon={<CreditCard className="h-4 w-4" />} label="订阅与计费" active={tab === 'billing'} onClick={() => setTab('billing')} />
              <NavItem icon={<Bell className="h-4 w-4" />} label="通知设置" active={tab === 'notifications'} onClick={() => setTab('notifications')} />
              <NavItem icon={<Lock className="h-4 w-4" />} label="账号安全" active={tab === 'security'} onClick={() => setTab('security')} />
              <NavItem icon={<FileText className="h-4 w-4" />} label="数据与隐私" active={tab === 'data'} onClick={() => setTab('data')} />
            </nav>
          </Card>
        </div>

        {/* 右侧内容 */}
        <div className="lg:col-span-3 space-y-4">
          {tab === 'profile' && (
            <>
              <Card className="p-5">
                <CardHeader title="基础信息" />
                <div className="flex items-center gap-4 mb-4 pb-4 border-b border-surface-border dark:border-dark-surface-border">
                  <Avatar name={currentUser.name} size="xl" />
                  <div>
                    <Button size="sm" variant="secondary">
                      更换头像
                    </Button>
                    <div className="text-2xs text-ink-3 mt-1.5">支持 JPG、PNG，最大 2MB</div>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Field label="姓名" defaultValue={currentUser.name} />
                  <Field label="邮箱" defaultValue={currentUser.email} />
                  <Field label="当前职位" defaultValue="高级前端工程师" />
                  <Field label="工作年限" defaultValue="3 年" />
                  <Field label="所在城市" defaultValue="北京" />
                  <Field label="个人网站" placeholder="https://" />
                </div>
                <div className="mt-3">
                  <label className="block text-xs font-medium text-ink-2 mb-1.5">个人简介</label>
                  <Textarea
                    rows={3}
                    defaultValue="3 年大厂前端开发经验，专注于大型 SPA 性能优化与组件库架构设计。"
                  />
                </div>
                <div className="mt-4 flex justify-end gap-2">
                  <Button variant="ghost">取消</Button>
                  <Button variant="primary">保存修改</Button>
                </div>
              </Card>

              <Card className="p-5">
                <CardHeader title="第三方账号" description="绑定后可快速登录与同步数据" />
                <div className="space-y-2">
                  <ThirdPartyItem
                    icon={<Github className="h-4 w-4" />}
                    name="GitHub"
                    desc="@lin-haoran"
                    connected
                  />
                  <ThirdPartyItem
                    icon={<Linkedin className="h-4 w-4" />}
                    name="LinkedIn"
                    desc="未绑定"
                  />
                  <ThirdPartyItem
                    icon={<Mail className="h-4 w-4" />}
                    name="Google"
                    desc="未绑定"
                  />
                </div>
              </Card>
            </>
          )}

          {tab === 'billing' && (
            <>
              <Card className="p-6 bg-gradient-to-br from-brand-50/50 to-surface dark:from-brand-500/5 dark:to-dark-surface border-brand-200/60 dark:border-brand-500/20">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-md bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
                      <Crown className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-semibold text-ink-1">Pro 会员</h2>
                        <Badge variant="brand" leftIcon={<Sparkles className="h-2.5 w-2.5" />}>
                          当前
                        </Badge>
                      </div>
                      <div className="text-xs text-ink-3 mt-0.5 flex items-center gap-1.5">
                        <Calendar className="h-3 w-3" />
                        续费日期 2026-08-12 · ¥99/月
                      </div>
                    </div>
                  </div>
                  <Button variant="primary" size="sm">
                    升级到 Enterprise
                  </Button>
                </div>
                <div className="grid grid-cols-3 gap-3 pt-4 border-t border-surface-border dark:border-dark-surface-border">
                  <PlanFeature label="模拟面试次数" value="无限" />
                  <PlanFeature label="简历分支数" value="无限" />
                  <PlanFeature label="AI 优化额度" value="500 次/月" />
                </div>
              </Card>

              <Card className="p-5">
                <CardHeader title="使用情况" description="本月 AI 服务使用量" />
                <div className="space-y-3">
                  <UsageBar label="AI 简历优化" used={42} total={500} />
                  <UsageBar label="模拟面试" used={12} total={50} />
                  <UsageBar label="AI 提示" used={186} total={1000} />
                </div>
              </Card>

              <Card className="p-5">
                <CardHeader title="账单历史" />
                <div className="divide-y divide-surface-border dark:divide-dark-surface-border">
                  {[
                    { date: '2026-05-12', amount: 99, status: 'paid', invoice: 'INV-202605-001' },
                    { date: '2026-04-12', amount: 99, status: 'paid', invoice: 'INV-202604-001' },
                    { date: '2026-03-12', amount: 99, status: 'paid', invoice: 'INV-202603-001' },
                  ].map((b) => (
                    <div key={b.invoice} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                      <div>
                        <div className="text-sm font-medium text-ink-1">¥{b.amount}.00</div>
                        <div className="text-2xs text-ink-3 mt-0.5">{b.date} · {b.invoice}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="success" leftIcon={<Check className="h-2.5 w-2.5" />}>
                          已支付
                        </Badge>
                        <Button size="sm" variant="ghost" leftIcon={<Download className="h-3.5 w-3.5" />}>
                          发票
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}

          {tab === 'notifications' && (
            <Card className="p-5">
              <CardHeader title="通知偏好" />
              <div className="space-y-3">
                <ToggleRow
                  title="邮件通知"
                  desc="面试报告、简历优化结果通过邮件发送"
                  checked={emailNotif}
                  onChange={setEmailNotif}
                />
                <div className="divider" />
                <ToggleRow
                  title="浏览器推送"
                  desc="新面试提醒、错题复习提醒"
                  checked={pushNotif}
                  onChange={setPushNotif}
                />
                <div className="divider" />
                <ToggleRow
                  title="每周能力报告"
                  desc="每周一发送上周能力成长摘要"
                  checked={weeklyReport}
                  onChange={setWeeklyReport}
                />
                <div className="divider" />
                <ToggleRow
                  title="面试预约提醒"
                  desc="预约面试前 15 分钟提醒"
                  checked={interviewReminder}
                  onChange={setInterviewReminder}
                />
              </div>
            </Card>
          )}

          {tab === 'security' && (
            <>
              <Card className="p-5">
                <CardHeader title="登录密码" />
                <div className="space-y-3">
                  <Field label="当前密码" type="password" />
                  <Field label="新密码" type="password" />
                  <Field label="确认新密码" type="password" />
                  <div className="flex justify-end">
                    <Button variant="primary">更新密码</Button>
                  </div>
                </div>
              </Card>

              <Card className="p-5">
                <CardHeader title="两步验证" description="为账号增加额外安全层" />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-md bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                      <Shield className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-ink-1">身份验证器</div>
                      <div className="text-2xs text-ink-3 mt-0.5">使用 Google Authenticator</div>
                    </div>
                  </div>
                  <Button variant="secondary" size="sm">
                    启用
                  </Button>
                </div>
              </Card>

              <Card className="p-5 border-red-200/60 dark:border-red-500/20">
                <div className="flex items-start gap-3">
                  <div className="h-9 w-9 rounded-md bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-ink-1">危险操作</h3>
                    <p className="text-xs text-ink-3 mt-1 leading-relaxed">
                      注销账号会永久删除所有数据，包括简历、面试记录、能力画像。
                      此操作不可恢复。
                    </p>
                    <div className="mt-3">
                      <Button variant="danger" leftIcon={<Trash2 className="h-3.5 w-3.5" />}>
                        永久注销账号
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            </>
          )}

          {tab === 'data' && (
            <>
              <Card className="p-5">
                <CardHeader title="数据导出" description="下载你的所有数据" />
                <p className="text-sm text-ink-2 leading-relaxed mb-3">
                  导出包含所有简历分支、模拟面试记录、能力画像、错题本等数据。
                  数据格式为 JSON，可在 30 天内重新下载。
                </p>
                <Button variant="secondary" leftIcon={<Download className="h-3.5 w-3.5" />}>
                  申请数据导出
                </Button>
              </Card>

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
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  active?: boolean
  onClick?: () => void
}) {
  return (
    <button
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
