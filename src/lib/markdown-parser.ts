/**
 * Markdown import parser — validates .md files, reads content,
 * parses into blocks via markdownToBlocks, maps to CreateBlockInput.
 */
import { markdownToBlocks } from './markdown-converter'
import type { CreateBlockInput } from '@/api/types'

const MAX_FILE_SIZE = 100 * 1024 // 100KB

export interface ImportResult {
  blocks: CreateBlockInput[]
  suggestedName: string
  warnings: string[]
}

export interface ImportError {
  code: 'INVALID_TYPE' | 'FILE_TOO_LARGE' | 'EMPTY_FILE' | 'PARSE_FAILED'
  message: string
}

function sanitizeFilename(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_').replace(/\.md$/i, '')
}

export async function readMarkdownFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(new Error('Failed to read file'))
    reader.readAsText(file, 'UTF-8')
  })
}

export function validateMarkdownFile(file: File): ImportError | null {
  if (!file.name.toLowerCase().endsWith('.md')) {
    return { code: 'INVALID_TYPE', message: '请选择 Markdown (.md) 文件' }
  }
  if (file.size > MAX_FILE_SIZE) {
    return { code: 'FILE_TOO_LARGE', message: '文件大小超过 100KB 限制' }
  }
  if (file.size === 0) {
    return { code: 'EMPTY_FILE', message: '文件内容为空，无法导入' }
  }
  return null
}

export function parseMarkdownImport(
  markdown: string,
  filename: string,
): ImportResult {
  const warnings: string[] = []

  if (!markdown.trim()) {
    throw { code: 'EMPTY_FILE', message: '文件内容为空，无法导入' } as ImportError
  }

  let parsed
  try {
    parsed = markdownToBlocks(markdown)
  } catch {
    throw { code: 'PARSE_FAILED', message: 'Markdown 解析失败，请检查文件格式' } as ImportError
  }

  if (!parsed || parsed.length === 0) {
    throw { code: 'PARSE_FAILED', message: '未能从文件中识别出任何简历模块' } as ImportError
  }

  // Detect if any blocks ended up as 'custom' due to unrecognized headings
  const customBlocks = parsed.filter((b) => b.type === 'custom')
  if (customBlocks.length > 0) {
    warnings.push(
      `${customBlocks.length} 个模块无法精确映射类型，已保留为自定义模块。支持的模块类型：简历标题、个人简介、工作经历、项目经历、教育背景、技能`,
    )
  }

  // Suggest branch name from first heading or filename
  const headingBlock = parsed.find((b) => b.type === 'heading')
  const suggestedName = headingBlock?.title || sanitizeFilename(filename)

  // Map ParsedBlock[] to CreateBlockInput[]
  const blocks: CreateBlockInput[] = parsed.map((b, idx) => ({
    type: b.type,
    title: b.title,
    content_md: b.content_md,
    meta: b.meta ?? undefined,
  }))

  return { blocks, suggestedName, warnings }
}
