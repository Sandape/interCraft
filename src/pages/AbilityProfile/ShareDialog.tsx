/** ShareDialog — create and manage share links. */
import { useState } from 'react'
import { X, Copy, Check, Trash2, Clock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCreateShareLink, useRevokeShareLink } from './hooks/mutations/useShareLink'
import { useShareLinks } from './hooks/queries/useAbilityProfile'
import type { ShareLinkListItem } from '@/api/abilityProfileClient'

interface Props {
  onClose: () => void
}

export default function ShareDialog({ onClose }: Props) {
  const [pin, setPin] = useState('')
  const [expiry, setExpiry] = useState<number | undefined>(undefined)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [newLinkUrl, setNewLinkUrl] = useState<string | null>(null)

  const { data: linksData, isLoading } = useShareLinks()
  const createShareLink = useCreateShareLink()
  const revokeShareLink = useRevokeShareLink()
  const currentUser = useAuthStore((s) => s.user)

  const links = linksData?.data ?? []

  const displayName = currentUser?.display_name || currentUser?.email.split('@')[0] || '我'

  const handleCreate = async () => {
    const result = await createShareLink.mutateAsync({
      pin: pin || undefined,
      expiresInHours: expiry,
    })
    const url = `${window.location.origin}${result.data.url}`
    setNewLinkUrl(url)
    await navigator.clipboard.writeText(url)
    setCopiedId('new')
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleCopy = async (url: string, id: string) => {
    await navigator.clipboard.writeText(url)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const fullUrl = (token: string) => `${window.location.origin}/shared/${token}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white dark:bg-dark-surface rounded-xl shadow-xl p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-ink-1">分享能力画像</h3>
          <button onClick={onClose} className="text-ink-3 hover:text-ink-1">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* User identity preview */}
        <div className="mb-4 flex items-center gap-2.5" data-testid="share-dialog-user">
          <Avatar
            name={displayName}
            size="sm"
            src={currentUser?.avatar_url ?? undefined}
          />
          <div className="min-w-0">
            <div className="text-sm font-medium text-ink-1 truncate">{displayName}</div>
            <div className="text-2xs text-ink-3 truncate">的能力画像</div>
          </div>
        </div>

        {/* Create new link */}
        <div className="mb-6 p-4 rounded-lg bg-surface-muted dark:bg-dark-surface-muted">
          <h4 className="text-sm font-medium text-ink-1 mb-3">生成新分享链接</h4>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-ink-2 block mb-1">过期时间</label>
              <select
                value={expiry ?? ''}
                onChange={(e) => setExpiry(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full text-sm border border-surface-border dark:border-dark-surface-border rounded-lg p-2 bg-transparent text-ink-1"
              >
                <option value="">永不过期</option>
                <option value={1}>1 小时</option>
                <option value={24}>24 小时</option>
                <option value={48}>48 小时</option>
                <option value={168}>7 天</option>
                <option value={720}>30 天</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-ink-2 block mb-1">PIN 码 (可选)</label>
              <input
                type="text"
                maxLength={4}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
                placeholder="4 位数字"
                className="w-full text-sm border border-surface-border dark:border-dark-surface-border rounded-lg p-2 bg-transparent text-ink-1 placeholder:text-ink-4"
              />
            </div>
            <Button
              variant="primary"
              onClick={handleCreate}
              loading={createShareLink.isPending}
              className="w-full"
            >
              {createShareLink.isPending ? '生成中...' : '生成链接'}
            </Button>
          </div>

          {newLinkUrl && (
            <div className="mt-3 p-2 bg-brand-50 dark:bg-brand-500/10 rounded-lg flex items-center gap-2 text-sm">
              <span className="flex-1 truncate text-brand-700 dark:text-brand-300">{newLinkUrl}</span>
              {copiedId === 'new' ? (
                <Check className="h-4 w-4 text-emerald-500 shrink-0" />
              ) : (
                <Copy className="h-4 w-4 text-ink-3 shrink-0 cursor-pointer" />
              )}
            </div>
          )}
        </div>

        {/* Existing links */}
        <div>
          <h4 className="text-sm font-medium text-ink-1 mb-2">已生成的链接</h4>
          {isLoading ? (
            <p className="text-xs text-ink-3">加载中...</p>
          ) : links.length === 0 ? (
            <p className="text-xs text-ink-3">暂无分享链接</p>
          ) : (
            <div className="space-y-2">
              {links.map((link: ShareLinkListItem) => (
                <div
                  key={link.id}
                  className="flex items-center gap-2 p-2 rounded-lg border border-surface-border dark:border-dark-surface-border"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-2xs font-medium px-1.5 py-0.5 rounded ${
                        link.status === 'active' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' :
                        link.status === 'expired' ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300' :
                        'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300'
                      }`}>
                        {link.status === 'active' ? '活跃' : link.status === 'expired' ? '已过期' : '已撤销'}
                      </span>
                      {link.has_pin && <span className="text-2xs text-ink-3">🔒 PIN</span>}
                      {link.expires_at && (
                        <span className="text-2xs text-ink-3 flex items-center gap-0.5">
                          <Clock className="h-2.5 w-2.5" />
                          过期
                        </span>
                      )}
                    </div>
                    <div className="text-2xs text-ink-3 mt-0.5">
                      访问 {link.access_count} 次
                      {link.last_accessed_at && ` · 最后访问 ${new Date(link.last_accessed_at).toLocaleDateString()}`}
                    </div>
                  </div>
                  {link.status === 'active' && (
                    <>
                      <button
                        onClick={() => handleCopy(fullUrl(link.token), link.id)}
                        className="p-1.5 text-ink-3 hover:text-brand-600 transition-colors"
                        title="复制链接"
                      >
                        {copiedId === link.id ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                      <button
                        onClick={() => revokeShareLink.mutate(link.id)}
                        className="p-1.5 text-ink-3 hover:text-red-500 transition-colors"
                        title="撤销"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
