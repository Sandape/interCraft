/**
 * AvatarDialog — upload, configure, and manage a branch's avatar (spec 027 US9).
 *
 * Sections:
 * 1. Drop / browse area for the source image (shown when no avatar yet)
 * 2. Live preview using <AvatarImage /> with current size/position/shape
 * 3. Controls: size slider (50..200), position picker (5), shape picker (3)
 * 4. Actions: Inherit-from-parent (only when branch has parent), Delete,
 *    Save (commits size/position/shape via PATCH branch).
 *
 * The dialog is fully controlled — it does not own the branch state. The
 * caller passes the current `branch` snapshot and receives PATCH input via
 * `onSave`. On close, the local draft is discarded.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Trash2, Upload, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import AvatarImage from './AvatarImage'
import {
  AVATAR_DEFAULT_POSITION,
  AVATAR_DEFAULT_SHAPE,
  AVATAR_DEFAULT_SIZE,
  AVATAR_POSITIONS,
  AVATAR_SHAPES,
  AVATAR_SIZE_MAX,
  AVATAR_SIZE_MIN,
  type AvatarPosition,
  type AvatarShape,
  type PatchBranchInput,
  type ResumeBranch,
} from '../api/types'
import {
  BranchAvatarApiError,
} from '../api/avatar'
import {
  useDeleteBranchAvatar,
  useInheritBranchAvatar,
  useUploadBranchAvatar,
} from '../hooks/useBranchAvatar'

interface AvatarDialogProps {
  open: boolean
  onClose: () => void
  branch: ResumeBranch
  /** Called when user clicks "保存"; receives the PATCH input to commit. */
  onSave: (patch: PatchBranchInput) => void | Promise<void>
}

const POSITION_LABEL: Record<AvatarPosition, string> = {
  left: '左',
  right: '右',
  top: '顶',
  center: '中',
  bottom: '底',
}

const SHAPE_LABEL: Record<AvatarShape, string> = {
  circle: '圆形',
  rounded: '圆角',
  square: '方形',
}

function describeError(e: unknown): string {
  if (e instanceof BranchAvatarApiError) {
    const code = e.code
    if (code === 'FILE_TOO_LARGE') return '图片过大(上限 2 MB),请压缩后重试'
    if (code === 'UNSUPPORTED_FORMAT') return '仅支持 PNG / JPEG / WebP'
    if (code === 'EMPTY_FILE') return '请选择一张图片'
    if (code === 'CANNOT_INHERIT') return '父级没有头像或本分支没有父级'
    return e.message
  }
  if (e instanceof Error) return e.message
  return '未知错误'
}

export default function AvatarDialog({ open, onClose, branch, onSave }: AvatarDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const upload = useUploadBranchAvatar(branch.id)
  const remove = useDeleteBranchAvatar(branch.id)
  const inherit = useInheritBranchAvatar(branch.id)

  const [size, setSize] = useState<number>(branch.avatar_size ?? AVATAR_DEFAULT_SIZE)
  const [position, setPosition] = useState<AvatarPosition>(
    branch.avatar_position ?? AVATAR_DEFAULT_POSITION,
  )
  const [shape, setShape] = useState<AvatarShape>(branch.avatar_shape ?? AVATAR_DEFAULT_SHAPE)

  // Reset draft when the dialog opens or the branch changes.
  useEffect(() => {
    if (!open) return
    setSize(branch.avatar_size ?? AVATAR_DEFAULT_SIZE)
    setPosition(branch.avatar_position ?? AVATAR_DEFAULT_POSITION)
    setShape(branch.avatar_shape ?? AVATAR_DEFAULT_SHAPE)
  }, [open, branch.id, branch.avatar_size, branch.avatar_position, branch.avatar_shape])

  const dirty = useMemo(() => {
    return (
      size !== (branch.avatar_size ?? AVATAR_DEFAULT_SIZE) ||
      position !== (branch.avatar_position ?? AVATAR_DEFAULT_POSITION) ||
      shape !== (branch.avatar_shape ?? AVATAR_DEFAULT_SHAPE)
    )
  }, [branch, size, position, shape])

  const saving = upload.isPending || remove.isPending || inherit.isPending

  function handlePick() {
    fileInputRef.current?.click()
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // allow same-file re-pick
    if (!file) return
    try {
      await upload.mutateAsync(file)
    } catch {
      // surfaced via upload.error
    }
  }

  async function handleDelete() {
    await remove.mutateAsync()
  }

  async function handleInherit() {
    try {
      await inherit.mutateAsync()
    } catch {
      // surfaced via inherit.error
    }
  }

  async function handleSave() {
    await onSave({
      avatar_size: size,
      avatar_position: position,
      avatar_shape: shape,
    })
    onClose()
  }

  const errorMessage =
    describeError(upload.error) ||
    describeError(remove.error) ||
    describeError(inherit.error)

  return (
    <Modal
      open={open}
      onClose={saving ? () => {} : onClose}
      title="头像设置"
      description="上传图片、调整尺寸/位置/形状;可从父级简历继承头像。"
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            取消
          </Button>
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={!dirty || !branch.avatar_url}
            loading={saving && dirty}
            data-testid="avatar-save"
          >
            保存
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ---- Preview ---- */}
        <div className="flex flex-col items-center gap-4">
          <div className="w-full aspect-square rounded-lg border border-dashed border-surface-border dark:border-dark-surface-border bg-surface-subtle dark:bg-dark-surface-subtle flex items-center justify-center overflow-hidden">
            {branch.avatar_url ? (
              <AvatarImage
                avatarUrl={branch.avatar_url}
                size={Math.min(220, size + 20)}
                shape={shape}
                position={position}
                className="!w-auto"
              />
            ) : (
              <div className="text-center px-4">
                <div className="text-2xs text-ink-3 mb-1">尚未上传头像</div>
                <Button
                  size="sm"
                  leftIcon={<Upload className="h-3.5 w-3.5" />}
                  onClick={handlePick}
                  disabled={saving}
                  data-testid="avatar-pick-empty"
                >
                  上传图片
                </Button>
              </div>
            )}
          </div>

          {branch.avatar_url && (
            <div className="flex gap-2 w-full">
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Upload className="h-3.5 w-3.5" />}
                onClick={handlePick}
                disabled={saving}
                loading={upload.isPending}
                data-testid="avatar-replace"
                className="flex-1"
              >
                更换
              </Button>
              {branch.parent_id && (
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
                  onClick={handleInherit}
                  disabled={saving}
                  loading={inherit.isPending}
                  data-testid="avatar-inherit"
                  title="从父级简历继承头像"
                >
                  继承父级
                </Button>
              )}
              <Button
                variant="danger"
                size="sm"
                leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                onClick={handleDelete}
                disabled={saving}
                loading={remove.isPending}
                data-testid="avatar-delete"
                title="删除头像"
              >
                删除
              </Button>
            </div>
          )}

          {errorMessage && (
            <div
              className="w-full text-2xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded px-3 py-2"
              data-testid="avatar-error"
              role="alert"
            >
              {errorMessage}
            </div>
          )}
        </div>

        {/* ---- Controls ---- */}
        <div className="space-y-5">
          {/* Size */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-ink-2">尺寸</label>
              <span className="text-2xs text-ink-3 tabular-nums">{size} px</span>
            </div>
            <input
              type="range"
              min={AVATAR_SIZE_MIN}
              max={AVATAR_SIZE_MAX}
              step={2}
              value={size}
              onChange={(e) => setSize(Number(e.target.value))}
              disabled={!branch.avatar_url}
              className="w-full accent-brand-500"
              data-testid="avatar-size-slider"
            />
            <div className="flex justify-between text-2xs text-ink-3 mt-0.5">
              <span>{AVATAR_SIZE_MIN}</span>
              <span>{AVATAR_SIZE_MAX}</span>
            </div>
          </div>

          {/* Position */}
          <div>
            <label className="text-xs font-medium text-ink-2 block mb-1.5">位置</label>
            <div className="grid grid-cols-5 gap-1.5">
              {AVATAR_POSITIONS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPosition(p)}
                  disabled={!branch.avatar_url}
                  className={cn(
                    'py-2 text-2xs rounded border transition-colors',
                    position === p
                      ? 'bg-brand-500 text-white border-brand-500'
                      : 'bg-surface dark:bg-dark-surface text-ink-2 border-surface-border dark:border-dark-surface-border hover:bg-surface-muted',
                    !branch.avatar_url && 'opacity-50 cursor-not-allowed',
                  )}
                  data-testid={`avatar-position-${p}`}
                >
                  {POSITION_LABEL[p]}
                </button>
              ))}
            </div>
          </div>

          {/* Shape */}
          <div>
            <label className="text-xs font-medium text-ink-2 block mb-1.5">形状</label>
            <div className="grid grid-cols-3 gap-1.5">
              {AVATAR_SHAPES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setShape(s)}
                  disabled={!branch.avatar_url}
                  className={cn(
                    'py-2 text-2xs rounded border transition-colors flex items-center justify-center gap-1.5',
                    shape === s
                      ? 'bg-brand-500 text-white border-brand-500'
                      : 'bg-surface dark:bg-dark-surface text-ink-2 border-surface-border dark:border-dark-surface-border hover:bg-surface-muted',
                    !branch.avatar_url && 'opacity-50 cursor-not-allowed',
                  )}
                  data-testid={`avatar-shape-${s}`}
                >
                  <ShapeIcon shape={s} active={shape === s} />
                  {SHAPE_LABEL[s]}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={handleFile}
        data-testid="avatar-file-input"
      />
    </Modal>
  )
}

function ShapeIcon({ shape, active }: { shape: AvatarShape; active: boolean }) {
  const radius = shape === 'circle' ? 'rounded-full' : shape === 'rounded' ? 'rounded-sm' : 'rounded-none'
  return (
    <span
      className={cn(
        'inline-block h-3 w-3 border',
        radius,
        active ? 'border-white' : 'border-current',
      )}
    />
  )
}