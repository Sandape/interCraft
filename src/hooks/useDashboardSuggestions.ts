/** REQ-057 — thin adapter over dashboard-summary next_action.

  Kept for any residual imports; Dashboard itself reads summary directly.
*/
import { useMemo } from 'react'
import type { DashboardSuggestions } from '@/types/dashboard'
import { useDashboardSummary } from '@/hooks/queries/useDashboardSummary'

export function useDashboardSuggestions(): DashboardSuggestions {
  const { data } = useDashboardSummary()
  return useMemo<DashboardSuggestions>(() => {
    const na = data?.l1.next_action
    if (!na) {
      return { tier: 0, blocks: [] }
    }
    return {
      tier: na.tier,
      blocks: [
        {
          id: na.id,
          title: na.title_zh,
          body: na.body_zh,
          cta: { label: na.cta.label, href: na.cta.href },
          tier: na.tier,
        },
      ],
    }
  }, [data])
}
