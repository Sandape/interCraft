import { useState } from 'react'
import { Shield, AlertTriangle, Trash2, History } from 'lucide-react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { accountApi, type LoginHistoryItem } from '@/api/account'

export default function SecurityTab() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState('')
  const [loginHistory, setLoginHistory] = useState<LoginHistoryItem[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleChangePassword = async () => {
    setPasswordMessage('')
    if (newPassword !== confirmPassword) {
      setPasswordMessage('两次密码不一致')
      return
    }
    if (newPassword.length < 6) {
      setPasswordMessage('新密码至少 6 位')
      return
    }
    setChangingPassword(true)
    try {
      await accountApi.changePassword({ current_password: currentPassword, new_password: newPassword })
      setPasswordMessage('密码已更新')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch {
      setPasswordMessage('密码更新失败')
    } finally {
      setChangingPassword(false)
    }
  }

  const handleLoadHistory = async () => {
    if (showHistory) {
      setShowHistory(false)
      return
    }
    const res = await accountApi.getLoginHistory()
    setLoginHistory(res.items)
    setShowHistory(true)
  }

  const handleDeleteAccount = async () => {
    if (!confirm('确定要注销账号吗？此操作不可恢复！')) return
    if (!confirm('再次确认：账号注销后 90 天物理清除所有数据。')) return
    setDeleting(true)
    try {
      await accountApi.deleteAccount()
      alert('账号已进入注销流程，7 天内可取消。')
    } catch {
      alert('注销失败')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <CardHeader title="登录密码" description="定期更换密码可以提高账号安全性" />
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">当前密码</label>
            <Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">新密码</label>
            <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">确认新密码</label>
            <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
          </div>
          {passwordMessage && (
            <p className={`text-xs ${passwordMessage.includes('失败') || passwordMessage.includes('不一致') ? 'text-red-500' : 'text-emerald-500'}`}>
              {passwordMessage}
            </p>
          )}
          <div className="flex justify-end">
            <Button variant="primary" onClick={handleChangePassword} disabled={changingPassword}>
              {changingPassword ? '更新中...' : '更新密码'}
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader title="登录活动" description="查看最近的登录记录" />
        <Button variant="secondary" size="sm" leftIcon={<History className="h-3.5 w-3.5" />} onClick={handleLoadHistory}>
          {showHistory ? '隐藏记录' : '查看登录记录'}
        </Button>
        {showHistory && (
          <div className="mt-3 space-y-1.5">
            {loginHistory.length === 0 && (
              <p className="text-sm text-ink-3">暂无登录记录</p>
            )}
            {loginHistory.map((item) => (
              <div key={item.id} className="flex items-center justify-between py-1.5 text-xs">
                <span className="text-ink-2">{item.device_name || '未知设备'}</span>
                <span className="text-ink-3">{item.ip && `${item.ip} · `}{new Date(item.created_at).toLocaleString('zh-CN')}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-5 border-red-200/60 dark:border-red-500/20">
        <div className="flex items-start gap-3">
          <div className="h-9 w-9 rounded-md bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-ink-1">危险操作</h3>
            <p className="text-xs text-ink-3 mt-1 leading-relaxed">
              注销账号会永久删除所有数据，包括简历、面试记录、能力画像。此操作不可恢复。
            </p>
            <div className="mt-3">
              <Button variant="danger" leftIcon={<Trash2 className="h-3.5 w-3.5" />} onClick={handleDeleteAccount} disabled={deleting}>
                {deleting ? '处理中...' : '永久注销账号'}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
