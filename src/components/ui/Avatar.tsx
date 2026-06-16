import { cn } from '@/lib/utils'
import { useAvatarBlob } from '@/hooks/queries/useAvatarBlob'

interface AvatarProps {
  name: string
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  src?: string
  className?: string
}

const sizeMap = {
  xs: 'h-5 w-5 text-2xs',
  sm: 'h-6 w-6 text-2xs',
  md: 'h-8 w-8 text-xs',
  lg: 'h-10 w-10 text-sm',
  xl: 'h-14 w-14 text-base',
}

const colorPairs = [
  'bg-blue-100 text-blue-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-violet-100 text-violet-700',
  'bg-pink-100 text-pink-700',
  'bg-cyan-100 text-cyan-700',
]

function hash(s: string) {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return h
}

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2)
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function Avatar({ name, size = 'md', src, className }: AvatarProps) {
  const colors = colorPairs[hash(name) % colorPairs.length]
  // Same-origin http(s) URLs (e.g. signed CDN URLs) load directly in <img>.
  // /api/v1/users/me/avatar/<id> requires a bearer token, so it must be
  // fetched through the hook and rendered as a same-origin blob URL.
  const isAuthUrl = typeof src === 'string' && src.includes('/api/v1/users/me/avatar/')
  const blobUrl = useAvatarBlob(isAuthUrl ? src ?? null : null)
  const resolvedSrc = isAuthUrl ? blobUrl : src

  return (
    <div
      className={cn(
        'inline-flex items-center justify-center rounded-full font-semibold overflow-hidden flex-shrink-0',
        sizeMap[size],
        colors,
        className,
      )}
      aria-label={name}
    >
      {resolvedSrc ? (
        <img src={resolvedSrc} alt={name} className="h-full w-full object-cover" />
      ) : (
        <span>{getInitials(name)}</span>
      )}
    </div>
  )
}
