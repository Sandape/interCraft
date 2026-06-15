/** ErrorBanner — interview error display component (T055).

Handles: quota_exceeded, llm_timeout, retry_exhausted,
parse_error, internal_error, session_expired.
*/
import { AlertCircle, Clock, Zap, AlertTriangle, RefreshCw, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { Link } from 'react-router-dom'

interface ErrorBannerProps {
  code: string
  message: string
  retryable?: boolean
  retryCount?: number
  onRetry?: () => void
  className?: string
}

const errorConfig: Record<string, { icon: typeof AlertCircle; bg: string; border: string }> = {
  quota_exceeded: { icon: Zap, bg: 'bg-red-50', border: 'border-red-300' },
  llm_timeout: { icon: Clock, bg: 'bg-amber-50', border: 'border-amber-300' },
  llm_rate_limited: { icon: Clock, bg: 'bg-amber-50', border: 'border-amber-300' },
  retry_exhausted: { icon: AlertTriangle, bg: 'bg-red-50', border: 'border-red-300' },
  parse_error: { icon: AlertTriangle, bg: 'bg-amber-50', border: 'border-amber-200' },
  internal_error: { icon: AlertCircle, bg: 'bg-red-50', border: 'border-red-300' },
  session_expired: { icon: Clock, bg: 'bg-gray-50', border: 'border-gray-300' },
}

export function ErrorBanner({
  code,
  message,
  retryable = false,
  retryCount = 0,
  onRetry,
  className,
}: ErrorBannerProps) {
  const config = errorConfig[code] || errorConfig.internal_error
  const Icon = config.icon

  const renderAction = () => {
    switch (code) {
      case 'quota_exceeded':
        return (
          <Link to="/settings">
            <Button variant="primary" size="sm">
              升级订阅 <ExternalLink className="ml-1 h-3 w-3" />
            </Button>
          </Link>
        )
      case 'llm_timeout':
        return retryable && retryCount < 3 ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              正在重试 ({retryCount}/3)…
            </span>
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        ) : null
      case 'retry_exhausted':
        return (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">AI 暂时无法响应</span>
            {onRetry && (
              <Button variant="ghost" size="sm" onClick={onRetry}>
                <RefreshCw className="mr-1 h-3 w-3" /> 重试
              </Button>
            )}
          </div>
        )
      case 'parse_error':
        return <span className="text-sm text-muted-foreground">已自动降级处理</span>
      case 'session_expired':
        return (
          <span className="text-sm text-muted-foreground">
            该面试已过期，可查看部分报告
          </span>
        )
      default:
        return onRetry ? (
          <Button variant="ghost" size="sm" onClick={onRetry}>
            <RefreshCw className="mr-1 h-3 w-3" /> 重试
          </Button>
        ) : null
    }
  }

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg border',
        config.bg,
        config.border,
        className,
      )}
    >
      <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{getErrorTitle(code)}</p>
        <p className="text-sm text-muted-foreground mt-0.5">{message}</p>
        <div className="mt-2">{renderAction()}</div>
      </div>
    </div>
  )
}

function getErrorTitle(code: string): string {
  switch (code) {
    case 'quota_exceeded': return '本月 AI 额度已用尽'
    case 'llm_timeout': return 'AI 响应超时'
    case 'llm_rate_limited': return 'AI 请求频率限制'
    case 'retry_exhausted': return 'AI 暂时无法响应'
    case 'parse_error': return '评分出现异常'
    case 'internal_error': return '发生未知错误'
    case 'session_expired': return '面试已过期'
    default: return '发生错误'
  }
}

export default ErrorBanner
