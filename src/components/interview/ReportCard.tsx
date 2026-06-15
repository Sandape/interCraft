/** ReportCard — interview report display component (T050).

Shows: overall score, dimension radar, per-question breakdown,
strengths, and improvements.
*/
import { ScoreDisplay } from './ScoreDisplay'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import { dimensionLabel } from '@/lib/dimensions'

interface DimensionScore {
  dimension: string
  score: number
  detail?: string
  suggestions?: string[]
}

interface QuestionScore {
  question_no: number
  dimension: string
  score: number
  feedback: string
}

interface ReportCardProps {
  overallScore: number
  perQuestionScore: QuestionScore[]
  dimensionScores: Record<string, number>
  strengths: DimensionScore[]
  improvements: DimensionScore[]
  summaryMd: string
  className?: string
}

function dimBadgeVariant(score: number) {
  if (score >= 7) return 'success' as const
  if (score >= 4) return 'warning' as const
  return 'danger' as const
}

export function ReportCard({
  overallScore,
  perQuestionScore,
  dimensionScores,
  strengths,
  improvements,
  summaryMd,
  className,
}: ReportCardProps) {
  return (
    <div className={cn('space-y-6', className)}>
      {/* Overall Score */}
      <Card>
        <CardHeader title="综合评分" />
        <div className="flex justify-center">
          <ScoreDisplay score={overallScore} size="lg" />
        </div>
      </Card>

      {/* Dimension Scores */}
      <Card>
        <CardHeader title="各维度得分" />
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(dimensionScores).map(([dim, score]) => (
            <div key={dim} className="flex items-center justify-between p-2 rounded bg-muted/50">
              <span className="text-sm font-medium">
                {dimensionLabel(dim)}
              </span>
              <Badge variant={dimBadgeVariant(score)}>
                {score.toFixed(1)}
              </Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* Per-Question Scores */}
      <Card>
        <CardHeader title="每题得分" />
        <div className="space-y-3">
          {perQuestionScore.map((q) => (
            <div key={q.question_no} className="flex items-center gap-3 p-3 rounded bg-muted/30">
              <ScoreDisplay score={q.score} size="sm" animated={false} />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">第 {q.question_no} 题</span>
                  <Badge variant="outline">{dimensionLabel(q.dimension)}</Badge>
                </div>
                <p className="text-sm text-muted-foreground mt-1">{q.feedback}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Strengths */}
      <Card>
        <CardHeader title="优势" />
        <div className="space-y-2">
          {strengths.map((s, i) => (
            <div key={i} className="flex items-start gap-3 p-3 rounded bg-green-50 border border-green-200">
              <ScoreDisplay score={s.score} size="sm" animated={false} />
              <div>
                <span className="font-medium">{dimensionLabel(s.dimension)}</span>
                <p className="text-sm text-muted-foreground">{s.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Improvements */}
      <Card>
        <CardHeader title="改进建议" />
        <div className="space-y-2">
          {improvements.map((imp, i) => (
            <div key={i} className="p-3 rounded bg-amber-50 border border-amber-200">
              <div className="flex items-center gap-2 mb-2">
                <ScoreDisplay score={imp.score} size="sm" animated={false} />
                <span className="font-medium">{dimensionLabel(imp.dimension)}</span>
              </div>
              <p className="text-sm text-muted-foreground mb-2">{imp.detail}</p>
              {imp.suggestions && imp.suggestions.length > 0 && (
                <ul className="list-disc list-inside text-sm space-y-1">
                  {imp.suggestions.map((sug, j) => (
                    <li key={j}>{sug}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Summary */}
      <Card>
        <CardHeader title="面试总结" />
        <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: summaryMd }} />
      </Card>
    </div>
  )
}

export default ReportCard
