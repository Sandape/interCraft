/** ScoreDisplay — 0-10 score with color coding + animated number (T051).

Colors: 0-3 red, 4-6 yellow/amber, 7-8 green, 9-10 teal
*/
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface ScoreDisplayProps {
  score: number
  maxScore?: number
  size?: 'sm' | 'md' | 'lg'
  animated?: boolean
  className?: string
}

function scoreColor(score: number): string {
  if (score <= 3) return 'text-red-500'
  if (score <= 6) return 'text-amber-500'
  if (score <= 8) return 'text-green-500'
  return 'text-teal-500'
}

function scoreBg(score: number): string {
  if (score <= 3) return 'bg-red-50 border-red-200'
  if (score <= 6) return 'bg-amber-50 border-amber-200'
  if (score <= 8) return 'bg-green-50 border-green-200'
  return 'bg-teal-50 border-teal-200'
}

const sizeClasses = {
  sm: 'text-lg w-10 h-10',
  md: 'text-2xl w-14 h-14',
  lg: 'text-4xl w-20 h-20',
}

export function ScoreDisplay({ score, maxScore = 10, size = 'md', animated = true, className }: ScoreDisplayProps) {
  const [displayScore, setDisplayScore] = useState(animated ? 0 : score)

  useEffect(() => {
    if (!animated) {
      setDisplayScore(score)
      return
    }
    const duration = 800
    const steps = 20
    const increment = score / steps
    let current = 0
    const interval = setInterval(() => {
      current += increment
      if (current >= score) {
        setDisplayScore(score)
        clearInterval(interval)
      } else {
        setDisplayScore(Math.round(current * 10) / 10)
      }
    }, duration / steps)
    return () => clearInterval(interval)
  }, [score, animated])

  return (
    <div className={cn('flex flex-col items-center gap-1', className)}>
      <div
        className={cn(
          'rounded-full border-2 flex items-center justify-center font-bold transition-colors',
          scoreColor(score),
          scoreBg(score),
          sizeClasses[size],
        )}
      >
        {displayScore}
      </div>
      <span className={cn('text-xs font-medium', scoreColor(score))}>
        / {maxScore}
      </span>
    </div>
  )
}

export default ScoreDisplay
