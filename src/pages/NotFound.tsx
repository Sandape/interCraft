import { ArrowLeft, MapPinOff } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

export default function NotFound() {
  const location = useLocation()

  return (
    <div className="min-h-full px-4 py-12 sm:px-8 flex items-center justify-center">
      <section className="w-full max-w-lg text-center" aria-labelledby="not-found-title">
        <div className="mx-auto h-12 w-12 rounded-lg bg-surface-muted dark:bg-dark-surface-muted text-ink-2 dark:text-dark-ink-secondary flex items-center justify-center">
          <MapPinOff className="h-5 w-5" aria-hidden="true" />
        </div>
        <p className="mt-5 text-xs font-medium uppercase tracking-[0.16em] text-ink-3">404</p>
        <h1 id="not-found-title" className="mt-2 text-2xl font-semibold tracking-tight text-ink-1">
          页面不存在
        </h1>
        <p className="mt-2 text-sm leading-6 text-ink-3">
          当前链接可能已失效，或页面地址输入有误。你可以返回工作台继续使用。
        </p>
        <code className="mt-4 block truncate rounded-md bg-surface-muted dark:bg-dark-surface-muted px-3 py-2 text-xs text-ink-3">
          {location.pathname}
        </code>
        <Link
          to="/dashboard"
          className="mt-6 inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-ink-1 px-4 text-sm font-medium text-white transition-colors hover:bg-ink-2 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:ring-offset-2 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-100"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          返回工作台
        </Link>
      </section>
    </div>
  )
}
