/**
 * EvictionToast — FR-004: shows "当前设备已被其他登录踢出" when the
 * session was evicted by a newer login on another device.
 *
 * The Toast does NOT clear tokens or redirect. The user dismisses it
 * when they are ready to handle the eviction (e.g., re-login).
 */
import { useEffect } from 'react'
import { LogOut, X } from 'lucide-react'
import { useAuthStore } from '../../stores/useAuthStore'
import { clearTokens } from '../../api/token-storage'

export function EvictionToast() {
  const evicted = useAuthStore((s) => s.evicted)
  const setEvicted = useAuthStore((s) => s.setEvicted)

  useEffect(() => {
    if (evicted) {
      // Auto-dismiss after 10 seconds if user doesn't act.
      const timer = setTimeout(() => {
        setEvicted(false)
      }, 10_000)
      return () => clearTimeout(timer)
    }
  }, [evicted, setEvicted])

  if (!evicted) return null

  function handleLogout() {
    clearTokens()
    setEvicted(false)
    window.location.href = '/login'
  }

  return (
    <div
      role="alert"
      data-testid="eviction-toast"
      className="fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 shadow-lg dark:border-orange-800 dark:bg-orange-950"
    >
      <LogOut className="h-4 w-4 shrink-0 text-orange-600 dark:text-orange-400" />
      <div className="text-sm text-orange-800 dark:text-orange-200">
        <span className="font-medium">当前设备已被其他登录踢出</span>
        <p className="text-xs text-orange-600 dark:text-orange-400">
          你的账号已在其他设备上登录。如需继续使用，请重新登录。
        </p>
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-md bg-orange-200 px-2.5 py-1 text-xs font-medium text-orange-800 hover:bg-orange-300 dark:bg-orange-800 dark:text-orange-200 dark:hover:bg-orange-700"
          data-testid="eviction-logout-btn"
        >
          重新登录
        </button>
        <button
          type="button"
          onClick={() => setEvicted(false)}
          className="rounded-md p-1 text-orange-500 hover:bg-orange-200 dark:hover:bg-orange-800"
          aria-label="关闭"
          data-testid="eviction-dismiss-btn"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
