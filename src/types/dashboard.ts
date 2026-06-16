/** Dashboard suggestion tier model — 018 #2 progressive disclosure.

  Three tiers reflect how much data the user has accumulated. The UI must
  not invent fake numbers or company names; blocks are rendered only from
  data returned by the upstream queries.
*/

export type Tier = 0 | 1 | 2

export interface SuggestionBlock {
  /** stable id used as React key + data-testid */
  id: string
  /** short title in Chinese */
  title: string
  /** 1-2 sentence body */
  body: string
  /** optional call-to-action */
  cta?: {
    label: string
    href: string
  }
  /** which tier renders this block */
  tier: Tier
}

export interface DashboardSuggestions {
  tier: Tier
  blocks: SuggestionBlock[]
}