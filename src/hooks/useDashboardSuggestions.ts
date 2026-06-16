/** 018 #2 — Dashboard progressive disclosure selector.

  Computes a tier (0/1/2) from upstream query data and returns tier-
  appropriate suggestion blocks. No fake numbers, no fake company names;
  every block is grounded in real data the user owns.
*/

import { useMemo } from 'react'
import type { DashboardSuggestions, SuggestionBlock, Tier } from '@/types/dashboard'
import { useResumeBranches } from '@/hooks/queries/useResumeBranches'
import { useErrorQuestions } from '@/hooks/queries/useErrorQuestions'
import { useJobs } from '@/hooks/queries/useJobs'
import { useInterviewSessions } from '@/hooks/queries/useInterviewSessions'

function count<T>(arr: T[] | undefined | null): number {
  return Array.isArray(arr) ? arr.length : 0
}

function completedInterviewCount(sessionsData: unknown): number {
  const sessions = (sessionsData as any)?.data
  if (!Array.isArray(sessions)) return 0
  return sessions.filter((s: any) => s.status === 'completed').length
}

export function useDashboardSuggestions(): DashboardSuggestions {
  const { data: branches = [] } = useResumeBranches()
  const { data: errorQsData } = useErrorQuestions({ limit: 50 })
  const { data: jobsData } = useJobs({ limit: 50 })
  const { data: sessionsData } = useInterviewSessions({ limit: 50 })

  return useMemo<DashboardSuggestions>(() => {
    const errorQs = count((errorQsData as any)?.data ?? errorQsData)
    const jobs = count((jobsData as any)?.data)
    const completedInterviews = completedInterviewCount(sessionsData)

    // Tier 0 — no completed interviews yet.
    if (completedInterviews === 0) {
      return {
        tier: 0,
        blocks: [
          {
            id: 'cta-first-interview',
            title: '完成首场模拟面试，获取能力画像',
            body: '我们会在你完成模拟面试后生成能力维度评分与个性化建议。',
            cta: { label: '开始模拟面试', href: '/interview/new' },
            tier: 0,
          },
        ],
      }
    }

    // Tier 1 — at least one completed interview but data still thin.
    const tier1Blocks: SuggestionBlock[] = []

    const latest = ((sessionsData as any)?.data ?? [])
      .filter((s: any) => s.status === 'completed')
      .sort((a: any, b: any) => {
        const ad = new Date(a.ended_at ?? a.created_at ?? 0).getTime()
        const bd = new Date(b.ended_at ?? b.created_at ?? 0).getTime()
        return bd - ad
      })[0] as { company?: string | null; position?: string | null; overall_score?: number | null } | undefined

    if (latest && (latest.company || latest.position)) {
      const label = [latest.company, latest.position].filter(Boolean).join(' · ')
      tier1Blocks.push({
        id: 'recap-latest-interview',
        title: `你最近的一场面试：${label}`,
        body:
          typeof latest.overall_score === 'number'
            ? `综合评分 ${latest.overall_score.toFixed(1)} / 10，建议先复盘薄弱维度。`
            : '复盘该场面试的表现，针对性巩固薄弱环节。',
        cta: { label: '查看面试报告', href: '/interview' },
        tier: 1,
      })
    }

    if (count(branches) === 0) {
      tier1Blocks.push({
        id: 'cta-create-resume',
        title: '关联一份简历，让模拟面试更贴合目标岗位',
        body: '绑定简历分支后，面试官会基于你的真实经历出题与打分。',
        cta: { label: '前往简历中心', href: '/resume' },
        tier: 1,
      })
    }

    if (errorQs === 0) {
      tier1Blocks.push({
        id: 'cta-add-error-question',
        title: '记录一道错题，开启错题本',
        body: '错题本会按维度聚合你的薄弱点，并据此生成强化训练计划。',
        cta: { label: '去错题本', href: '/error-book' },
        tier: 1,
      })
    }

    if (jobs === 0) {
      tier1Blocks.push({
        id: 'cta-add-job',
        title: '记录一个求职目标',
        body: '添加目标岗位后，可在面试前回顾该岗位的招聘需求。',
        cta: { label: '去求职记录', href: '/jobs' },
        tier: 1,
      })
    }

    if (tier1Blocks.length > 0) {
      return { tier: 1, blocks: tier1Blocks }
    }

    // Tier 2 — completed interviews + resume + errors + jobs all present.
    return {
      tier: 2,
      blocks: [
        {
          id: 'global-ability-trend',
          title: '能力趋势稳定，可考虑纵向挑战',
          body: `已完成 ${completedInterviews} 场模拟面试，建议继续在最近一场中得分较低的维度继续投入。`,
          cta: { label: '查看能力画像', href: '/ability-profile' },
          tier: 2,
        },
        {
          id: 'global-resume-refine',
          title: '简历仍有优化空间',
          body: `当前已有 ${count(branches)} 份简历分支，建议挑一份最常投递的版本做一次完整回顾。`,
          cta: { label: '打开简历中心', href: '/resume' },
          tier: 2,
        },
        {
          id: 'global-error-coach',
          title: '错题强化训练待启动',
          body: `错题本已收录 ${errorQs} 道题，定期启动强化可避免重复失分。`,
          cta: { label: '开始强化', href: '/error-book' },
          tier: 2,
        },
      ],
    }
  }, [branches, errorQsData, jobsData, sessionsData])
}

/** Convenience: just the tier. */
export function useDashboardTier(): Tier {
  return useDashboardSuggestions().tier
}