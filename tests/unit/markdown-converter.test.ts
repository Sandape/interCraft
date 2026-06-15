import { describe, it, expect } from 'vitest'
import { blocksToMarkdown, markdownToBlocks } from '@/lib/markdown-converter'
import type { ResumeBlock } from '@/api/types'

const makeBlock = (overrides: Partial<ResumeBlock> = {}): ResumeBlock => ({
  id: overrides.id ?? 'block-1',
  branch_id: 'branch-1',
  type: overrides.type ?? 'custom',
  title: overrides.title ?? null,
  content_md: overrides.content_md ?? '',
  content_html: null,
  meta: overrides.meta ?? null,
  order_index: '1',
  collapsed: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})

const branch = { name: '张三的简历', company: '字节跳动', position: '高级前端工程师' }

describe('blocksToMarkdown', () => {
  it('converts a heading block to # title', () => {
    const blocks = [makeBlock({ type: 'heading', title: '张三' })]
    const result = blocksToMarkdown(branch, blocks)
    expect(result).toContain('# 张三')
  })

  it('includes contact info after heading', () => {
    const blocks = [makeBlock({ type: 'heading', title: '张三' })]
    const result = blocksToMarkdown(branch, blocks)
    expect(result).toContain('高级前端工程师 · 字节跳动')
  })

  it('uses branch name when no heading block exists', () => {
    const result = blocksToMarkdown(branch, [])
    expect(result).toContain('# 张三的简历')
  })

  it('converts summary blocks with ## 个人简介', () => {
    const blocks = [
      makeBlock({ type: 'heading', title: '张三' }),
      makeBlock({ type: 'summary', content_md: '资深前端工程师，5年经验。' }),
    ]
    const result = blocksToMarkdown(branch, blocks)
    expect(result).toContain('## 个人简介')
    expect(result).toContain('资深前端工程师，5年经验。')
  })

  it('includes frontmatter metadata for experience blocks', () => {
    const blocks = [
      makeBlock({
        type: 'experience',
        title: '字节跳动',
        content_md: '- 主导架构设计',
        meta: { company: '字节跳动', role: '高级前端工程师' },
      }),
    ]
    const result = blocksToMarkdown(branch, blocks)
    expect(result).toContain('---')
    expect(result).toContain('company: 字节跳动')
    expect(result).toContain('role: 高级前端工程师')
  })

  it('converts skill blocks with bullet list', () => {
    const blocks = [
      makeBlock({ type: 'skill', content_md: '- React\n- TypeScript\n- Python' }),
    ]
    const result = blocksToMarkdown(branch, blocks)
    expect(result).toContain('## 技能')
    expect(result).toContain('- React')
  })

  it('handles empty blocks gracefully', () => {
    const result = blocksToMarkdown(branch, [])
    expect(result).toBeTruthy()
    expect(typeof result).toBe('string')
  })
})

describe('markdownToBlocks', () => {
  it('parses heading from # title', () => {
    const md = '# 张三\n\n## 个人简介\n\n资深工程师。\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('heading')
    expect(blocks[0].title).toBe('张三')
    expect(blocks[1].type).toBe('summary')
    expect(blocks[1].content_md).toBe('资深工程师。')
  })

  it('detects experience block from heading text', () => {
    const md = '## 工作经历 — 字节跳动\n\n- 项目 A\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('experience')
    expect(blocks[0].content_md).toBe('- 项目 A')
  })

  it('detects skill block from heading text', () => {
    const md = '## 技能\n\n- React\n- TypeScript\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('skill')
    expect(blocks[0].content_md).toContain('- React')
  })

  it('detects education block from heading text', () => {
    const md = '## 教育背景\n\n北京大学\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('education')
  })

  it('detects project block from heading text', () => {
    const md = '## 项目经历 — MyProject\n\n项目描述\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('project')
  })

  it('falls back to custom for unknown headings', () => {
    const md = '## 其他信息\n\n一些内容\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('custom')
  })

  it('parses frontmatter metadata in blocks', () => {
    const md = [
      '## 工作经历 — 字节跳动',
      '',
      '---',
      'company: 字节跳动',
      'role: 高级前端工程师',
      '---',
      '',
      '工作内容描述',
    ].join('\n')
    const blocks = markdownToBlocks(md)
    expect(blocks[0].meta).toEqual({ company: '字节跳动', role: '高级前端工程师' })
  })

  it('handles empty markdown', () => {
    const blocks = markdownToBlocks('')
    expect(blocks).toHaveLength(0)
  })

  it('round-trips blocks through markdown conversion', () => {
    const original = [
      makeBlock({ type: 'heading', title: '张三' }),
      makeBlock({ type: 'summary', content_md: '简介内容' }),
      makeBlock({ type: 'skill', content_md: '- React\n- TypeScript' }),
    ]
    const md = blocksToMarkdown(branch, original)
    const parsed = markdownToBlocks(md)

    // Skip heading comparison (heading is handled specially)
    expect(parsed.filter((b) => b.type === 'summary')).toHaveLength(1)
    expect(parsed.filter((b) => b.type === 'skill')).toHaveLength(1)
    expect(parsed.find((b) => b.type === 'summary')?.content_md).toBe('简介内容')
    expect(parsed.find((b) => b.type === 'skill')?.content_md).toContain('- React')
  })
})
