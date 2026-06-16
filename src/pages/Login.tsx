/**
 * Login page — uses `useLogin` mutation; on success navigates to /dashboard.
 */
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Mail, Lock, ArrowRight, Eye, EyeOff, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useLogin } from '@/hooks/mutations/useLogin'
import { useRegister } from '@/hooks/mutations/useRegister'
import { useAuthStore } from '@/stores/useAuthStore'
import { cn } from '@/lib/utils'
import { AuthError, ValidationError } from '@/api/errors'

export default function Login({ initialMode: initialModeProp }: { initialMode?: 'login' | 'register' } = {}) {
  const [search] = useSearchParams()
  const urlMode = search.get('mode') === 'register' ? 'register' : null
  const [mode, setMode] = useState<'login' | 'register'>(
    urlMode ?? initialModeProp ?? 'login',
  )
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)

  const login = useLogin()
  const register = useRegister()

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErrorMsg(null)
    if (mode === 'login') {
      login.mutate(
        { email, password },
        {
          onSuccess: (data) => {
            setUser(data.user)
            navigate('/dashboard', { replace: true })
          },
          onError: (err) => setErrorMsg(humanizeError(err)),
        },
      )
    } else {
      register.mutate(
        { email, password, display_name: displayName || null },
        {
          onSuccess: (data) => {
            setUser(data.user)
            navigate('/dashboard', { replace: true })
          },
          onError: (err) => setErrorMsg(humanizeError(err)),
        },
      )
    }
  }

  const submitting = login.isPending || register.isPending

  return (
    <div className="min-h-screen w-screen flex bg-surface dark:bg-dark-surface">
      <div className="hidden lg:flex flex-1 bg-gradient-to-br from-brand-900 via-brand-800 to-brand-900 p-12 flex-col justify-between">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-md bg-white flex items-center justify-center">
            <Sparkles className="h-4 w-4 text-brand-900" strokeWidth={2.5} />
          </div>
          <div className="text-base font-semibold text-white">InterCraft</div>
        </div>
        <div>
          <h1 className="text-3xl font-semibold text-white leading-tight tracking-tight">
            AI 驱动的<br />技术求职赋能平台
          </h1>
          <p className="text-sm text-white/70 mt-3 max-w-md">
            从简历管理到模拟面试，帮助每一位技术求职者精准匹配理想岗位。
          </p>
        </div>
        <div className="text-2xs text-white/50">
          © 2026 InterCraft. SOC 2 Type II 合规在审.
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-ink-1 tracking-tight">
              {mode === 'login' ? '欢迎回来' : '创建账号'}
            </h2>
            <p className="text-sm text-ink-3 mt-1">
              {mode === 'login' ? '继续你的求职准备之旅' : '开始系统化的求职准备'}
            </p>
          </div>

          {mode === 'register' && (
            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">姓名（可选）</label>
              <Input
                name="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="请输入你的姓名"
                autoComplete="name"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">邮箱</label>
            <Input
              type="email"
              name="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              leftIcon={<Mail className="h-3.5 w-3.5" />}
              placeholder="you@example.com"
              autoComplete="email"
              data-testid="email-input"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">密码</label>
            <Input
              type={showPwd ? 'text' : 'password'}
              name="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              leftIcon={<Lock className="h-3.5 w-3.5" />}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  className="text-ink-muted hover:text-ink-2"
                  aria-label={showPwd ? '隐藏密码' : '显示密码'}
                >
                  {showPwd ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              }
              placeholder="至少 8 位字符（数字+字母）"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              data-testid="password-input"
            />
          </div>

          {errorMsg && (
            <div
              role="alert"
              data-testid="auth-error"
              className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-md px-3 py-2"
            >
              {errorMsg}
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            className={cn('w-full')}
            rightIcon={<ArrowRight className="h-4 w-4" />}
            disabled={submitting}
            data-testid="auth-submit"
          >
            {submitting ? '处理中…' : mode === 'login' ? '登录' : '创建账号'}
          </Button>

          <div className="text-center text-sm text-ink-3">
            {mode === 'login' ? '还没有账号？' : '已有账号？'}
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setErrorMsg(null)
              }}
              className="text-brand-600 dark:text-brand-300 font-medium ml-1 hover:underline"
            >
              {mode === 'login' ? '立即注册' : '直接登录'}
            </button>
          </div>

          <div className="text-center text-2xs text-ink-3">
            <Link to="/" className="hover:underline">
              返回首页
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}

function humanizeError(err: unknown): string {
  if (err instanceof ValidationError) {
    if (err.code === 'auth.password_too_weak') return '密码强度不足：至少 8 位且包含数字与字母'
    if (err.code === 'auth.email_invalid') return '邮箱格式不正确'
    if (err.fieldErrors.length > 0) {
      return err.fieldErrors.map((f) => f.message).join('；')
    }
    return err.message
  }
  if (err instanceof AuthError) {
    if (err.code === 'auth.invalid_credentials' || err.code === 'auth.token_invalid') {
      return '邮箱或密码错误'
    }
    if (err.code === 'auth.email_taken') return '该邮箱已被注册'
    return err.message
  }
  if (err instanceof Error) return err.message
  return '未知错误'
}
