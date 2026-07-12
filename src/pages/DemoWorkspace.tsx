import { useState } from 'react'
import { ArrowLeft, LockKeyhole, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BrandLockup } from '@/components/public/PublicHeader'
import { DemoWorkspaceNav, type DemoView } from '@/components/public/DemoWorkspaceShell'
import { DemoWorkspaceView } from '@/components/public/DemoWorkspaceViews'
import { publicDemoData } from '@/data/publicDemoData'
import { trackProductEvent } from '@/lib/product-events'
import '@/styles/public-product.css'

export default function DemoWorkspace() {
  const [view, setView] = useState<DemoView>('overview')

  return (
    <div className="demo-workspace-page min-h-dvh overflow-x-hidden bg-surface-subtle text-ink-1">
      <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-800" role="status">
        <span className="font-semibold">示例数据 · 只读模式</span>
        <span className="hidden sm:inline"> — 这是匿名产品演示，不会展示或修改真实账号数据。</span>
      </div>
      <header className="border-b border-surface-border bg-surface">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-4">
            <BrandLockup />
            <span className="hidden h-5 w-px bg-surface-border sm:block" />
            <div className="hidden text-xs text-ink-3 sm:block">
              {publicDemoData.candidate} · {publicDemoData.targetRole}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/" className="btn-ghost btn-lg hidden sm:inline-flex" aria-label="返回产品首页">
              <ArrowLeft className="h-4 w-4" /> 首页
            </Link>
            <Link
              to="/register"
              className="btn-primary btn-lg min-h-11"
              onClick={() => trackProductEvent({ name: 'demo_register_cta', source: 'demo_header' })}
            >
              创建自己的工作台
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto grid w-full min-w-0 max-w-[1440px] grid-cols-[minmax(0,1fr)] lg:grid-cols-[200px_minmax(0,1fr)]">
        <aside className="min-w-0 max-w-full border-b border-surface-border bg-surface p-3 lg:min-h-[calc(100dvh-105px)] lg:border-b-0 lg:border-r lg:p-4">
          <div className="mb-3 hidden px-2 text-2xs font-medium uppercase tracking-[0.14em] text-ink-muted lg:block">
            Sample workspace
          </div>
          <DemoWorkspaceNav active={view} onChange={setView} />
          <div className="mt-5 hidden border-t border-surface-border pt-4 lg:block">
            <button type="button" disabled className="btn-primary btn-md w-full" title="只读模式下不可生成">
              <Plus className="h-3.5 w-3.5" /> 生成岗位定制简历
            </button>
            <p className="mt-2 px-1 text-2xs leading-relaxed text-ink-3">
              <LockKeyhole className="mr-1 inline h-3 w-3" /> 登录或注册后创建自己的版本。
            </p>
          </div>
        </aside>

        <main className="min-w-0 p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-6xl">
            <div className="mb-4 flex items-center justify-between lg:hidden">
              <div className="text-xs text-ink-3">{publicDemoData.candidate}</div>
              <button type="button" disabled className="btn-secondary btn-md" title="只读模式下不可生成">
                生成岗位定制简历
              </button>
            </div>
            <DemoWorkspaceView view={view} />
          </div>
        </main>
      </div>
    </div>
  )
}
