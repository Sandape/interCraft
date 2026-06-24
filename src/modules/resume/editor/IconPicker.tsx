/**
 * IconPicker — modal grid of 14 brand icons for `icon:<name>` syntax.
 * US4 T065 / US6 FR-046.
 *
 * Click an icon → calls `onInsert('icon:<name> ')` which inserts at cursor
 * in the Monaco editor.
 */
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import svgMap, { ICON_NAMES, type IconName } from '@/modules/resume/renderer/icons/svg-map'

interface IconPickerProps {
  open: boolean
  onClose: () => void
  onInsert: (syntax: string) => void
}

const ICON_LABELS: Record<IconName, string> = {
  github: 'GitHub',
  email: 'Email',
  blog: '博客',
  weixin: '微信',
  juejin: '掘金',
  zhihu: '知乎',
  weibo: '微博',
  qq: 'QQ',
  twitter: 'Twitter',
  facebook: 'Facebook',
  csdn: 'CSDN',
  yuque: '语雀',
  sifou: '思否',
  phone: '电话',
}

export default function IconPicker({ open, onClose, onInsert }: IconPickerProps) {
  function handlePick(name: IconName) {
    onInsert(`icon:${name} `)
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="选择图标"
      description="点击插入 `icon:<name>` 语法到光标位置"
      size="md"
      footer={
        <Button variant="ghost" onClick={onClose}>
          关闭
        </Button>
      }
    >
      <div
        className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-7 gap-2"
        data-testid="icon-picker-grid"
      >
        {ICON_NAMES.map((name) => (
          <button
            key={name}
            onClick={() => handlePick(name)}
            title={ICON_LABELS[name]}
            data-testid={`icon-picker-${name}`}
            className="flex flex-col items-center justify-center gap-1 p-2 rounded-md border border-surface-border dark:border-dark-surface-border hover:bg-surface-muted dark:hover:bg-dark-surface-muted hover:border-brand-300 dark:hover:border-brand-500/50 transition-colors"
          >
            <span
              className="w-4 h-4 flex items-center justify-center text-ink-1"
              dangerouslySetInnerHTML={{ __html: svgMap[name] }}
            />
            <span className="text-2xs text-ink-3">{ICON_LABELS[name]}</span>
          </button>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-surface-border dark:border-dark-surface-border">
        <p className="text-2xs text-ink-3">
          共 {ICON_NAMES.length} 个图标，语法示例：
          <code className="ml-1 px-1 py-0.5 bg-surface-muted dark:bg-dark-surface-muted rounded">
            icon:github
          </code>
        </p>
      </div>
    </Modal>
  )
}
