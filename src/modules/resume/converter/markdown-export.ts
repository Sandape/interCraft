import { blocksToMarkdown } from '@/modules/resume/converter/markdown-converter'
import type { ResumeBlock, ResumeBranch } from '@/modules/resume/api/types'

export function generateMarkdownFilename(branch: ResumeBranch): string {
  const base = branch.name.replace(/[<>:"/\\|?*]/g, '_').trim() || 'resume'
  return `${base}.md`
}

export function downloadMarkdown(branch: ResumeBranch, blocks: ResumeBlock[]): void {
  const markdown = blocksToMarkdown(
    { name: branch.name, company: branch.company, position: branch.position },
    blocks,
  )
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = generateMarkdownFilename(branch)
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function downloadSourceMarkdown(markdown: string, filename: string): void {
  const safeFilename = filename.replace(/[<>:"/\\|?*]/g, '_').trim() || 'resume.md'
  const finalFilename = safeFilename.toLowerCase().endsWith('.md')
    ? safeFilename
    : `${safeFilename}.md`
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  downloadBlob(blob, finalFilename)
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
