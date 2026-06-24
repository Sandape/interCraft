/**
 * MarkdownToolbar — format toolbar above the Code mode Markdown editor.
 * Operates on the Monaco editor instance (US6 T088/T089).
 */
import { Bold, Italic, Heading1, Heading2, Heading3, List, Link, ImageIcon } from 'lucide-react'
import type { editor } from 'monaco-editor'
import * as monaco from 'monaco-editor'

interface MarkdownToolbarProps {
  editor: editor.IStandaloneCodeEditor | null
  onOpenIconPicker?: () => void
}

type ToolbarAction = {
  icon: typeof Bold
  label: string
  action: (ed: editor.IStandaloneCodeEditor) => void
}

function insertAtCursor(ed: editor.IStandaloneCodeEditor, text: string) {
  const selection = ed.getSelection()
  if (!selection) return
  ed.executeEdits('toolbar', [{ range: selection, text }])
  ed.focus()
}

function wrapText(ed: editor.IStandaloneCodeEditor, left: string, right: string) {
  const selection = ed.getSelection()
  if (!selection) return
  const model = ed.getModel()
  if (!model) return
  const selected = model.getValueInRange(selection)
  const wrapped = `${left}${selected}${right}`
  ed.executeEdits('toolbar', [{ range: selection, text: wrapped }])
  // Select the wrapped text
  ed.setSelection(
    new monaco.Selection(
      selection.startLineNumber,
      selection.startColumn,
      selection.endLineNumber,
      selection.endColumn + left.length + right.length,
    ),
  )
  ed.focus()
}

function insertAtLineStart(ed: editor.IStandaloneCodeEditor, prefix: string) {
  const selection = ed.getSelection()
  if (!selection) return
  const line = selection.startLineNumber
  ed.executeEdits('toolbar', [{ range: new monaco.Range(line, 1, line, 1), text: prefix }])
  ed.focus()
}

const ACTIONS: ToolbarAction[] = [
  { icon: Bold, label: '加粗 (Ctrl+B)', action: (ed) => wrapText(ed, '**', '**') },
  { icon: Italic, label: '斜体 (Ctrl+I)', action: (ed) => wrapText(ed, '*', '*') },
  { icon: Heading1, label: '标题 1', action: (ed) => insertAtLineStart(ed, '# ') },
  { icon: Heading2, label: '标题 2', action: (ed) => insertAtLineStart(ed, '## ') },
  { icon: Heading3, label: '标题 3', action: (ed) => insertAtLineStart(ed, '### ') },
  { icon: List, label: '无序列表', action: (ed) => insertAtLineStart(ed, '- ') },
  {
    icon: Link,
    label: '链接',
    action: (ed) => {
      const selection = ed.getSelection()
      if (!selection) return
      const model = ed.getModel()
      if (!model) return
      const selected = model.getValueInRange(selection)
      if (selected) {
        wrapText(ed, '[', '](url)')
      } else {
        insertAtCursor(ed, '[text](url)')
      }
    },
  },
]

export default function MarkdownToolbar({ editor, onOpenIconPicker }: MarkdownToolbarProps) {
  return (
    <div className="flex items-center gap-0.5 px-2 py-1 border-b border-surface-border dark:border-dark-surface-border bg-surface dark:bg-dark-surface">
      {ACTIONS.map((act) => {
        const Icon = act.icon
        return (
          <button
            key={act.label}
            title={act.label}
            onClick={() => editor && act.action(editor)}
            className="p-1 rounded hover:bg-surface-muted dark:hover:bg-dark-surface-muted text-ink-3 hover:text-ink-1 disabled:opacity-30"
            disabled={!editor}
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        )
      })}
      <div className="w-px h-4 mx-1 bg-surface-border dark:border-dark-surface-border" />
      <button
        title="插入图标"
        onClick={onOpenIconPicker}
        className="p-1 rounded hover:bg-surface-muted dark:hover:bg-dark-surface-muted text-ink-3 hover:text-ink-1"
      >
        <ImageIcon className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}
