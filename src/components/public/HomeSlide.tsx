import { useEffect, useRef, useState } from 'react'
import { useInViewOnce } from '@/hooks/useInViewOnce'
import { cn } from '@/lib/utils'

export type HomeChapter = {
  id: string
  index: string
  label: string
}

export function useHomeDeckNavigation() {
  const deckRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const deck = deckRef.current
    if (!deck) return

    let locked = false
    let unlockTimer: number | undefined

    const onWheel = (event: WheelEvent) => {
      const isDesktopDeck = window.matchMedia('(min-width: 1024px) and (min-height: 700px)').matches
      if (
        !isDesktopDeck ||
        locked ||
        event.ctrlKey ||
        Math.abs(event.deltaY) <= Math.abs(event.deltaX) ||
        Math.abs(event.deltaY) < 6
      ) return

      const slideHeight = deck.clientHeight
      const slideCount = deck.querySelectorAll('[data-home-slide]').length
      if (!slideHeight || !slideCount) return

      const currentIndex = Math.round(deck.scrollTop / slideHeight)
      const direction = event.deltaY > 0 ? 1 : -1
      const nextIndex = Math.min(slideCount - 1, Math.max(0, currentIndex + direction))
      if (nextIndex === currentIndex) return

      event.preventDefault()
      locked = true
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      deck.scrollTo({
        top: nextIndex * slideHeight,
        behavior: reduceMotion ? 'auto' : 'smooth',
      })
      unlockTimer = window.setTimeout(() => {
        locked = false
      }, 700)
    }

    deck.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      deck.removeEventListener('wheel', onWheel)
      if (unlockTimer !== undefined) window.clearTimeout(unlockTimer)
    }
  }, [])

  return deckRef
}

export function HomeSlide({
  id,
  labelledBy,
  className,
  children,
}: {
  id: string
  labelledBy: string
  className?: string
  children: React.ReactNode
}) {
  const { ref, inView } = useInViewOnce<HTMLElement>('-8% 0px -18%')

  return (
    <section
      ref={ref}
      id={id}
      aria-labelledby={labelledBy}
      className={cn('public-slide scroll-mt-16', inView && 'is-visible', className)}
      data-home-slide={id}
    >
      <div className="public-slide-content">{children}</div>
    </section>
  )
}

export function HomeChapterNav({ chapters }: { chapters: readonly HomeChapter[] }) {
  const [activeChapter, setActiveChapter] = useState(chapters[0]?.id ?? '')

  useEffect(() => {
    if (!('IntersectionObserver' in window)) return

    const observer = new IntersectionObserver(
      (entries) => {
        const current = entries.find((entry) => entry.isIntersecting)
        if (current?.target.id) setActiveChapter(current.target.id)
      },
      { rootMargin: '-44% 0px -44%', threshold: 0 },
    )

    chapters.forEach(({ id }) => {
      const slide = document.getElementById(id)
      if (slide) observer.observe(slide)
    })

    return () => observer.disconnect()
  }, [chapters])

  return (
    <nav
      className={cn('public-chapter-nav', activeChapter === 'scenarios' && 'is-inverse')}
      aria-label="首页章节"
    >
      <span className="public-chapter-rail" aria-hidden="true" />
      {chapters.map(({ id, index, label }) => {
        const isActive = activeChapter === id
        return (
          <a
            key={id}
            href={`#${id}`}
            className={cn('public-chapter-link', isActive && 'is-active')}
            aria-label={`${index} ${label}`}
            aria-current={isActive ? 'step' : undefined}
          >
            <span className="public-chapter-dot" aria-hidden="true" />
            <span className="public-chapter-index">{index}</span>
            <span className="public-chapter-label">{label}</span>
          </a>
        )
      })}
    </nav>
  )
}
