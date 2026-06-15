import { describe, it, expect } from 'vitest'
import { markdownToBlocks } from '@/lib/markdown-converter'

describe('markdownToBlocks — import scenarios', () => {
  it('maps # heading to heading block', () => {
    const md = '# 测试简历\n\n## 个人简介\n\n一个测试。\n'
    const blocks = markdownToBlocks(md)
    const heading = blocks.find((b) => b.type === 'heading')
    expect(heading).toBeDefined()
    expect(heading!.title).toBe('测试简历')
  })

  it('maps ## 经历 to experience block', () => {
    const md = '## 经历 — 阿里\n\n- 项目 A\n- 项目 B\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('experience')
    expect(blocks[0].content_md).toContain('- 项目 A')
    expect(blocks[0].content_md).toContain('- 项目 B')
  })

  it('maps ## 教育 to education block', () => {
    const md = '## 教育\n\n清华大学\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('education')
  })

  it('maps ## 技能 to skill block with list items', () => {
    const md = '## 技能\n\n- React\n- TypeScript\n- Node.js\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('skill')
    expect(blocks[0].content_md).toContain('- React')
    expect(blocks[0].content_md).toContain('- TypeScript')
  })

  it('maps ## 项目 to project block', () => {
    const md = '## 项目经历 — MyApp\n\n一个全栈项目。\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('project')
  })

  it('maps unrecognized heading to custom block', () => {
    const md = '## 获奖情况\n\nACM 金牌\n'
    const blocks = markdownToBlocks(md)
    expect(blocks[0].type).toBe('custom')
  })

  it('handles multiple blocks in order', () => {
    const md = [
      '# 张三',
      '',
      '## 个人简介',
      '',
      '简介内容',
      '',
      '## 工作经历 — A公司',
      '',
      '- 做了 X',
      '',
      '## 技能',
      '',
      '- React',
      '',
      '## 教育',
      '',
      '北大',
    ].join('\n')
    const blocks = markdownToBlocks(md)
    const types = blocks.map((b) => b.type)
    expect(types).toEqual(['heading', 'summary', 'experience', 'skill', 'education'])
  })

  it('handles markdown without any headings', () => {
    const md = 'Just some text without headings.\nMore text.\n'
    const blocks = markdownToBlocks(md)
    expect(blocks).toHaveLength(0)
  })

  it('handles whitespace-only content', () => {
    const blocks = markdownToBlocks('   \n  \n  ')
    expect(blocks).toHaveLength(0)
  })
})
