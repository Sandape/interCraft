import { ArrowRight, Check, MoveRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CareerLoop } from '@/components/public/CareerLoop'
import { HomeChapterNav, HomeSlide, useHomeDeckNavigation } from '@/components/public/HomeSlide'
import { PublicHeader, BrandLockup } from '@/components/public/PublicHeader'
import { RetentionEvidence, TargetedResumeEvidence } from '@/components/public/ProductEvidence'
import { WorkspacePreview } from '@/components/public/WorkspacePreview'
import { trackProductEvent } from '@/lib/product-events'
import '@/styles/public-product.css'

const audiences = [
  { title: '校招', detail: '把课程、项目和实习整理成可复用职业素材。' },
  { title: '社招', detail: '针对每个岗位重组证据，保留完整求职脉络。' },
  { title: '实习', detail: '没有完整 JD，也可以从岗位方向开始准备。' },
  { title: '转行', detail: '识别可迁移能力，同时看清需要补足的差距。' },
] as const

const homeChapters = [
  { id: 'hero', index: '01', label: '开始' },
  { id: 'workflow', index: '02', label: '闭环' },
  { id: 'product-proof', index: '03', label: '定制' },
  { id: 'retention', index: '04', label: '沉淀' },
  { id: 'scenarios', index: '05', label: '行动' },
] as const

export default function PublicHome() {
  const deckRef = useHomeDeckNavigation()

  return (
    <div ref={deckRef} className="public-product min-h-screen overflow-x-hidden bg-surface text-ink-1">
      <a href="#main-content" className="skip-link">
        跳到主要内容
      </a>
      <PublicHeader />
      <HomeChapterNav chapters={homeChapters} />

      <main id="main-content">
        <HomeSlide
          id="hero"
          labelledBy="hero-title"
          className="public-hero relative border-b border-surface-border bg-surface-subtle"
        >
          <div className="mx-auto grid w-full max-w-7xl items-center gap-10 px-5 sm:px-8 lg:grid-cols-[0.82fr_1.18fr] lg:gap-12 lg:px-10">
            <div className="public-hero-copy max-w-2xl">
              <p className="slide-reveal text-xs font-semibold uppercase tracking-[0.18em] text-brand-600">
                AI job-search workspace
              </p>
              <h1 id="hero-title" className="slide-reveal mt-5 text-balance text-4xl font-semibold leading-[1.12] tracking-[-0.035em] text-ink-1 sm:text-[44px] sm:leading-[1.08] lg:text-[40px] xl:text-[44px]">
                把一份根简历，变成每个目标岗位的完整准备
              </h1>
              <p className="slide-reveal mt-5 max-w-xl text-base leading-7 text-ink-2 sm:text-lg sm:leading-8">
                从目标岗位出发，生成岗位定制简历，继续模拟面试、复盘错题，并把每次准备沉淀成长期能力画像。
              </p>
              <div className="slide-reveal mt-7 flex flex-col gap-2.5 sm:flex-row lg:flex-col xl:flex-row">
                <Link
                  to="/register"
                  className="btn-primary btn-lg min-h-11 px-5"
                  onClick={() => trackProductEvent({ name: 'homepage_primary_cta', source: 'hero' })}
                >
                  免费开始 · 创建岗位定制简历 <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/demo"
                  className="btn-secondary btn-lg min-h-11 px-5"
                  onClick={() => trackProductEvent({ name: 'homepage_demo_cta', source: 'hero' })}
                >
                  查看只读示例工作台
                </Link>
              </div>
              <div className="slide-reveal mt-5 flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-3">
                {['可以跳过引导', '进度自动保存', '先看示例再注册'].map((item) => (
                  <span key={item} className="inline-flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-emerald-600" /> {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="slide-visual hero-workspace relative lg:-mr-8">
              <div className="mb-3 flex items-center justify-between px-1 text-2xs text-ink-3">
                <span>真实产品界面结构 · 匿名示例数据</span>
                <span className="hidden sm:inline">根简历 + 岗位 → 派生简历</span>
              </div>
              <WorkspacePreview />
            </div>
          </div>
          <a className="public-scroll-cue" href="#workflow">
            <span>继续探索</span>
            <span className="public-scroll-cue-line" aria-hidden="true" />
          </a>
        </HomeSlide>

        <HomeSlide id="workflow" labelledBy="workflow-title" className="border-b border-surface-border bg-surface">
          <div className="mx-auto w-full max-w-7xl px-5 sm:px-8 lg:px-10">
            <div className="slide-reveal">
              <SectionIntro
                titleId="workflow-title"
                index="02"
                eyebrow="One continuous workflow"
                title="求职不是六个孤立工具，而是一条会积累的路径"
                body="岗位决定简历重点，简历成为面试上下文；面试暴露的问题进入错题本，再回到能力画像和下一份岗位准备。"
              />
            </div>
            <div className="slide-visual mt-12 sm:mt-16">
              <CareerLoop />
            </div>
          </div>
        </HomeSlide>

        <HomeSlide id="product-proof" labelledBy="product-proof-title" className="bg-surface-subtle">
          <div className="mx-auto w-full max-w-7xl px-5 sm:px-8 lg:px-10">
            <div className="grid gap-10 lg:grid-cols-[0.65fr_1.35fr] lg:items-start">
              <div className="slide-reveal">
                <SectionIntro
                  titleId="product-proof-title"
                  index="03"
                  eyebrow="The activation moment"
                  title="先得到一份面向具体岗位的简历，再决定下一步"
                  body="不是泛泛地“优化简历”。InterCraft 把根简历与目标岗位放在同一个上下文里，给出岗位定制版本、匹配分析、能力差距和可执行建议。"
                />
                <div className="mt-7 border-l-2 border-brand-900 pl-4">
                  <div className="text-xs font-semibold text-ink-1">当前 Activation</div>
                  <p className="mt-1 text-xs leading-relaxed text-ink-3">
                    创建第一份岗位定制简历，并看到匹配、差距与优化建议。
                  </p>
                </div>
              </div>
              <div className="slide-visual"><TargetedResumeEvidence /></div>
            </div>
          </div>
        </HomeSlide>

        <HomeSlide id="retention" labelledBy="retention-title" className="border-y border-surface-border bg-surface">
          <div className="mx-auto w-full max-w-7xl px-5 sm:px-8 lg:px-10">
            <div className="mb-10 grid gap-5 md:grid-cols-[0.85fr_1.15fr] md:items-end">
              <h2 id="retention-title" className="slide-reveal text-balance text-3xl font-semibold tracking-[-0.025em] text-ink-1 sm:text-4xl">
                面试结束，不让经验散掉
              </h2>
              <p className="slide-reveal max-w-2xl text-sm leading-7 text-ink-2 md:justify-self-end">
                报告指出关键短板，错题本保留需要反复练习的问题，能力画像把零散反馈整理成可追踪的长期信号。
              </p>
            </div>
            <div className="slide-visual"><RetentionEvidence /></div>
          </div>
        </HomeSlide>

        <HomeSlide id="scenarios" labelledBy="scenarios-title" className="public-final-slide bg-brand-900 text-white">
          <div className="mx-auto w-full max-w-7xl px-5 sm:px-8 lg:px-10">
            <div className="grid gap-8 lg:grid-cols-[0.78fr_1.22fr] lg:items-start lg:gap-14">
              <div className="slide-reveal">
                <SectionIntro
                  titleId="scenarios-title"
                  index="05"
                  eyebrow="Different stages, same workspace"
                  title="从第一次求职，到下一次职业转向"
                  body="示例候选人只是产品证明，不是目标用户边界。InterCraft 面向不同阶段和行业的泛求职用户。"
                  inverse
                />
              </div>
              <div className="audience-grid grid border-y border-white/15 sm:grid-cols-2">
                {audiences.map((audience, index) => (
                  <article
                    key={audience.title}
                    className="audience-card border-b border-white/15 py-5 sm:border-r sm:px-6 sm:odd:border-l-0 sm:even:border-r-0"
                    style={{ '--audience-index': index } as React.CSSProperties}
                  >
                    <div className="font-mono text-2xs text-white/35">0{index + 1}</div>
                    <h3 className="mt-2 text-lg font-semibold text-white">{audience.title}</h3>
                    <p className="mt-1.5 text-xs leading-6 text-white/60">{audience.detail}</p>
                  </article>
                ))}
              </div>
            </div>

            <div className="final-cta mt-10 grid gap-6 border-t border-white/15 pt-8 md:grid-cols-[1fr_auto] md:items-end">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-white/45">Your next role starts here</p>
                <h2 className="mt-3 max-w-3xl text-balance text-2xl font-semibold tracking-[-0.025em] sm:text-3xl">
                  先选一个目标岗位，创建你的第一份岗位定制简历
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-white/65">
                  没有具体 JD 也可以开始；选择岗位方向，之后再补充真实岗位信息。
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Link
                  to="/register"
                  className="btn-lg inline-flex min-h-11 items-center justify-center gap-2 rounded bg-white px-5 font-medium text-brand-900 transition-colors duration-200 hover:bg-surface-muted"
                  onClick={() => trackProductEvent({ name: 'homepage_primary_cta', source: 'final' })}
                >
                  免费开始 <MoveRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/demo"
                  className="btn-lg inline-flex min-h-11 items-center justify-center rounded border border-white/25 px-5 font-medium text-white transition-colors duration-200 hover:bg-white/10"
                  onClick={() => trackProductEvent({ name: 'homepage_demo_cta', source: 'final' })}
                >
                  查看示例
                </Link>
              </div>
            </div>

            <footer className="public-final-footer mt-8 flex flex-col gap-4 border-t border-white/10 pt-5 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between">
              <BrandLockup inverse />
              <p>根简历、岗位定制简历、模拟面试、错题本与能力画像。</p>
              <div className="flex gap-5">
                <Link to="/login" className="hover:text-white">登录</Link>
                <Link to="/register" className="hover:text-white">注册</Link>
                <Link to="/demo" className="hover:text-white">示例工作台</Link>
              </div>
            </footer>
          </div>
        </HomeSlide>
      </main>
    </div>
  )
}

function SectionIntro({
  titleId,
  index,
  eyebrow,
  title,
  body,
  inverse = false,
}: {
  titleId: string
  index: string
  eyebrow: string
  title: string
  body: string
  inverse?: boolean
}) {
  return (
    <div className="max-w-3xl">
      <div className={`flex items-center gap-3 text-2xs font-medium uppercase tracking-[0.16em] ${inverse ? 'text-white/50' : 'text-ink-3'}`}>
        <span className={`font-mono ${inverse ? 'text-white/35' : 'text-ink-muted'}`}>{index}</span>
        <span className={`h-px w-8 ${inverse ? 'bg-white/20' : 'bg-surface-border'}`} />
        {eyebrow}
      </div>
      <h2 id={titleId} className={`mt-5 text-balance text-3xl font-semibold tracking-[-0.025em] sm:text-4xl ${inverse ? 'text-white' : 'text-ink-1'}`}>
        {title}
      </h2>
      <p className={`mt-4 max-w-2xl text-sm leading-7 ${inverse ? 'text-white/65' : 'text-ink-2'}`}>{body}</p>
    </div>
  )
}
