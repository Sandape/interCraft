/**
 * Bidirectional conversion between resume blocks and Markdown.
 *
 * Blocks → Markdown: aggregate all block contents into a single .md document
 * Markdown → Blocks: parse .md into structured blocks for Quick Mode editing
 */
import type { ResumeBlock, ResumeBranch, BlockType } from '@/modules/resume/api/types'

export interface ParsedBlock {
  type: BlockType
  title: string | null
  content_md: string
  meta: Record<string, unknown> | null
}

const BLOCK_TYPE_LABELS: { type: BlockType; labels: string[] }[] = [
  // Order matters: more specific patterns checked first.
  // "项目经历" contains "经历" so must check project before experience.
  { type: 'heading', labels: ['简历标题', 'heading', '标题'] },
  { type: 'project', labels: ['项目经历', '项目', 'projects', 'project'] },
  { type: 'experience', labels: ['工作经历', '实习经历', '经历', 'experience', '工作'] },
  { type: 'education', labels: ['教育背景', '教育', 'education', '学历'] },
  { type: 'skill', labels: ['技能', 'skills', 'skill', '技术栈'] },
  { type: 'summary', labels: ['个人简介', '简介', 'summary', '关于', 'about'] },
]

function detectBlockType(heading: string): BlockType {
  const lower = heading.toLowerCase()
  for (const entry of BLOCK_TYPE_LABELS) {
    if (entry.labels.some((l) => lower.includes(l.toLowerCase()))) {
      return entry.type
    }
  }
  return 'custom'
}

function extractMetaFromHeading(heading: string): { title: string | null; meta: Record<string, unknown> | null } {
  // Parse "## 工作经历 — 字节跳动" → title=工作经历, meta.company=字节跳动
  const dashParts = heading.split(/[—–—]/)
  if (dashParts.length < 2) return { title: heading.trim() || null, meta: null }

  const baseTitle = dashParts[0].trim() || null
  const after = dashParts.slice(1).join('—').trim()

  // Simple heuristic: if after part looks like a company name
  return { title: baseTitle, meta: { company: after } }
}

// ── Blocks → Markdown ──────────────────────────────────────────

export function blocksToMarkdown(
  branch: { name: string; company?: string | null; position?: string | null },
  blocks: ResumeBlock[],
): string {
  const lines: string[] = []

  // Resume heading block
  const headingBlock = blocks.find((b) => b.type === 'heading')
  if (headingBlock) {
    lines.push(`# ${headingBlock.title || branch.name}`)
    if (branch.company || branch.position) {
      const contactInfo = [branch.position, branch.company].filter(Boolean).join(' · ')
      lines.push('')
      lines.push(contactInfo)
    }
    lines.push('')
  } else {
    lines.push(`# ${branch.name}`)
    lines.push('')
  }

  // Non-heading blocks
  const contentBlocks = blocks.filter((b) => b.type !== 'heading')

  const typeLabelMap = new Map(
    BLOCK_TYPE_LABELS.map((e) => [e.type, e.labels[0]]),
  )

  for (const block of contentBlocks) {
    const typeLabel = typeLabelMap.get(block.type) ?? block.type
    let heading = `## ${typeLabel}`
    if (block.title) heading += ` — ${block.title}`

    lines.push(heading)
    lines.push('')

    // Write frontmatter-style metadata
    if (block.meta && Object.keys(block.meta).length > 0) {
      lines.push('---')
      for (const [k, v] of Object.entries(block.meta)) {
        if (v != null) lines.push(`${k}: ${String(v)}`)
      }
      lines.push('---')
      lines.push('')
    }

    lines.push(block.content_md)
    lines.push('')
  }

  return lines.join('\n').trim() + '\n'
}

// ── Markdown → Blocks ──────────────────────────────────────────

export function markdownToBlocks(markdown: string): ParsedBlock[] {
  const blocks: ParsedBlock[] = []
  const lines = markdown.split('\n')

  let currentBlock: { type: BlockType; title: string | null; content: string[]; meta: Record<string, unknown> | null } | null = null
  let inFrontmatter = false
  let frontmatterLines: string[] = []

  function flushBlock() {
    if (!currentBlock) return
    blocks.push({
      type: currentBlock.type,
      title: currentBlock.title,
      content_md: currentBlock.content.join('\n').trim(),
      meta: currentBlock.meta,
    })
    currentBlock = null
  }

  function parseFrontmatter(): Record<string, unknown> | null {
    if (frontmatterLines.length === 0) return null
    const meta: Record<string, unknown> = {}
    for (const line of frontmatterLines) {
      const colonIdx = line.indexOf(':')
      if (colonIdx > 0) {
        const key = line.slice(0, colonIdx).trim()
        const value = line.slice(colonIdx + 1).trim()
        if (key && value) meta[key] = value
      }
    }
    return Object.keys(meta).length > 0 ? meta : null
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // H1 → heading block
    if (/^#\s/.test(line) && !/^##\s/.test(line)) {
      flushBlock()
      const title = line.replace(/^#\s+/, '').trim()
      currentBlock = { type: 'heading', title: title || null, content: [], meta: null }
      continue
    }

    // H2 → new block boundary
    if (/^##\s/.test(line)) {
      flushBlock()
      const headingText = line.replace(/^##\s+/, '').trim()
      const { title, meta } = extractMetaFromHeading(headingText)
      const blockType = detectBlockType(headingText)
      currentBlock = { type: blockType, title, content: [], meta: meta as Record<string, unknown> | null }
      frontmatterLines = []
      inFrontmatter = false
      continue
    }

    // Frontmatter detection
    if (currentBlock && line.trim() === '---' && !inFrontmatter) {
      inFrontmatter = true
      frontmatterLines = []
      continue
    }
    if (currentBlock && line.trim() === '---' && inFrontmatter) {
      currentBlock.meta = parseFrontmatter()
      inFrontmatter = false
      continue
    }

    // Inside frontmatter
    if (currentBlock && inFrontmatter) {
      frontmatterLines.push(line)
      continue
    }

    // Regular content
    if (currentBlock) {
      currentBlock.content.push(line)
    }
  }

  flushBlock()
  return blocks
}
