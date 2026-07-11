import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { QrCode, Unlink, RefreshCw, Loader2, CheckCircle2, Clock } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AITaskActions } from '@/components/ai'
import { useAITask } from '@/hooks/queries/useAITasks'
import { AgentRepository, resolveQrcodeSrc } from '@/repositories/AgentRepository'
import type { BindingStatus, AgentPreferences } from '@/repositories/AgentRepository'
import type { AgentConsumerStatus, AgentTask } from '@/repositories/AgentRepository'

type ScanStatus = 'idle' | 'loading' | 'waiting' | 'scanned' | 'confirmed' | 'expired' | 'error'

function toTimeInput(value?: string | null): string {
  if (!value) return ''
  return value.slice(0, 5)
}

function pickActiveTask(tasks: AgentTask[]): AgentTask | undefined {
  return tasks.find((task) => {
    if (task.terminal) return false
    if (task.available_actions?.length) {
      return task.available_actions.some((a) => a === 'cancel' || a === 'resume')
    }
    return !['succeeded', 'failed', 'dead_letter', 'cancelled', 'canceled', 'expired'].includes(task.status)
  })
}

function pickRecoverableTask(tasks: AgentTask[]): AgentTask | undefined {
  return tasks.find((task) => {
    if (task.available_actions?.includes('resume') || task.available_actions?.includes('system_failure_retry')) {
      return true
    }
    return ['failed', 'dead_letter', 'cancelled', 'canceled'].includes(task.status)
  })
}

export default function AgentSettings() {
  const [binding, setBinding] = useState<BindingStatus | null>(null)
  const [bindingLoading, setBindingLoading] = useState(true)
  const [bindingLoadError, setBindingLoadError] = useState<string | null>(null)
  const [scanStatus, setScanStatus] = useState<ScanStatus>('idle')
  const [qrcodeSrc, setQrcodeSrc] = useState<string | null>(null)
  const [qrcodeToken, setQrcodeToken] = useState<string | null>(null)
  const [expiresIn, setExpiresIn] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [preferences, setPreferences] = useState<AgentPreferences | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [quietStart, setQuietStart] = useState('')
  const [quietEnd, setQuietEnd] = useState('')
  const [notificationMode, setNotificationMode] = useState<'realtime' | 'hourly_digest'>('realtime')
  const [saving, setSaving] = useState(false)
  const [consumer, setConsumer] = useState<AgentConsumerStatus | null>(null)
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [taskAction, setTaskAction] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load binding status on mount
  useEffect(() => {
    loadBindingStatus()
    loadPreferences()
    loadRuntimeStatus()
  }, [])

  // Countdown timer
  useEffect(() => {
    if (scanStatus === 'waiting' && expiresIn > 0) {
      const timer = setInterval(() => {
        setExpiresIn((prev) => {
          if (prev <= 1) {
            setScanStatus('expired')
            return 0
          }
          return prev - 1
        })
      }, 1000)
      return () => clearInterval(timer)
    }
  }, [scanStatus, expiresIn])

  const loadBindingStatus = async () => {
    setBindingLoading(true)
    setBindingLoadError(null)
    try {
      const data = await AgentRepository.fetchBindingStatus()
      setBinding(data)
    } catch {
      setBindingLoadError('暂时无法读取微信绑定状态，请重试。')
    } finally {
      setBindingLoading(false)
    }
  }

  const loadPreferences = async () => {
    try {
      const data = await AgentRepository.fetchPreferences()
      setPreferences(data)
      setDisplayName(data.display_name)
      setQuietStart(toTimeInput(data.quiet_hours_start))
      setQuietEnd(toTimeInput(data.quiet_hours_end))
      setNotificationMode(data.notification_mode || 'realtime')
    } catch { /* ignore */ }
  }

  const loadRuntimeStatus = async () => {
    try {
      const [consumerStatus, taskList] = await Promise.all([
        AgentRepository.fetchConsumerStatus(),
        AgentRepository.fetchTasks(),
      ])
      setConsumer(consumerStatus)
      setTasks(taskList.items)
    } catch {
      setConsumer(null)
    }
  }

  const handleTaskAction = async (task: AgentTask, action: 'cancel' | 'resume') => {
    setTaskAction(task.id)
    setError(null)
    try {
      if (action === 'cancel') await AgentRepository.cancelTask(task.id)
      else await AgentRepository.resumeTask(task.id)
      await loadRuntimeStatus()
    } catch (e: any) {
      setError(e?.message || '任务操作失败，请刷新后重试')
    } finally {
      setTaskAction(null)
    }
  }

  const currentTask = pickActiveTask(tasks)
  const recoverableTask = pickRecoverableTask(tasks)
  const canonicalTaskId = currentTask?.task_id || currentTask?.id || recoverableTask?.task_id || recoverableTask?.id || null
  const { data: canonicalTask, refetch: refetchCanonical } = useAITask(canonicalTaskId, {
    enabled: Boolean(canonicalTaskId),
  })

  const handleGetQrcode = async () => {
    setScanStatus('loading')
    setError(null)
    try {
      const data = await AgentRepository.fetchQrcode()
      setQrcodeSrc(resolveQrcodeSrc(data))
      setQrcodeToken(data.qrcode_token)
      setExpiresIn(data.expires_in_sec)
      setScanStatus('waiting')
      startPolling(data.qrcode_token)
    } catch (e: any) {
      setError(e?.message || '获取二维码失败')
      setScanStatus('error')
    }
  }

  const startPolling = useCallback((token: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const data = await AgentRepository.pollQrcodeStatus(token)
        if (data.status === 'confirmed') {
          clearInterval(pollRef.current!)
          setScanStatus('confirmed')
          await loadBindingStatus()
        } else if (data.status === 'scanned') {
          setScanStatus('scanned')
        } else if (data.status === 'expired') {
          clearInterval(pollRef.current!)
          setScanStatus('expired')
        } else if (data.status === 'wait') {
          setScanStatus('waiting')
        }
      } catch {
        // Poll error, continue
      }
    }, 2000)
  }, [])

  const handleCancelQrcode = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    setScanStatus('idle')
    setQrcodeSrc(null)
    setQrcodeToken(null)
  }

  const handleUnbind = async () => {
    if (!confirm('解除后 Agent 将无法通过微信联系你。确定要解除吗？')) return
    try {
      await AgentRepository.unbindWechat()
      setBinding(null)
    } catch (e: any) {
      setError(e?.message || '解绑失败')
    }
  }

  const handleSavePreferences = async () => {
    setSaving(true)
    setError(null)
    try {
      const payload: Partial<AgentPreferences> = {
        display_name: displayName,
        notification_mode: notificationMode,
        quiet_hours_start: quietStart || null,
        quiet_hours_end: quietEnd || null,
      }
      if ((quietStart && !quietEnd) || (!quietStart && quietEnd)) {
        setError('免打扰时段需同时填写开始与结束时间，或全部留空')
        return
      }
      const updated = await AgentRepository.updatePreferences(payload)
      setPreferences(updated)
      setDisplayName(updated.display_name)
      setQuietStart(toTimeInput(updated.quiet_hours_start))
      setQuietEnd(toTimeInput(updated.quiet_hours_end))
      setNotificationMode(updated.notification_mode || 'realtime')
    } catch (e: any) {
      setError(e?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Agent 助手</h1>

      {/* QR Binding Card */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">微信绑定</h2>

        {bindingLoading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-gray-600" role="status">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            正在读取微信绑定状态…
          </div>
        ) : bindingLoadError ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4" role="alert">
            <p className="text-sm text-amber-800">{bindingLoadError}</p>
            <Button variant="ghost" size="sm" className="mt-3" onClick={loadBindingStatus}>
              <RefreshCw className="mr-1 h-4 w-4" aria-hidden="true" />
              重试
            </Button>
          </div>
        ) : binding?.bound ? (
          /* Bound State */
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg border border-green-200">
              <CheckCircle2 className="w-6 h-6 text-green-600" />
              <div>
                <p className="font-medium text-green-800">已绑定微信</p>
                <p className="text-sm text-green-600">
                  状态：{binding.agent_status === 'active' ? '在线' : binding.agent_status === 'degraded' ? '连接异常' : '休眠'}
                </p>
                {binding.bound_at && (
                  <p className="text-xs text-green-500 mt-1">
                    绑定时间：{new Date(binding.bound_at).toLocaleString('zh-CN')}
                  </p>
                )}
              </div>
            </div>
            <Button variant="ghost" onClick={handleUnbind} className="text-red-600 border-red-300">
              <Unlink className="w-4 h-4 mr-2" />
              解除绑定
            </Button>
          </div>
        ) : (
          /* Unbound State */
          <div className="space-y-4">
            <p className="text-gray-600">绑定微信后，Agent 可以通过微信与你联系，包括发送面试提醒和备战报告。</p>
            <Button
              onClick={handleGetQrcode}
              disabled={scanStatus === 'loading' || scanStatus === 'waiting'}
            >
              {scanStatus === 'loading' ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <QrCode className="w-4 h-4 mr-2" />
              )}
              获取绑定二维码
            </Button>

            {/* QR Code Display */}
            {(scanStatus === 'waiting' || scanStatus === 'scanned') && qrcodeSrc && (
              <div className="space-y-3 p-4 bg-gray-50 rounded-lg">
                <img
                  src={qrcodeSrc}
                  alt="WeChat QR Code"
                  className="w-48 h-48 mx-auto border rounded"
                />
                <div className="text-center space-y-1">
                  {scanStatus === 'waiting' && (
                    <p className="text-sm text-gray-500 flex items-center justify-center gap-1">
                      <Clock className="w-4 h-4" />
                      请使用微信扫码绑定（{expiresIn}秒后过期）
                    </p>
                  )}
                  {scanStatus === 'scanned' && (
                    <p className="text-sm text-blue-600 font-medium">
                      已扫码，请在微信中确认绑定
                    </p>
                  )}
                </div>
                <div className="text-center">
                  <Button variant="ghost" size="sm" onClick={handleCancelQrcode}>
                    取消
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      handleCancelQrcode()
                      handleGetQrcode()
                    }}
                  >
                    <RefreshCw className="w-3 h-3 mr-1" />
                    刷新
                  </Button>
                </div>
              </div>
            )}

            {/* QR Expired */}
            {scanStatus === 'expired' && (
              <div className="p-4 bg-yellow-50 rounded-lg text-center">
                <p className="text-yellow-700 mb-2">二维码已过期</p>
                <Button size="sm" onClick={handleGetQrcode}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  重新获取
                </Button>
              </div>
            )}

            {/* Error */}
            {scanStatus === 'error' && error && (
              <div className="p-4 bg-red-50 rounded-lg text-red-700">
                {error}
              </div>
            )}
          </div>
        )}
      </Card>

      <Card className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">运行状态</h2>
            <p className="mt-1 text-sm text-gray-500">
              微信消费者：{consumer?.state === 'active' ? '运行中' : consumer?.state === 'standby' ? '待接管' : '当前环境未启用'}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={loadRuntimeStatus}>
            <RefreshCw className="mr-1 h-4 w-4" />
            刷新
          </Button>
        </div>

        {currentTask ? (
          <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4" data-testid="agent-current-task">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium text-gray-900">{currentTask.summary || currentTask.kind}</p>
                <p className="mt-1 text-sm text-gray-600">
                  阶段：{currentTask.stage} · 状态：{currentTask.canonical_status || currentTask.status}
                  {currentTask.progress_percent != null ? ` · ${currentTask.progress_percent}%` : ''}
                </p>
                <Link
                  to={`/ai-tasks/${encodeURIComponent(currentTask.task_id || currentTask.id)}`}
                  className="mt-1 inline-flex text-xs text-brand-600 underline"
                  data-testid="agent-task-link"
                >
                  打开 AI 任务
                </Link>
              </div>
              <div className="flex gap-2" data-testid="agent-server-actions">
                {(currentTask.available_actions ?? []).includes('cancel') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={taskAction === currentTask.id}
                    onClick={() => handleTaskAction(currentTask, 'cancel')}
                  >
                    取消任务
                  </Button>
                )}
                {(currentTask.available_actions ?? []).includes('resume') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={taskAction === currentTask.id}
                    onClick={() => handleTaskAction(currentTask, 'resume')}
                  >
                    恢复任务
                  </Button>
                )}
              </div>
            </div>
            {canonicalTask && (
              <div className="mt-3" data-testid="agent-canonical-actions">
                <AITaskActions
                  task={canonicalTask}
                  onConflictRefresh={() => {
                    void refetchCanonical()
                    void loadRuntimeStatus()
                  }}
                />
              </div>
            )}
          </div>
        ) : (
          <p className="mt-4 text-sm text-gray-500">当前没有执行中的 Agent 任务。</p>
        )}

        {recoverableTask && !currentTask && (
          <div className="mt-3" data-testid="agent-recoverable-task">
            <Button
              variant="ghost"
              size="sm"
              disabled={taskAction === recoverableTask.id}
              onClick={() => handleTaskAction(recoverableTask, 'resume')}
            >
              恢复最近失败任务
            </Button>
          </div>
        )}
      </Card>

      {/* Preferences Card */}
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">Agent 偏好</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">显示名称</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={20}
              placeholder="我的求职助手"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">免打扰开始</label>
              <Input
                type="time"
                value={quietStart}
                onChange={(e) => setQuietStart(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">免打扰结束</label>
              <Input
                type="time"
                value={quietEnd}
                onChange={(e) => setQuietEnd(e.target.value)}
              />
            </div>
          </div>
          <p className="text-xs text-gray-500">
            免打扰时段内，面试备战报告等推送会延迟发送（需两端都填写，或全部留空关闭）。
          </p>
          <div>
            <label className="block text-sm font-medium mb-1">通知模式</label>
            <select
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
              value={notificationMode}
              onChange={(e) =>
                setNotificationMode(e.target.value as 'realtime' | 'hourly_digest')
              }
            >
              <option value="realtime">实时推送</option>
              <option value="hourly_digest">每小时摘要（规划中）</option>
            </select>
          </div>
          {error && scanStatus !== 'error' && (
            <div className="p-3 bg-red-50 rounded-lg text-sm text-red-700">{error}</div>
          )}
          <Button onClick={handleSavePreferences} disabled={saving}>
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            保存偏好
          </Button>
        </div>
      </Card>
    </div>
  )
}
