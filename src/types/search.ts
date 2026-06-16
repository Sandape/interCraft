/**
 * Global search response types — mirror backend/app/modules/search/schemas.py.
 */

export type SearchType = 'resume' | 'interview' | 'ability' | 'faq' | 'resource'

export interface SearchResultItem {
  id: string
  type: SearchType
  title: string
  subtitle: string | null
  destination: string
  score: number
  meta: Record<string, unknown>
}

export interface SearchGroup {
  type: SearchType
  label: string
  items: SearchResultItem[]
  total: number
}

export interface SearchResponse {
  groups: SearchGroup[]
  query: string
  took_ms: number
}

export type SearchRequestState = 'idle' | 'loading' | 'success' | 'error'
