/**
 * ResumeV2New — creates a new v2 resume and navigates to its editor (US1 T028).
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createResume } from '@/modules/resume/v2/api'

function randomSlug(): string {
  // 8 hex chars; backend enforces ^[a-z0-9-]+$, 1..64 chars.
  return `v2-${Math.random().toString(16).slice(2, 10)}`
}

export default function ResumeV2New() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      setCreating(true)
      setError(null)
      try {
        const r = await createResume({
          name: 'Untitled v2 Resume',
          slug: randomSlug(),
          template: 'pikachu',
          from_sample: true,
        })
        if (!cancelled) navigate(`/resume/${r.id}`, { replace: true })
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to create')
          setCreating(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [navigate])

  if (error) {
    return (
      <div className="p-8 text-sm text-ink-3">
        <div className="mb-2 text-base text-ink-1">创建失败</div>
        <div className="text-xs text-ink-3">{error}</div>
        <button
          type="button"
          onClick={() => navigate('/dashboard')}
          className="mt-4 text-xs text-primary-500"
        >
          返回
        </button>
      </div>
    )
  }

  return (
    <div className="p-8 text-sm text-ink-3">
      {creating ? '正在创建新简历…' : ''}
    </div>
  )
}
