import { Link } from 'react-router-dom'
import { Sparkles, Clock, FileText, ArrowRight, Layers } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { timeAgo, cn } from '@/lib/utils'
import type { ResumeBranch } from '@/modules/resume/api/types'

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  optimizing: '优化中',
  ready: '就绪',
  submitted: '已投递',
  archived: '归档',
}

const STATUS_VARIANT: Record<string, 'default' | 'success' | 'warning' | 'brand'> = {
  draft: 'default',
  optimizing: 'warning',
  ready: 'success',
  submitted: 'brand',
  archived: 'default',
}

interface PrimaryResumeCardProps {
  branch: ResumeBranch
  blockCount: number
  previewText?: string
}

export default function PrimaryResumeCard({ branch, blockCount, previewText }: PrimaryResumeCardProps) {
  return (
    <Link to={`/resume/${branch.id}`} className="group block">
      <Card
        hover
        padding="lg"
        className="border-brand-200 dark:border-brand-500/20 bg-gradient-to-r from-brand-50/30 to-white dark:from-brand-500/5 dark:to-dark-surface"
      >
        <div className="flex items-start gap-4">
          {/* Icon */}
          <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center flex-shrink-0 shadow-sm">
            <Sparkles className="h-4.5 w-4.5 text-white" />
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h2 className="text-base font-semibold text-ink-1 group-hover:text-brand-600 transition-colors">
                {branch.name}
              </h2>
              <Badge variant="brand" className="text-2xs">
                主简历
              </Badge>
              <Badge variant={STATUS_VARIANT[branch.status]}>
                {STATUS_LABEL[branch.status]}
              </Badge>
            </div>

            <div className="flex items-center gap-2 text-xs text-ink-3 mb-2">
              {branch.company && <span>{branch.company}</span>}
              {branch.position && (
                <>
                  {branch.company && <span>·</span>}
                  <span>{branch.position}</span>
                </>
              )}
              <span>·</span>
              <span>数据源 — 派生分支的基础</span>
            </div>

            {/* Preview excerpt */}
            {previewText && (
              <p className="text-xs text-ink-3 leading-relaxed line-clamp-2 mb-2.5">
                {previewText}
              </p>
            )}

            {/* Meta footer */}
            <div className="flex items-center gap-3 text-2xs text-ink-3">
              <span className="flex items-center gap-1">
                <Layers className="h-2.5 w-2.5" />
                {blockCount} 个模块
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-2.5 w-2.5" />
                {branch.last_edited_at ? `更新于 ${timeAgo(branch.last_edited_at)}` : '刚刚创建'}
              </span>
              {branch.match_score != null && (
                <span
                  className={cn(
                    'font-medium',
                    branch.match_score >= 90
                      ? 'text-emerald-600'
                      : branch.match_score >= 80
                        ? 'text-brand-600'
                        : 'text-amber-600',
                  )}
                >
                  匹配度 {branch.match_score}%
                </span>
              )}
            </div>
          </div>

          {/* Arrow indicator */}
          <ArrowRight className="h-4 w-4 text-ink-muted group-hover:text-brand-500 transition-colors flex-shrink-0 mt-3" />
        </div>
      </Card>
    </Link>
  )
}
