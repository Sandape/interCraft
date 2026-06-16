import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'

const LABELS: Record<string, string> = {
  rejected: '已拒绝',
  withdrawn: '已撤回',
}

interface TerminalConfirmModalProps {
  open: boolean
  to: string
  company: string
  position: string
  onConfirm: () => void
  onCancel: () => void
  isPending: boolean
}

export function TerminalConfirmModal({
  open,
  to,
  company,
  position,
  onConfirm,
  onCancel,
  isPending,
}: TerminalConfirmModalProps) {
  const label = LABELS[to] ?? to
  return (
    <Modal open={open} onClose={onCancel} title={`确认标记为「${label}」？`} size="sm">
      <p className="text-sm text-ink-2">
        即将把 <span className="font-medium text-ink-1">{company}</span> ·{' '}
        <span className="font-medium text-ink-1">{position}</span> 标记为
        「{label}」状态。此操作不可撤销（仍可在状态菜单中重新调整）。
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={isPending}>
          取消
        </Button>
        <Button
          variant="primary"
          onClick={onConfirm}
          loading={isPending}
          data-testid="terminal-confirm-submit"
        >
          确认
        </Button>
      </div>
      <span data-testid="terminal-confirm-modal" className="hidden" />
    </Modal>
  )
}
