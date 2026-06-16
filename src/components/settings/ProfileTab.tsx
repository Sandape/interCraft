import { useState, useEffect, useRef } from 'react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Input, Textarea } from '@/components/ui/Input'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { useUpdateProfile } from '@/hooks/mutations/useUpdateProfile'
import { useUploadAvatar, useRemoveAvatar } from '@/hooks/mutations/useUploadAvatar'
import { useAvatarBlob } from '@/hooks/queries/useAvatarBlob'
import { AvatarApiError } from '@/api/avatar'

const MAX_BYTES = 2 * 1024 * 1024
const MAX_DIMENSION = 2048
const ACCEPT = 'image/png,image/jpeg'

function isImageFile(file: File): boolean {
  if (file.type === 'image/png' || file.type === 'image/jpeg') return true
  // Some browsers/clients omit the type. Allow common extensions.
  const name = file.name.toLowerCase()
  return name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg')
}

export function ProfileTab() {
  const { data: user } = useCurrentUser()
  const updateProfile = useUpdateProfile()
  const uploadAvatar = useUploadAvatar()
  const removeAvatarMut = useRemoveAvatar()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [displayName, setDisplayName] = useState('')
  const [title, setTitle] = useState('')
  const [yearsOfExperience, setYearsOfExperience] = useState<number>(0)
  const [targetRole, setTargetRole] = useState('')
  const [bio, setBio] = useState('')

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [avatarError, setAvatarError] = useState<string | null>(null)
  const [avatarSuccess, setAvatarSuccess] = useState<string | null>(null)

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name ?? '')
      setTitle(user.title ?? '')
      setYearsOfExperience(user.years_of_experience ?? 0)
      setTargetRole(user.target_role ?? '')
      setBio(user.bio ?? '')
    }
  }, [user])

  // Free the preview object URL when it changes or unmounts.
  useEffect(() => {
    if (!previewUrl) return
    return () => {
      try {
        URL.revokeObjectURL(previewUrl)
      } catch {
        // noop
      }
    }
  }, [previewUrl])

  const handleSave = () => {
    updateProfile.mutate({
      display_name: displayName,
      title,
      years_of_experience: yearsOfExperience,
      target_role: targetRole,
      bio,
    })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAvatarError(null)
    setAvatarSuccess(null)
    const file = e.target.files?.[0]
    if (!file) return
    if (!isImageFile(file)) {
      setAvatarError('仅支持 JPG / PNG 图片')
      e.target.value = ''
      return
    }
    if (file.size > MAX_BYTES) {
      setAvatarError('图片不能超过 2MB')
      e.target.value = ''
      return
    }
    // Client-side dimension check: avoids a round-trip to the server and
    // matches the spec's 2048px cap exactly. Uses an in-memory Image so the
    // preview is not consumed by an object URL we haven't created yet.
    const probe = new Image()
    const probeUrl = URL.createObjectURL(file)
    probe.onload = () => {
      URL.revokeObjectURL(probeUrl)
      if (probe.width > MAX_DIMENSION || probe.height > MAX_DIMENSION) {
        setAvatarError(`图片尺寸不能超过 ${MAX_DIMENSION}x${MAX_DIMENSION}`)
        e.target.value = ''
        setSelectedFile(null)
        setPreviewUrl(null)
        return
      }
      setSelectedFile(file)
      setPreviewUrl(URL.createObjectURL(file))
    }
    probe.onerror = () => {
      URL.revokeObjectURL(probeUrl)
      setAvatarError('图片文件无法解析')
      e.target.value = ''
    }
    probe.src = probeUrl
  }

  const handleConfirmUpload = async () => {
    if (!selectedFile) return
    setAvatarError(null)
    setAvatarSuccess(null)
    try {
      await uploadAvatar.mutateAsync(selectedFile)
      setAvatarSuccess('头像已更新')
      setSelectedFile(null)
      setPreviewUrl(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      if (err instanceof AvatarApiError) {
        setAvatarError(err.message)
      } else if (err instanceof Error) {
        setAvatarError(err.message)
      } else {
        setAvatarError('上传失败')
      }
    }
  }

  const handleCancelPreview = () => {
    setSelectedFile(null)
    setPreviewUrl(null)
    setAvatarError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleRemove = async () => {
    setAvatarError(null)
    setAvatarSuccess(null)
    try {
      await removeAvatarMut.mutateAsync()
      setAvatarSuccess('已移除头像')
    } catch (err) {
      if (err instanceof AvatarApiError) {
        setAvatarError(err.message)
      } else if (err instanceof Error) {
        setAvatarError(err.message)
      } else {
        setAvatarError('移除失败')
      }
    }
  }

  const displayAvatarUrl = previewUrl ?? user?.avatar_url ?? undefined
  const remoteAvatarBlob = useAvatarBlob(user?.avatar_url ?? null)
  const avatarToShow = previewUrl ?? remoteAvatarBlob ?? undefined
  const hasAvatar = !!user?.avatar_url || !!previewUrl
  const uploading = uploadAvatar.isPending

  return (
    <>
      <Card className="p-5">
        <CardHeader title="基础信息" />
        <div className="flex items-center gap-4 mb-4 pb-4 border-b border-surface-border dark:border-dark-surface-border">
          <Avatar name={displayName || 'User'} size="xl" src={avatarToShow} />
          <div className="flex-1 min-w-0">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT}
              data-testid="avatar-file-input"
              className="hidden"
              onChange={handleFileChange}
            />
            <div className="flex items-center gap-2 flex-wrap">
              <Button
                size="sm"
                variant="secondary"
                data-testid="avatar-change-button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                更换头像
              </Button>
              {selectedFile && (
                <>
                  <Button
                    size="sm"
                    variant="primary"
                    data-testid="avatar-confirm"
                    onClick={handleConfirmUpload}
                    loading={uploading}
                  >
                    确认上传
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleCancelPreview}
                    disabled={uploading}
                  >
                    取消
                  </Button>
                </>
              )}
              {!selectedFile && hasAvatar && (
                <Button
                  size="sm"
                  variant="ghost"
                  data-testid="avatar-remove"
                  onClick={handleRemove}
                  disabled={removeAvatarMut.isPending}
                >
                  {removeAvatarMut.isPending ? '正在移除…' : '移除头像'}
                </Button>
              )}
            </div>
            <div className="text-2xs text-ink-3 mt-1.5">支持 JPG、PNG，最大 2MB</div>
            {avatarError && (
              <div
                data-testid="avatar-error"
                className="mt-2 text-xs text-red-600 dark:text-red-400"
              >
                {avatarError}
              </div>
            )}
            {avatarSuccess && (
              <div
                data-testid="avatar-success"
                className="mt-2 text-xs text-emerald-600 dark:text-emerald-400"
              >
                {avatarSuccess}
              </div>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">姓名</label>
            <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">邮箱</label>
            <Input value={user?.email ?? ''} disabled />
            <div className="text-2xs text-ink-3 mt-0.5">邮箱不可修改</div>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">当前职位</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="如：高级前端工程师" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">工作年限</label>
            <Input type="number" value={String(yearsOfExperience)} onChange={(e) => setYearsOfExperience(Number(e.target.value) || 0)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">目标岗位</label>
            <Input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} placeholder="如：高级前端工程师" />
          </div>
        </div>
        <div className="mt-3">
          <label className="block text-xs font-medium text-ink-2 mb-1.5">个人简介</label>
          <Textarea rows={3} value={bio} onChange={(e) => setBio(e.target.value)} placeholder="介绍一下自己…" />
        </div>
        {updateProfile.isSuccess && (
          <div className="mt-3 text-xs text-emerald-600 dark:text-emerald-400">保存成功</div>
        )}
        {updateProfile.isError && (
          <div className="mt-3 text-xs text-red-600 dark:text-red-400">
            {(updateProfile.error as Error)?.message ?? '保存失败'}
          </div>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" disabled={updateProfile.isPending}>取消</Button>
          <Button variant="primary" onClick={handleSave} loading={updateProfile.isPending}>
            保存修改
          </Button>
        </div>
      </Card>
    </>
  )
}
