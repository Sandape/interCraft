import { useState, useEffect, useRef } from 'react'
import { Download, FileText, CheckCircle, Clock, AlertCircle, RefreshCw } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Progress } from '@/components/ui/Progress'
import { accountApi, type ExportStatusResponse } from '@/api/account'

type ExportState = 'idle' | 'pending' | 'processing' | 'completed' | 'failed'

export default function ExportTab() {
  const [exportState, setExportState] = useState<ExportState>('idle')
  const [taskId, setTaskId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  const handleStartExport = async () => {
    setError('')
    setExportState('pending')
    try {
      const res = await accountApi.createExport()
      setTaskId(res.task_id)
      setExportState('processing')
      // Poll
      pollingRef.current = setInterval(async () => {
        try {
          const status = await accountApi.getExportStatus(res.task_id)
          setProgress(status.progress_pct)
          if (status.status === 'completed') {
            setExportState('completed')
            if (pollingRef.current) clearInterval(pollingRef.current)
          } else if (status.status === 'failed') {
            setExportState('failed')
            setError('导出失败')
            if (pollingRef.current) clearInterval(pollingRef.current)
          }
        } catch {
          // Retry on next poll
        }
      }, 3000)
    } catch {
      setExportState('failed')
      setError('创建导出任务失败')
    }
  }

  const handleDownload = () => {
    if (taskId) {
      window.open(accountApi.downloadExportUrl(taskId), '_blank')
    }
  }

  const handleReset = () => {
    if (pollingRef.current) clearInterval(pollingRef.current)
    setExportState('idle')
    setTaskId(null)
    setProgress(0)
    setError('')
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <CardHeader title="数据导出" description="下载你的所有数据" />
        <p className="text-sm text-ink-2 leading-relaxed mb-3">
          导出包含所有简历分支、模拟面试记录、能力画像、错题本等数据。数据格式为 JSON，可在 72 小时内重新下载。
        </p>

        {exportState === 'idle' && (
          <Button variant="secondary" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={handleStartExport}>
            申请数据导出
          </Button>
        )}

        {exportState === 'pending' && (
          <div className="flex items-center gap-2 text-sm text-ink-3">
            <Clock className="h-4 w-4 animate-pulse" />
            正在创建导出任务...
          </div>
        )}

        {exportState === 'processing' && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-ink-3">
              <RefreshCw className="h-4 w-4 animate-spin" />
              正在打包数据 ({progress}%)
            </div>
            <Progress value={progress} size="sm" variant="brand" />
          </div>
        )}

        {exportState === 'completed' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
              <CheckCircle className="h-4 w-4" />
              导出已完成，点击下载按钮获取 ZIP 文件
            </div>
            <div className="flex gap-2">
              <Button variant="primary" leftIcon={<Download className="h-3.5 w-3.5" />} onClick={handleDownload}>
                下载导出文件
              </Button>
              <Button variant="ghost" size="sm" onClick={handleReset}>
                重新导出
              </Button>
            </div>
          </div>
        )}

        {exportState === 'failed' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-red-500">
              <AlertCircle className="h-4 w-4" />
              {error || '导出失败，请稍后重试'}
            </div>
            <Button variant="secondary" size="sm" onClick={handleReset}>
              重试
            </Button>
          </div>
        )}
      </Card>

      <Card className="p-5">
        <CardHeader title="数据存储" description="了解我们如何保护你的数据" />
        <div className="space-y-2">
          <InfoRow label="数据存储位置" value="阿里云 · 北京" />
          <InfoRow label="数据加密" value="AES-256（传输 + 存储）" />
          <InfoRow label="备份频率" value="每日增量 + 每周全量" />
          <InfoRow label="导出有效期" value="72 小时" />
        </div>
        <div className="mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border text-xs text-ink-3">
          我们承诺：你的数据仅用于 AI 优化你的求职准备，不会用于任何模型训练或第三方共享。
        </div>
      </Card>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-ink-3">{label}</span>
      <span className="text-sm text-ink-1 font-medium">{value}</span>
    </div>
  )
}
