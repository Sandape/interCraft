import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Layers3, Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { trackProductEvent } from '@/lib/product-events'

export function BrandLockup({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link to="/" className="inline-flex min-h-11 items-center gap-2.5" aria-label="InterCraft 首页">
      <span
        className={cn(
          'flex h-8 w-8 items-center justify-center rounded-md border',
          inverse ? 'border-white/20 bg-white text-brand-900' : 'border-brand-900 bg-brand-900 text-white',
        )}
      >
        <Layers3 className="h-4 w-4" strokeWidth={1.8} />
      </span>
      <span className={cn('text-sm font-semibold tracking-[-0.01em]', inverse ? 'text-white' : 'text-ink-1')}>
        InterCraft
      </span>
    </Link>
  )
}

export function PublicHeader() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const scrollRoot = document.querySelector<HTMLElement>('.public-product')
    const onScroll = () => setScrolled((scrollRoot?.scrollTop ?? window.scrollY) > 16)
    const eventTarget: HTMLElement | Window = scrollRoot ?? window
    onScroll()
    eventTarget.addEventListener('scroll', onScroll, { passive: true })
    return () => eventTarget.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={cn(
        'public-header fixed inset-x-0 top-0 z-50 border-b transition-[background-color,border-color,box-shadow] duration-200',
        scrolled || open
          ? 'border-surface-border bg-surface/95 shadow-notion-sm backdrop-blur-sm'
          : 'border-transparent bg-transparent',
      )}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
        <BrandLockup />

        <nav className="hidden items-center gap-7 md:flex" aria-label="首页导航">
          <a className="text-sm text-ink-2 transition-colors hover:text-ink-1" href="#workflow">
            求职闭环
          </a>
          <a className="text-sm text-ink-2 transition-colors hover:text-ink-1" href="#product-proof">
            产品实景
          </a>
          <a className="text-sm text-ink-2 transition-colors hover:text-ink-1" href="#scenarios">
            适用场景
          </a>
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Link to="/login" className="btn-ghost btn-lg">
            登录
          </Link>
          <Link
            to="/register"
            className="btn-primary btn-lg"
            onClick={() => trackProductEvent({ name: 'homepage_primary_cta', source: 'nav' })}
          >
            免费开始
          </Link>
        </div>

        <button
          type="button"
          className="btn-ghost flex h-11 w-11 p-0 md:hidden"
          aria-label={open ? '关闭导航' : '打开导航'}
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-surface-border bg-surface px-5 pb-5 pt-3 md:hidden">
          <nav className="grid gap-1" aria-label="移动端首页导航">
            {[
              ['#workflow', '求职闭环'],
              ['#product-proof', '产品实景'],
              ['#scenarios', '适用场景'],
            ].map(([href, label]) => (
              <a
                key={href}
                href={href}
                className="flex min-h-11 items-center border-b border-surface-border text-sm text-ink-2"
                onClick={() => setOpen(false)}
              >
                {label}
              </a>
            ))}
          </nav>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Link to="/login" className="btn-secondary btn-lg">
              登录
            </Link>
            <Link
              to="/register"
              className="btn-primary btn-lg"
              onClick={() => trackProductEvent({ name: 'homepage_primary_cta', source: 'mobile_nav' })}
            >
              免费开始
            </Link>
          </div>
        </div>
      )}
    </header>
  )
}
