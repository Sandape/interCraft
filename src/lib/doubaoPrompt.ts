import type { Job } from '@/repositories/JobRepository'
import type { InterviewPlan } from '@/repositories/interviewSessionRepo'
import type { ResumeV2ListItem } from '@/modules/resume/v2/api'

export interface DoubaoPromptSection {
  id: 'job' | 'focus' | 'followups'
  title: string
  content: string
}

export interface DoubaoPromptPayload {
  title: string
  subtitle: string
  sections: DoubaoPromptSection[]
  copyText: string
}

export interface DoubaoPromptOptions {
  questionCount?: number | null
  scheduledAt?: string | null
}

export function buildDoubaoPromptPayload(
  job: Job,
  _resume: ResumeV2ListItem,
  plan: InterviewPlan | null | undefined,
  _options: DoubaoPromptOptions = {},
): DoubaoPromptPayload {
  const originalJd = job.requirements_md?.trim() || '未登记原生 JD。请先在求职追踪中补充 requirements_md。'
  const sections: DoubaoPromptSection[] = [
    {
      id: 'job',
      title: '原生 JD',
      content: originalJd,
    },
    {
      id: 'focus',
      title: '考察侧重点',
      content: formatFocusAreas(plan),
    },
    {
      id: 'followups',
      title: '建议追问方向',
      content: formatFollowups(plan),
    },
  ]

  return {
    title: `${job.company} · ${job.position}`,
    subtitle: '复制到豆包后，按原生 JD、考察侧重点和追问方向开始定制模拟面试。',
    sections,
    copyText: sections.map((section) => `## ${section.title}\n${section.content}`).join('\n\n'),
  }
}

function formatFocusAreas(plan: InterviewPlan | null | undefined): string {
  const areas = plan?.focus_areas ?? []
  if (!areas.length) {
    return '1. 围绕原生 JD 中的核心职责、关键能力和成功标准展开。\n2. 优先核验候选人是否有与岗位要求直接相关的项目证据。\n3. 对业务理解、协作方式、结果指标和落地复盘进行交叉验证。'
  }

  return areas
    .map((area, index) => {
      const weight = typeof area.weight === 'number' ? `，权重 ${Math.round(area.weight * 100)}%` : ''
      const reason = area.reason ? `：${area.reason}` : ''
      return `${index + 1}. ${area.area}${weight}${reason}`
    })
    .join('\n')
}

function formatFollowups(plan: InterviewPlan | null | undefined): string {
  const tips = toNumberedList(plan?.tips)
  if (tips) return tips

  const questions = toNumberedList(plan?.suggested_questions)
  if (questions) return questions

  return '1. 先让候选人用一个真实项目说明自己如何匹配 JD 中最重要的职责。\n2. 对关键结论继续追问“为什么这样判断、如何验证、结果指标是什么”。\n3. 当回答停留在概念层时，要求补充具体场景、行动、数据和复盘。'
}

function toNumberedList(items: string[] | undefined): string {
  const clean = (items ?? []).map((item) => item.trim()).filter(Boolean)
  if (!clean.length) return ''
  return clean.map((item, index) => `${index + 1}. ${item}`).join('\n')
}
