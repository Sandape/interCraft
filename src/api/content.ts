/**
 * Content API service — resources, FAQ, search.
 */
import { apiClient, withMock } from './client'

export interface ResourceItem {
  id: string
  title: string
  summary: string
  category: string
  tags: string[]
  content_type: string
  read_time_minutes: number | null
  sort_order: number
  created_at: string
}

export interface ResourceDetail extends ResourceItem {
  content: string
  video_url: string | null
  related_resources: { id: string; title: string }[]
}

export interface FaqItem {
  id: string
  question: string
  category: string
  sort_order: number
}

export interface FaqCategory {
  category: string
  label: string
  items: FaqItem[]
}

export interface FaqDetail {
  id: string
  question: string
  answer: string
  category: string
  sort_order: number
  created_at: string
}

export interface SearchResult {
  id: string
  title?: string
  question?: string
  category: string
  score: number
}

export interface SearchResponse {
  faq: SearchResult[]
  resources: SearchResult[]
}

const mockResourceItems: ResourceItem[] = [
  { id: '1', title: '技术面试准备指南', summary: '系统设计、算法、行为面试的全面准备方法', category: 'tech_prep', tags: ['系统设计', '算法'], content_type: 'article', read_time_minutes: 15, sort_order: 1, created_at: '2026-06-01T00:00:00Z' },
  { id: '2', title: '简历优化完全手册', summary: '从排版到内容，让你的简历脱颖而出', category: 'resume_guide', tags: ['简历', 'STAR'], content_type: 'article', read_time_minutes: 10, sort_order: 1, created_at: '2026-06-01T00:00:00Z' },
  { id: '3', title: '模拟面试最佳实践', summary: '如何最大化模拟面试的价值', category: 'interview_tips', tags: ['模拟面试'], content_type: 'article', read_time_minutes: 8, sort_order: 1, created_at: '2026-06-01T00:00:00Z' },
]

export const contentApi = {
  listResources: (params?: { category?: string; tag?: string; content_type?: string; limit?: number; offset?: number }) =>
    withMock(
      () => {
        const query = new URLSearchParams()
        if (params?.category) query.set('category', params.category)
        if (params?.tag) query.set('tag', params.tag)
        if (params?.content_type) query.set('content_type', params.content_type)
        if (params?.limit) query.set('limit', String(params.limit))
        if (params?.offset) query.set('offset', String(params.offset))
        const qs = query.toString()
        return apiClient.request<{ items: ResourceItem[]; total: number; limit: number; offset: number }>('GET', `/api/v1/resources${qs ? `?${qs}` : ''}`)
      },
      () => ({
        items: params?.category
          ? mockResourceItems.filter((r) => r.category === params.category)
          : mockResourceItems,
        total: mockResourceItems.length,
        limit: params?.limit ?? 20,
        offset: params?.offset ?? 0,
      }),
    )(),

  getResource: (id: string) =>
    withMock(
      () => apiClient.request<ResourceDetail>('GET', `/api/v1/resources/${id}`),
      () => ({
        ...mockResourceItems[0],
        content: '# 模拟内容\n\n这是开发模式的模拟资源内容。',
        video_url: null,
        related_resources: [],
      }) as unknown as ResourceDetail,
    )(),

  listFaq: (category?: string) =>
    withMock(
      () => {
        const qs = category ? `?category=${category}` : ''
        return apiClient.request<{ categories: FaqCategory[] }>('GET', `/api/v1/help/faq${qs}`)
      },
      () => ({
        categories: [
          {
            category: 'account',
            label: '账号相关',
            items: [
              { id: '1', question: '如何注销账号?', category: 'account', sort_order: 1 },
              { id: '2', question: '如何取消注销?', category: 'account', sort_order: 2 },
            ],
          },
          {
            category: 'interview',
            label: '面试相关',
            items: [
              { id: '3', question: '如何开始模拟面试?', category: 'interview', sort_order: 1 },
            ],
          },
        ],
      }),
    )(),

  getFaq: (id: string) =>
    withMock(
      () => apiClient.request<FaqDetail>('GET', `/api/v1/help/faq/${id}`),
      () => ({
        id, question: '如何注销账号?', answer: '前往 Settings → 安全 点击「注销账号」。',
        category: 'account', sort_order: 1, created_at: '2026-06-01T00:00:00Z',
      }),
    )(),

  search: (q: string, scope?: string) =>
    withMock(
      () => {
        const query = new URLSearchParams({ q })
        if (scope) query.set('scope', scope)
        return apiClient.request<SearchResponse>('GET', `/api/v1/help/search?${query.toString()}`)
      },
      () => ({ faq: [], resources: [] }),
    )(),
}
