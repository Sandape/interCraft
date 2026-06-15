import { useState, useRef, useCallback } from 'react'
import MarkdownEditor from './MarkdownEditor'
import ResumePreview from './ResumePreview'

interface WysiwygEditorProps {
  markdown: string
  onChange: (value: string) => void
  styleId?: string
  readOnly?: boolean
  onAutoSave?: (value: string) => void
}

export default function WysiwygEditor({
  markdown,
  onChange,
  styleId,
  readOnly = false,
  onAutoSave,
}: WysiwygEditorProps) {
  const [splitRatio, setSplitRatio] = useState(50)
  const containerRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)

  const handleMouseDown = useCallback(() => {
    dragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      const pct = Math.max(20, Math.min(80, (x / rect.width) * 100))
      setSplitRatio(pct)
    }

    const handleMouseUp = () => {
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [])

  return (
    <div
      ref={containerRef}
      className="flex h-full"
      data-testid="wysiwyg-editor"
    >
      {/* Left: Markdown Editor */}
      <div className="overflow-hidden" style={{ width: `${splitRatio}%` }}>
        <MarkdownEditor
          value={markdown}
          onChange={onChange}
          readOnly={readOnly}
          onAutoSave={onAutoSave}
        />
      </div>

      {/* Drag handle */}
      <div
        onMouseDown={handleMouseDown}
        className="w-2 cursor-col-resize bg-surface-border dark:bg-dark-surface-border hover:bg-brand-500/30 transition-colors flex-shrink-0"
        data-testid="split-handle"
      />

      {/* Right: Resume Preview */}
      <div className="overflow-hidden flex-1" style={{ width: `${100 - splitRatio}%` }}>
        <ResumePreview markdown={markdown} styleId={styleId} />
      </div>
    </div>
  )
}
