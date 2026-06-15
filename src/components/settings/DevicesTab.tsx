import { useState, useEffect } from 'react'
import { Smartphone, Monitor, LogOut, RefreshCw } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { accountApi, type DeviceItem } from '@/api/account'

export default function DevicesTab() {
  const [devices, setDevices] = useState<DeviceItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    accountApi.listDevices().then((res) => {
      setDevices(res.devices)
      setLoading(false)
    })
  }, [])

  const handleLogoutOthers = async () => {
    if (!confirm('确定要下线其他设备吗？')) return
    await accountApi.logoutOtherDevices()
    setDevices((prev) => prev.filter((d) => d.is_current))
  }

  if (loading) {
    return <Card className="p-5 text-center text-sm text-ink-3">加载中...</Card>
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <CardHeader
          title="已登录设备"
          description="登录您账号的设备列表。如发现不认识的设备，请立即下线。"
        />
        <div className="space-y-2">
          {devices.length === 0 && (
            <p className="text-sm text-ink-3 py-4 text-center">暂无设备记录</p>
          )}
          {devices.map((d) => (
            <div
              key={d.id}
              className="flex items-center justify-between p-3 rounded-md border border-surface-border dark:border-dark-surface-border"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-md bg-surface-muted dark:bg-dark-surface-muted flex items-center justify-center">
                  {d.device_name?.toLowerCase().includes('mobile') ? (
                    <Smartphone className="h-4 w-4 text-ink-2" />
                  ) : (
                    <Monitor className="h-4 w-4 text-ink-2" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-ink-1">{d.device_name || '未知设备'}</span>
                    {d.is_current && <Badge variant="brand">当前设备</Badge>}
                  </div>
                  <div className="text-2xs text-ink-3 mt-0.5">
                    {d.browser && <span>{d.browser} · </span>}
                    {d.ip && <span>{d.ip} · </span>}
                    {d.last_seen_at && <span>最近活跃 {new Date(d.last_seen_at).toLocaleString('zh-CN')}</span>}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        {devices.length > 1 && (
          <div className="mt-4 pt-3 border-t border-surface-border dark:border-dark-surface-border">
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<LogOut className="h-3.5 w-3.5" />}
              onClick={handleLogoutOthers}
            >
              下线其他设备
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
