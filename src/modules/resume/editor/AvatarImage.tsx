/**
 * AvatarImage — pure render component for a branch avatar.
 *
 * - shape: circle | rounded | square (controls border-radius)
 * - size:  50..200 px (also exposed via --avatar-size for theme CSS to read)
 * - position: left | right | top | center | bottom
 *   - Sets the wrapper's flex/grid placement inside the resume header.
 *   - Exposes data-avatar-position so theme CSS can adjust local spacing.
 *
 * Returns null when avatarUrl is null/empty so callers can drop it in
 * unconditionally without guarding.
 *
 * Spec 027 US9.
 */
import type { AvatarPosition, AvatarShape } from '../api/types'
import { cn } from '@/lib/utils'

interface AvatarImageProps {
  avatarUrl: string | null | undefined
  size?: number | null
  position?: AvatarPosition | null
  shape?: AvatarShape | null
  /** Optional alt text. */
  alt?: string
  className?: string
  /** Show the avatar inline-flex (the default for header placement). */
  block?: boolean
}

const SHAPE_CLASS: Record<AvatarShape, string> = {
  circle: 'rounded-full',
  rounded: 'rounded-lg',
  square: 'rounded-none',
}

export default function AvatarImage({
  avatarUrl,
  size = 100,
  position = 'right',
  shape = 'circle',
  alt = '头像',
  className,
  block = true,
}: AvatarImageProps) {
  if (!avatarUrl) return null

  const px = Math.max(50, Math.min(200, size ?? 100))
  const shapeClass = SHAPE_CLASS[shape ?? 'circle']

  return (
    <div
      className={cn('flex-shrink-0', block && 'block', className)}
      data-avatar-position={position ?? 'right'}
      style={
        {
          width: `${px}px`,
          height: `${px}px`,
          // expose to theme CSS so layouts can use the same value
          ['--avatar-size' as string]: `${px}px`,
        } as React.CSSProperties
      }
    >
      <img
        src={avatarUrl}
        alt={alt}
        className={cn('h-full w-full object-cover', shapeClass)}
        draggable={false}
        loading="eager"
      />
    </div>
  )
}