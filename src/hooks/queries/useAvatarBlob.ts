/**
 * useAvatarBlob — fetch an authenticated avatar URL and convert to a
 * same-origin object URL the browser can load in an `<img>` tag.
 *
 * The GET /users/me/avatar/{id} endpoint requires a bearer token, so a
 * bare `<img src=...>` request would 401. This hook handles the fetch
 * + cleanup of the object URL.
 */
import { useEffect, useState } from 'react'
import { fetchAvatarBlob } from '@/api/avatar'

export function useAvatarBlob(avatarUrl: string | null | undefined): string | null {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!avatarUrl) {
      setBlobUrl(null)
      return
    }

    let cancelled = false
    let currentUrl: string | null = null

    fetchAvatarBlob(avatarUrl)
      .then((blob) => {
        if (cancelled) return
        currentUrl = URL.createObjectURL(blob)
        setBlobUrl(currentUrl)
      })
      .catch(() => {
        if (cancelled) return
        setBlobUrl(null)
      })

    return () => {
      cancelled = true
      if (currentUrl) URL.revokeObjectURL(currentUrl)
    }
  }, [avatarUrl])

  return blobUrl
}
