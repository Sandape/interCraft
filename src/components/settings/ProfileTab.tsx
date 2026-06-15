import { useState, useEffect } from 'react'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Input, Textarea } from '@/components/ui/Input'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { useUpdateProfile } from '@/hooks/mutations/useUpdateProfile'

export function ProfileTab() {
  const { data: user } = useCurrentUser()
  const updateProfile = useUpdateProfile()

  const [displayName, setDisplayName] = useState('')
  const [title, setTitle] = useState('')
  const [yearsOfExperience, setYearsOfExperience] = useState<number>(0)
  const [targetRole, setTargetRole] = useState('')
  const [bio, setBio] = useState('')

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name ?? '')
      setTitle(user.title ?? '')
      setYearsOfExperience(user.years_of_experience ?? 0)
      setTargetRole(user.target_role ?? '')
      setBio(user.bio ?? '')
    }
  }, [user])

  const handleSave = () => {
    updateProfile.mutate({
      display_name: displayName,
      title,
      years_of_experience: yearsOfExperience,
      target_role: targetRole,
      bio,
    })
  }

  return (
    <>
      <Card className="p-5">
        <CardHeader title="基础信息" />
        <div className="flex items-center gap-4 mb-4 pb-4 border-b border-surface-border dark:border-dark-surface-border">
          <Avatar name={displayName || 'User'} size="xl" />
          <div>
            <Button size="sm" variant="secondary">
              更换头像
            </Button>
            <div className="text-2xs text-ink-3 mt-1.5">支持 JPG、PNG，最大 2MB</div>
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
