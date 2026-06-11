import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Mail,
  Lock,
  Sparkles,
  ArrowRight,
  Github,
  Linkedin,
  Eye,
  EyeOff,
  Check,
  Chrome,
  Shield,
  Zap,
  Target,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { cn } from '@/lib/utils'

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [showPwd, setShowPwd] = useState(false)

  return (
    <div className="h-screen w-screen flex bg-surface dark:bg-dark-surface">
      {/* 左侧 - 品牌价值 */}
      <div className="hidden lg:flex flex-1 relative bg-gradient-to-br from-brand-900 via-brand-800 to-brand-900 dark:from-brand-900 dark:via-[#0B1220] dark:to-brand-900 p-12 flex-col justify-between overflow-hidden">
        {/* 装饰背景 */}
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-20 right-20 h-64 w-64 rounded-full bg-brand-500/30 blur-3xl" />
          <div className="absolute bottom-20 left-20 h-64 w-64 rounded-full bg-blue-500/20 blur-3xl" />
        </div>

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-md bg-white flex items-center justify-center shadow-notion">
            <Sparkles className="h-4 w-4 text-brand-900" strokeWidth={2.5} />
          </div>
          <div>
            <div className="text-base font-semibold text-white tracking-tight">InterCraft</div>
            <div className="text-2xs text-white/60">面试工坊</div>
          </div>
        </div>

        {/* 主标题 */}
        <div className="relative z-10 max-w-md">
          <h1 className="text-3xl font-semibold text-white leading-tight tracking-tight">
            AI 驱动的<br />技术求职赋能平台
          </h1>
          <p className="text-sm text-white/70 leading-relaxed mt-3">
            从核心简历管理到针对性优化，从沉浸式模拟面试到数据化能力画像，
            帮助每一位技术求职者精准匹配理想岗位。
          </p>

          <div className="space-y-2.5 mt-6">
            <Feature icon={<Target className="h-3.5 w-3.5" />} title="精准匹配" desc="基于 JD 自动优化简历" />
            <Feature icon={<Zap className="h-3.5 w-3.5" />} title="智能面试" desc="实时反馈与多维评分" />
            <Feature icon={<Shield className="h-3.5 w-3.5" />} title="数据安全" desc="ISO 27001 与等保三级" />
          </div>
        </div>

        {/* 底部数据 */}
        <div className="relative z-10 grid grid-cols-3 gap-4">
          <div>
            <div className="text-xl font-semibold text-white tabular-nums">12,800+</div>
            <div className="text-2xs text-white/60 mt-0.5">活跃用户</div>
          </div>
          <div>
            <div className="text-xl font-semibold text-white tabular-nums">86,500+</div>
            <div className="text-2xs text-white/60 mt-0.5">模拟面试</div>
          </div>
          <div>
            <div className="text-xl font-semibold text-white tabular-nums">92.3%</div>
            <div className="text-2xs text-white/60 mt-0.5">好评率</div>
          </div>
        </div>
      </div>

      {/* 右侧 - 表单 */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="h-8 w-8 rounded-md bg-gradient-to-br from-brand-900 to-brand-600 flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
            </div>
            <div className="text-sm font-semibold text-ink-1">InterCraft 面试工坊</div>
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-semibold text-ink-1 tracking-tight">
              {mode === 'login' ? '欢迎回来' : '创建账号'}
            </h2>
            <p className="text-sm text-ink-3 mt-1">
              {mode === 'login' ? '继续你的求职准备之旅' : '开始系统化的求职准备'}
            </p>
          </div>

          {/* 第三方登录 */}
          <div className="space-y-2 mb-5">
            <Button variant="secondary" size="lg" className="w-full" leftIcon={<Github className="h-4 w-4" />}>
              使用 GitHub 继续
            </Button>
            <Button variant="secondary" size="lg" className="w-full" leftIcon={<Linkedin className="h-4 w-4" />}>
              使用 LinkedIn 继续
            </Button>
            <Button variant="secondary" size="lg" className="w-full" leftIcon={<Chrome className="h-4 w-4" />}>
              使用 Google 继续
            </Button>
          </div>

          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-surface-border dark:bg-dark-surface-border" />
            <span className="text-2xs text-ink-3">或使用邮箱</span>
            <div className="flex-1 h-px bg-surface-border dark:bg-dark-surface-border" />
          </div>

          {/* 表单 */}
          <div className="space-y-3">
            {mode === 'register' && (
              <div>
                <label className="block text-xs font-medium text-ink-2 mb-1.5">姓名</label>
                <Input placeholder="请输入你的姓名" />
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">邮箱</label>
              <Input type="email" leftIcon={<Mail className="h-3.5 w-3.5" />} placeholder="you@example.com" />
            </div>
            <div>
              <label className="flex items-center justify-between text-xs font-medium text-ink-2 mb-1.5">
                <span>密码</span>
                {mode === 'login' && (
                  <a href="#" className="text-2xs text-brand-600 dark:text-brand-300 hover:underline font-normal">
                    忘记密码？
                  </a>
                )}
              </label>
              <Input
                type={showPwd ? 'text' : 'password'}
                leftIcon={<Lock className="h-3.5 w-3.5" />}
                rightIcon={
                  <button
                    type="button"
                    onClick={() => setShowPwd((v) => !v)}
                    className="text-ink-muted hover:text-ink-2 transition-colors"
                    aria-label={showPwd ? '隐藏密码' : '显示密码'}
                  >
                    {showPwd ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                }
                placeholder="至少 8 位字符"
              />
            </div>

            {mode === 'register' && (
              <div className="space-y-1.5 pt-1">
                <PasswordRule ok label="至少 8 位字符" />
                <PasswordRule ok label="包含数字与字母" />
                <PasswordRule label="包含特殊字符" />
              </div>
            )}

            <div className="flex items-start gap-2 pt-1">
              <input
                type="checkbox"
                id="agree"
                className="mt-0.5 h-3.5 w-3.5 rounded border-surface-border text-brand-500 focus:ring-2 focus:ring-brand-500/20"
              />
              <label htmlFor="agree" className="text-2xs text-ink-3 leading-relaxed">
                我已阅读并同意
                <a href="#" className="text-brand-600 dark:text-brand-300 hover:underline mx-0.5">
                  《服务协议》
                </a>
                和
                <a href="#" className="text-brand-600 dark:text-brand-300 hover:underline mx-0.5">
                  《隐私政策》
                </a>
              </label>
            </div>

            <Button
              variant="primary"
              size="lg"
              className="w-full"
              rightIcon={<ArrowRight className="h-4 w-4" />}
            >
              {mode === 'login' ? '登录' : '创建账号'}
            </Button>
          </div>

          <div className="text-center text-sm text-ink-3 mt-5">
            {mode === 'login' ? '还没有账号？' : '已有账号？'}
            <button
              onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
              className="text-brand-600 dark:text-brand-300 font-medium ml-1 hover:underline"
            >
              {mode === 'login' ? '立即注册' : '直接登录'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Feature({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="h-6 w-6 rounded-md bg-white/10 backdrop-blur flex items-center justify-center flex-shrink-0 mt-0.5 text-white">
        {icon}
      </div>
      <div>
        <div className="text-sm font-medium text-white">{title}</div>
        <div className="text-2xs text-white/60 mt-0.5">{desc}</div>
      </div>
    </div>
  )
}

function PasswordRule({ ok, label }: { ok?: boolean; label: string }) {
  return (
    <div className={cn('flex items-center gap-1.5 text-2xs', ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-ink-3')}>
      <div
        className={cn(
          'h-3 w-3 rounded-full flex items-center justify-center',
          ok ? 'bg-emerald-500 text-white' : 'border border-ink-muted',
        )}
      >
        {ok && <Check className="h-2 w-2" strokeWidth={3} />}
      </div>
      {label}
    </div>
  )
}
