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

interface MarkdownEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
  /** Callback for auto-save after user stops typing (debounced externally) */
  onAutoSave?: (value: string) => void
  className?: string
}

export default function MarkdownEditor({
  value,
  onChange,
  readOnly = false,
  onAutoSave,
  className = '',
}: MarkdownEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleMount: OnMount = useCallback((editor) => {
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
  }, [])

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
