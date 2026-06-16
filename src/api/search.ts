/**
 * Search API client — typed wrapper around /api/v1/search.
 */
import { apiClient } from './client'
import type { SearchResponse } from '@/types/search'

export const searchApi = {
  search: (q: string, signal?: AbortSignal) =>
    apiClient.request<SearchResponse>({
      method: 'GET',
      path: '/api/v1/search',
      query: { q },
      signal,
    }),
}
