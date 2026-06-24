import { useState, useCallback, useEffect } from 'react'
import type { ResumeBlock, ResumeBranch } from '@/modules/resume/api/types'
import { blocksToMarkdown, markdownToBlocks } from '@/modules/resume/converter/markdown-converter'

export type EditorMode = 'quick' | 'code'

interface UseModeToggleOptions {
  branch: ResumeBranch | undefined
  blocks: ResumeBlock[]
  onBlocksChange: (blocks: ResumeBlock[]) => void
}

export function useModeToggle({ branch, blocks, onBlocksChange }: UseModeToggleOptions) {
  const [mode, setMode] = useState<EditorMode>('quick')
  const [markdownContent, setMarkdownContent] = useState('')
  const [pendingBlockSnapshot, setPendingBlockSnapshot] = useState<ResumeBlock[] | null>(null)

  // When switching TO code mode: aggregate blocks into a markdown document
  const switchToCode = useCallback(() => {
    if (!branch) return
    const md = blocksToMarkdown(
      { name: branch.name, company: branch.company, position: branch.position },
      blocks,
    )
    setMarkdownContent(md)
    // Snapshot current blocks so we can restore if needed
    setPendingBlockSnapshot(blocks)
    setMode('code')
  }, [branch, blocks])

  // When switching TO quick: parse markdown back into blocks
  const switchToQuick = useCallback(() => {
    const parsed = markdownToBlocks(markdownContent)
    // Map parsed blocks to existing ResumeBlock structure (preserving IDs where possible)
    const newBlocks: ResumeBlock[] = parsed.map((pb, i) => {
      const existing = pendingBlockSnapshot?.[i] ?? blocks[i]
      return {
        id: existing?.id ?? `new-${i}`,
        branch_id: branch?.id ?? '',
        type: pb.type,
        title: pb.title,
        content_md: pb.content_md,
        content_html: null,
        meta: pb.meta,
        order_index: String(i),
        collapsed: false,
        created_at: existing?.created_at ?? new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
    })
    onBlocksChange(newBlocks)
    setPendingBlockSnapshot(null)
    setMode('quick')
  }, [markdownContent, blocks, pendingBlockSnapshot, branch, onBlocksChange])

  const toggleMode = useCallback(() => {
    if (mode === 'quick') {
      switchToCode()
    } else {
      switchToQuick()
    }
  }, [mode, switchToCode, switchToQuick])

  // Update blocks reference when blocks change externally (e.g., after create/delete)
  useEffect(() => {
    // Only in quick mode — don't interfere with code mode
    if (mode === 'quick') {
      // Nothing needed; blocks reference is up to date
    }
  }, [mode])

  return {
    mode,
    setMode,
    markdownContent,
    setMarkdownContent,
    toggleMode,
    switchToCode,
    switchToQuick,
  }
}
