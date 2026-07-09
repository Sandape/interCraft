import { useState, useEffect, useCallback, useRef } from 'react'
import { QrCode, Unlink, RefreshCw, Loader2, CheckCircle2, Clock } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { AgentRepository, resolveQrcodeSrc } from '@/repositories/AgentRepository'
import type { BindingStatus, AgentPreferences } from '@/repositories/AgentRepository'

type ScanStatus = 'idle' | 'loading' | 'waiting' | 'scanned' | 'confirmed' | 'expired' | 'error'

export default function AgentSettings() {
  const [binding, setBinding] = useState<BindingStatus | null>(null)
  const [scanStatus, setScanStatus] = useState<ScanStatus>('idle')
  const [qrcodeSrc, setQrcodeSrc] = useState<string | null>(null)
  const [qrcodeToken, setQrcodeToken] = useState<string | null>(null)
  const [expiresIn, setExpiresIn] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [preferences, setPreferences] = useState<AgentPreferences | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [saving, setSaving] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load binding status on mount
  useEffect(() => {
    loadBindingStatus()
    loadPreferences()
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
    try {
      const data = await AgentRepository.fetchBindingStatus()
      setBinding(data)
    } catch {
      // Not bound yet
    }
  }

  const loadPreferences = async () => {
    try {
      const data = await AgentRepository.fetchPreferences()
      setPreferences(data)
      setDisplayName(data.display_name)
    } catch { /* ignore */ }
  }

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
    try {
      await AgentRepository.updatePreferences({ display_name: displayName })
      setPreferences((prev) => prev ? { ...prev, display_name: displayName } : prev)
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

        {binding?.bound ? (
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
          <Button onClick={handleSavePreferences} disabled={saving}>
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            保存偏好
          </Button>
        </div>
      </Card>
    </div>
  )
}
