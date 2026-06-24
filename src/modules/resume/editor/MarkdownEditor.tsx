import { useRef, useCallback, useEffect } from 'react'
import Editor, { loader, type OnMount } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import type { editor } from 'monaco-editor'

const monacoGlobal = globalThis as typeof globalThis & {
  MonacoEnvironment?: { getWorker: () => Worker }
}

monacoGlobal.MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
}

loader.config({ monaco })

function wrapSelection(ed: editor.ICodeEditor, wrapper: string) {
  const selection = ed.getSelection()
  if (!selection) return
  const model = ed.getModel()
  if (!model) return
  const text = model.getValueInRange(selection)
  if (!text) return
  const wrapped = `${wrapper}${text}${wrapper}`
  ed.executeEdits('keyboard-shortcut', [{ range: selection, text: wrapped }])
  // Select the wrapped text (including markers)
  ed.setSelection(
    new monaco.Selection(
      selection.startLineNumber,
      selection.startColumn,
      selection.endLineNumber,
      selection.endColumn + wrapper.length * 2,
    ),
  )
  ed.focus()
}

interface MarkdownEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
  onAutoSave?: (value: string) => void
  onSaveVersion?: () => void
  className?: string
}

export default function MarkdownEditor({
  value,
  onChange,
  readOnly = false,
  onAutoSave,
  onSaveVersion,
  className = '',
}: MarkdownEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleMount: OnMount = useCallback(
    (editor) => {
      editorRef.current = editor
      editor.updateOptions({
        wordWrap: 'on',
        minimap: { enabled: false },
        lineNumbers: 'off',
        folding: false,
        lineDecorationsWidth: 0,
        renderLineHighlight: 'none',
        scrollBeyondLastLine: false,
        fontSize: 14,
        fontFamily:
          "'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'SF Mono', Consolas, monospace",
        padding: { top: 16, bottom: 16 },
      })

      // Ctrl+S / Cmd+S — save version (US6 T090)
      editor.addAction({
        id: 'save-version',
        label: 'Save Version',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS],
        run: () => onSaveVersion?.(),
      })

      // Ctrl+B / Cmd+B — bold (US6 T090)
      editor.addAction({
        id: 'bold-text',
        label: 'Bold',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyB],
        run: (ed) => wrapSelection(ed, '**'),
      })

      // Ctrl+I / Cmd+I — italic (US6 T090)
      editor.addAction({
        id: 'italic-text',
        label: 'Italic',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyI],
        run: (ed) => wrapSelection(ed, '*'),
      })
    },
    [onSaveVersion],
  )

  const handleChange = useCallback(
    (newValue: string | undefined) => {
      const v = newValue ?? ''
      onChange(v)
      if (onAutoSave) {
        if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
        autoSaveTimerRef.current = setTimeout(() => onAutoSave(v), 1500)
      }
    },
    [onChange, onAutoSave],
  )

  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current)
    }
  }, [])

  return (
    <div className={`h-full w-full ${className}`}>
      <Editor
        height="100%"
        defaultLanguage="markdown"
        value={value}
        onChange={handleChange}
        onMount={handleMount}
        loading={<div className="text-sm text-ink-3 p-4">加载编辑器…</div>}
        options={{ readOnly }}
        theme="vs-light"
      />
    </div>
  )
}
