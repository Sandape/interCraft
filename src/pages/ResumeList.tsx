/**
 * ResumeList page — lists branches from the repository, allows creating
 * a new branch (cloned from main by default) and navigates into the
 * editor on click. Supports in-place edit, delete, pin, and status display.
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, Sparkles, FileText, GitBranch, Clock, Pin, Pencil, Trash2, Upload } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Input } from '@/components/ui/Input'
import { useResumeBranches } from '@/hooks/queries/useResumeBranches'
import { useCreateBranch, useDeleteBranch, usePatchBranch } from '@/hooks/mutations/useBranchMutations'
import { timeAgo, cn } from '@/lib/utils'
import type { BranchStatus, ResumeBranch } from '@/api/types'
import PrimaryResumeCard from '@/components/resume/list/PrimaryResumeCard'
import ImportModal from '@/components/resume/import/ImportModal'

const STATUS_LABEL: Record<BranchStatus, string> = {
  draft: '草稿',
  optimizing: '优化中',
  ready: '就绪',
  submitted: '已投递',
  archived: '归档',
}

const STATUS_VARIANT: Record<BranchStatus, 'default' | 'success' | 'warning' | 'brand'> = {
  draft: 'default',
  optimizing: 'warning',
  ready: 'success',
  submitted: 'brand',
  archived: 'default',
}

export default function ResumeList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: branches = [], isLoading } = useResumeBranches()
  const createBranch = useCreateBranch()
  const deleteBranch = useDeleteBranch()
  const patchBranch = usePatchBranch()

  const main = branches.find((b) => b.is_main) ?? branches[0]

  // Create modal
  const [open, setOpen] = useState(false)

  // Auto-open create modal when ?new=true is present in the URL
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setOpen(true)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const [name, setName] = useState('')
  const [company, setCompany] = useState('')
  const [position, setPosition] = useState('')
  const [parentId, setParentId] = useState<string | null>(null)

  // Import modal
  const [importOpen, setImportOpen] = useState(false)

  // Delete modal
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // Edit modal
  const [editTarget, setEditTarget] = useState<ResumeBranch | null>(null)
  const [editName, setEditName] = useState('')
  const [editCompany, setEditCompany] = useState('')
  const [editPosition, setEditPosition] = useState('')
  const [editStatus, setEditStatus] = useState<BranchStatus>('draft')

  function openEdit(b: ResumeBranch) {
    setEditTarget(b)
    setEditName(b.name)
    setEditCompany(b.company ?? '')
    setEditPosition(b.position ?? '')
    setEditStatus(b.status)
  }

  function onSaveEdit() {
    if (!editTarget || !editName.trim()) return
    patchBranch.mutate(
      {
        id: editTarget.id,
        input: {
          name: editName.trim(),
          company: editCompany.trim() || null,
          position: editPosition.trim() || null,
          status: editStatus,
        },
      },
      { onSuccess: () => setEditTarget(null) },
    )
  }

  function onCreate() {
    if (!name.trim()) return
    createBranch.mutate(
      {
        name: name.trim(),
        company: company.trim() || null,
        position: position.trim() || null,
        parent_id: parentId ?? main?.id ?? null,
      },
      {
        onSuccess: (branch) => {
          setOpen(false)
          setName('')
          setCompany('')
          setPosition('')
          setParentId(null)
          setSearchParams({}, { replace: true })
          navigate(`/resume/${branch.id}`)
        },
      },
    )
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-ink-1 tracking-tight">简历中心</h1>
          <p className="text-sm text-ink-3 mt-1">
            维护一份核心简历，针对不同岗位克隆出定制版本（COW 不会污染源）
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            leftIcon={<Upload className="h-3.5 w-3.5" />}
            onClick={() => setImportOpen(true)}
            data-testid="import-markdown-button"
          >
            导入 Markdown
          </Button>
          <Button
            variant="primary"
            leftIcon={<Plus className="h-3.5 w-3.5" />}
            onClick={() => setOpen(true)}
            data-testid="new-branch-button"
          >
            新建分支
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-sm text-ink-3">加载中…</div>
      ) : branches.length === 0 ? (
        <Card padding="lg" className="text-center">
          <FileText className="h-8 w-8 text-ink-muted mx-auto" />
          <p className="mt-3 text-sm text-ink-2">还没有简历</p>
          <p className="text-2xs text-ink-3 mt-1">点击「新建分支」创建第一份简历</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Primary resume card */}
          {main && (
            <>
              <PrimaryResumeCard
                branch={main}
                blockCount={main.block_count}
              />
              {/* Section separator */}
              <div className="flex items-center gap-3 pt-2">
                <div className="flex-1 h-px bg-surface-border dark:bg-dark-surface-border" />
                <span className="text-xs text-ink-3 flex-shrink-0">
                  派生简历 · {branches.filter((b) => !b.is_main).length} 份
                </span>
                <div className="flex-1 h-px bg-surface-border dark:bg-dark-surface-border" />
              </div>
            </>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {branches.map((b) => (
            <Link key={b.id} to={`/resume/${b.id}`} className="group" data-testid={`branch-card-${b.id}`}>
              <Card hover padding="md" className="h-full relative">
                {/* Pin indicator */}
                {b.is_pinned && (
                  <Pin className="absolute top-2 right-2 h-3 w-3 text-amber-500 fill-amber-500" />
                )}

                <div className="flex items-start gap-3 mb-3">
                  <div
                    className={cn(
                      'h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0',
                      b.is_main
                        ? 'bg-brand-50 dark:bg-brand-500/15 text-brand-600'
                        : 'bg-surface-muted text-ink-2',
                    )}
                  >
                    {b.is_main ? <Sparkles className="h-3.5 w-3.5" /> : <FileText className="h-3.5 w-3.5" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-ink-1 truncate group-hover:text-brand-600 transition-colors">
                      {b.name}
                    </div>
                    {b.company && (
                      <div className="text-2xs text-ink-3 mt-0.5 truncate">
                        {b.company}{b.position ? ` · ${b.position}` : ''}
                      </div>
                    )}
                    {!b.company && b.position && (
                      <div className="text-2xs text-ink-3 mt-0.5 truncate">{b.position}</div>
                    )}
                    <div className="text-2xs text-ink-3 mt-0.5">
                      {b.is_main ? '主简历（数据源）' : b.parent_id ? '基于主简历克隆' : '独立分支'}
                    </div>
                  </div>
                </div>

                {/* Status badges + match score */}
                <div className="flex items-center justify-between text-2xs mb-3">
                  <Badge variant={STATUS_VARIANT[b.status]}>{STATUS_LABEL[b.status]}</Badge>
                  {b.match_score != null && (
                    <span
                      className={cn(
                        'font-medium',
                        b.match_score >= 90 ? 'text-emerald-600' : b.match_score >= 80 ? 'text-brand-600' : 'text-amber-600',
                      )}
                    >
                      匹配 {b.match_score}%
                    </span>
                  )}
                </div>

                {/* Footer: time + actions */}
                <div className="flex items-center justify-between text-2xs text-ink-3 pt-3 border-t border-surface-border dark:border-dark-surface-border">
                  <span className="flex items-center gap-1">
                    <Clock className="h-2.5 w-2.5" />
                    {b.last_edited_at ? timeAgo(b.last_edited_at) : '刚刚创建'}
                  </span>
                  <span className="flex items-center gap-1">
                    {b.parent_id && (
                      <Badge variant="default" leftIcon={<GitBranch className="h-2.5 w-2.5" />}>
                        派生
                      </Badge>
                    )}
                  </span>
                </div>

                {/* Action buttons — visible on hover */}
                <div
                  className="absolute top-2 right-6 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => e.preventDefault()}
                >
                  {/* Pin toggle */}
                  {!b.is_main && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        e.preventDefault()
                        patchBranch.mutate({ id: b.id, input: { is_pinned: !b.is_pinned } })
                      }}
                      className="p-1 rounded hover:bg-surface-muted text-ink-3 hover:text-ink-1"
                      aria-label={b.is_pinned ? '取消置顶' : '置顶'}
                    >
                      <Pin className={cn('h-3 w-3', b.is_pinned && 'fill-brand-500 text-brand-500')} />
                    </button>
                  )}
                  {/* Edit */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      e.preventDefault()
                      openEdit(b)
                    }}
                    className="p-1 rounded hover:bg-surface-muted text-ink-3 hover:text-ink-1"
                    aria-label="编辑属性"
                  >
                    <Pencil className="h-3 w-3" />
                  </button>
                  {/* Delete — not for main branch */}
                  {!b.is_main && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        e.preventDefault()
                        setDeleteTarget(b.id)
                        setDeleteError(null)
                      }}
                      className="p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-ink-3 hover:text-red-500"
                      aria-label="删除分支"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </Card>
            </Link>
          ))}
        </div>
        </div>
      )}

      {/* Create branch modal */}
      <Modal
        open={open}
        onClose={() => {
          setOpen(false)
          setSearchParams({}, { replace: true })
        }}
        title="新建简历分支"
        description="克隆主简历的块结构；后续对分支的修改不会影响源"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => {
              setOpen(false)
              setSearchParams({}, { replace: true })
            }}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={!name.trim() || createBranch.isPending}
              onClick={onCreate}
              data-testid="create-branch-confirm"
            >
              {createBranch.isPending ? '创建中…' : '创建分支'}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">分支名称</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：字节前端 · 2026"
              data-testid="new-branch-name"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">公司（可选）</label>
            <Input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="例如：字节跳动"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">职位（可选）</label>
            <Input
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              placeholder="例如：高级前端工程师"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">基于</label>
            <select
              className="w-full h-9 px-3 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1"
              value={parentId ?? main?.id ?? ''}
              onChange={(e) => setParentId(e.target.value || null)}
              data-testid="new-branch-parent"
            >
              {main && <option value={main.id}>主简历（{main.name}）</option>}
              {branches
                .filter((b) => !b.is_main)
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
            </select>
          </div>
        </div>
      </Modal>

      {/* Edit branch modal */}
      <Modal
        open={editTarget !== null}
        onClose={() => setEditTarget(null)}
        title="编辑分支属性"
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditTarget(null)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={!editName.trim() || patchBranch.isPending}
              onClick={onSaveEdit}
            >
              {patchBranch.isPending ? '保存中…' : '保存'}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">名称</label>
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">公司</label>
            <Input value={editCompany} onChange={(e) => setEditCompany(e.target.value)} placeholder="（可选）" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">职位</label>
            <Input value={editPosition} onChange={(e) => setEditPosition(e.target.value)} placeholder="（可选）" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">状态</label>
            <select
              className="w-full h-9 px-3 text-sm rounded-md border border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface text-ink-1"
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value as BranchStatus)}
            >
              {Object.entries(STATUS_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation modal */}
      <Modal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="删除简历分支"
        description="删除后无法恢复，相关模块和版本也会一并删除"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button
              variant="primary"
              className="bg-red-600 hover:bg-red-700"
              disabled={deleteBranch.isPending}
              onClick={() => {
                if (!deleteTarget) return
                deleteBranch.mutate(deleteTarget, {
                  onSuccess: () => setDeleteTarget(null),
                  onError: (err) => setDeleteError(err.message),
                })
              }}
            >
              {deleteBranch.isPending ? '删除中…' : '确认删除'}
            </Button>
          </>
        }
      >
        {deleteError && <p className="text-sm text-red-500 mb-2">{deleteError}</p>}
        <p className="text-sm text-ink-2">确认删除此分支？</p>
      </Modal>

      {/* Import markdown modal */}
      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  )
}
