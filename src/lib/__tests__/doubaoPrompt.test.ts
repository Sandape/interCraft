import { describe, expect, it } from 'vitest'
import { buildDoubaoPromptPayload } from '../doubaoPrompt'
import type { Job } from '@/repositories/JobRepository'
import type { ResumeV2ListItem } from '@/modules/resume/v2/api'
import type { InterviewPlan } from '@/repositories/interviewSessionRepo'

const rawJd = [
  '岗位职责：',
  '1. 负责 AI 产品从 0 到 1 的规划。',
  '2. 设计高质量 Prompt 工作流。',
  '3. 与算法、工程、运营协作落地。',
  '任职要求：必须理解大模型评测、用户增长和商业化指标。',
].join('\n')

const job: Job = {
  id: 'job-1',
  company: 'Acme AI',
  position: 'AI Product Manager',
  jd_url: null,
  branch_id: 'resume-1',
  status: 'interviewing',
  status_history: [],
  notes_md: null,
  base_location: 'Shanghai',
  requirements_md: rawJd,
  employment_type: 'full_time',
  salary_range_text: '30k-50k',
  headcount: 2,
  interview_time: null,
  created_at: '2026-07-07T00:00:00Z',
  updated_at: '2026-07-07T00:00:00Z',
}

const resume: ResumeV2ListItem = {
  id: 'resume-1',
  name: 'AI PM Resume',
  slug: 'ai-pm',
  tags: [],
  is_public: false,
  is_locked: false,
  version: 1,
  created_at: null,
  updated_at: null,
}

const plan: InterviewPlan = {
  target_company: 'Acme AI',
  target_position: 'AI Product Manager',
  job_requirements: 'AI product, prompt workflow, metrics',
  tech_stack: ['LLM', 'Prompt Engineering'],
  interview_difficulty: 'medium',
  focus_areas: [{ area: 'Prompt 设计能力', weight: 0.7, reason: 'JD 的核心工作流' }],
  suggested_questions: ['你如何评估一个 Prompt 工作流的质量？'],
  web_research_summary: 'No external search needed.',
  tips: ['持续追问评测指标、样本构造和上线后的效果复盘。'],
}

describe('buildDoubaoPromptPayload', () => {
  it('only keeps original JD, focus areas and suggested follow-up directions', () => {
    const payload = buildDoubaoPromptPayload(job, resume, plan)

    expect(payload.sections.map((section) => section.id)).toEqual(['job', 'focus', 'followups'])
    expect(payload.copyText).toContain(`## 原生 JD\n${rawJd}`)
    expect(payload.copyText).toContain('## 考察侧重点')
    expect(payload.copyText).toContain('Prompt 设计能力，权重 70%：JD 的核心工作流')
    expect(payload.copyText).toContain('## 建议追问方向')
    expect(payload.copyText).toContain('持续追问评测指标、样本构造和上线后的效果复盘。')
  })

  it('does not include removed prompt sections or image/blob references', () => {
    const payload = buildDoubaoPromptPayload(job, resume, plan)

    expect(payload.copyText).not.toContain('豆包角色指令')
    expect(payload.copyText).not.toContain('候选人简历上下文')
    expect(payload.copyText).not.toContain('InterCraft 面试计划')
    expect(payload.copyText).not.toContain('面试时间/题量')
    expect(payload.copyText).not.toContain('对话规则')
    expect(payload.copyText).not.toMatch(/blob:/i)
    expect(payload.copyText).not.toMatch(/image/i)
    expect(payload.copyText).not.toMatch(/doubao-card-image/i)
  })
})
