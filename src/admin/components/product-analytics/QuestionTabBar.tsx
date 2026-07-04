/**
 * QuestionTabBar — REQ-044 US2 / FR-011.
 *
 * Renders the 7 question tabs (activation / funnel / retention /
 * adoption / journey / release / experiment) and notifies the parent
 * of the active tab via the ``activeTab`` callback. Tabs are rendered
 * as a horizontal bar; switching is in-page state (no navigation).
 */
import type { QuestionTab } from '@/types/admin-product-analytics'

interface QuestionTabBarProps {
  activeTab: QuestionTab
  onChange: (tab: QuestionTab) => void
}

const TAB_LABELS: Record<QuestionTab, string> = {
  activation: 'Activation',
  funnel: 'Funnel',
  retention: 'Retention',
  adoption: 'Adoption',
  journey: 'Journey',
  release: 'Release',
  experiment: 'Experiment',
}

const TABS: QuestionTab[] = [
  'activation',
  'funnel',
  'retention',
  'adoption',
  'journey',
  'release',
  'experiment',
]

export function QuestionTabBar({ activeTab, onChange }: QuestionTabBarProps) {
  return (
    <div
      className="ac-pa-tabs"
      data-testid="question-tab-bar"
      role="tablist"
      aria-label="Product analytics question tabs"
    >
      {TABS.map((tab) => {
        const isActive = tab === activeTab
        return (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={isActive}
            data-testid={`question-tab-${tab}`}
            data-active={isActive ? 'true' : 'false'}
            className={
              isActive
                ? 'ac-pa-tab ac-pa-tab--active'
                : 'ac-pa-tab'
            }
            onClick={() => onChange(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        )
      })}
    </div>
  )
}

export default QuestionTabBar