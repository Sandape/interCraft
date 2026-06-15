/** ProgressBar — interview progress indicator (T037).

Shows: "第 X/5 轮" with animated node status dots.
Flow: intake → q1 → s1 → q2 → s2 → q3 → s3 → q4 → s4 → q5 → s5 → report
*/
import { cn } from '@/lib/utils'

interface ProgressBarProps {
  currentQuestion: number
  totalQuestions: number
  currentNode: string | null
  className?: string
}

const NODE_LABELS: Record<string, string> = {
  intake: 'Info',
  question_gen: 'Q',
  score: 'S',
  report: 'R',
}

export function ProgressBar({ currentQuestion, totalQuestions, currentNode, className }: ProgressBarProps) {
  const stages: Array<{ label: string; node: string; active: boolean; completed: boolean }> = []

  // Intake stage
  stages.push({
    label: 'Start',
    node: 'intake',
    active: currentNode === 'intake',
    completed: currentQuestion > 0 || currentNode === 'question_gen' || currentNode === 'score' || currentNode === 'report',
  })

  for (let i = 1; i <= totalQuestions; i++) {
    stages.push({
      label: `Q${i}`,
      node: `q${i}`,
      active: currentNode === 'question_gen' && currentQuestion === i,
      completed: currentQuestion > i,
    })
    stages.push({
      label: `S${i}`,
      node: `s${i}`,
      active: currentNode === 'score' && currentQuestion === i,
      completed: currentQuestion > i || (currentQuestion === i && currentNode === 'report'),
    })
  }

  stages.push({
    label: 'Report',
    node: 'report',
    active: currentNode === 'report',
    completed: currentNode === 'completed',
  })

  return (
    <div className={cn('flex items-center gap-1.5', className)}>
      <span className="text-sm font-medium text-muted-foreground mr-2">
        第 {Math.min(currentQuestion, totalQuestions)}/{totalQuestions} 轮
      </span>
      <div className="flex items-center gap-1">
        {stages.map((stage, i) => (
          <div key={i} className="flex items-center gap-1">
            <div
              className={cn(
                'w-2.5 h-2.5 rounded-full transition-all duration-300',
                stage.completed && 'bg-green-500',
                stage.active && 'bg-primary animate-pulse scale-125',
                !stage.completed && !stage.active && 'bg-muted-foreground/30',
              )}
              title={stage.label}
            />
            {i < stages.length - 1 && (
              <div
                className={cn(
                  'w-2 h-px',
                  stage.completed ? 'bg-green-500' : 'bg-muted-foreground/20',
                )}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default ProgressBar
