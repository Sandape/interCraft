/** AbilityRepository — 6-dimension ability profile (M09, US5). */
import { request } from '../api/client'
import { abilityDimensions as mockAbilities } from '../data/mockData'

export interface SubScore {
  actual: number
  ideal: number
}

export interface AbilityDimension {
  id: string
  dimension_key: string
  actual_score: number
  ideal_score: number
  sub_scores: Record<string, SubScore>
  is_active: boolean
  source: string
  last_updated_at: string
  created_at: string
  updated_at: string
}

export interface AbilityHistoryPoint {
  snapshot_date: string
  aggregate: string
  actual_score: number
  ideal_score: number
  dimension_key: string
}

export interface DimensionMeta {
  key: string
  label_zh: string
  label_en: string
  sub_keys: { key: string; label_zh: string }[]
}

const BASE = '/api/v1/ability-dimensions'

// ---- Abstract interface ----
export abstract class AbilityRepository {
  abstract list(isActive?: boolean): Promise<{ data: AbilityDimension[] }>
  abstract get(key: string): Promise<AbilityDimension>
  abstract patch(key: string, patch: Record<string, unknown>): Promise<AbilityDimension>
  abstract toggle(key: string, isActive: boolean): Promise<AbilityDimension>
  abstract history(dimensionKey?: string, aggregate?: 'month' | 'day', from?: string, to?: string, limit?: number): Promise<{ data: AbilityHistoryPoint[] }>
  abstract dimensionsMeta(): Promise<{ dimensions: DimensionMeta[] }>
}

// ---- HTTP implementation ----
export class HttpAbilityRepository extends AbilityRepository {
  async list(isActive?: boolean): Promise<{ data: AbilityDimension[] }> {
    const params = new URLSearchParams()
    if (isActive !== undefined) params.set('is_active', String(isActive))
    const qs = params.toString()
    return request<{ data: AbilityDimension[] }>('GET', `${BASE}${qs ? `?${qs}` : ''}`)
  }

  async get(key: string): Promise<AbilityDimension> {
    return request<AbilityDimension>('GET', `${BASE}/${key}`)
  }

  async patch(key: string, patch: Record<string, unknown>): Promise<AbilityDimension> {
    return request<AbilityDimension>('PATCH', `${BASE}/${key}`, patch)
  }

  async toggle(key: string, isActive: boolean): Promise<AbilityDimension> {
    return request<AbilityDimension>('POST', `${BASE}/${key}/toggle`, { is_active: isActive })
  }

  async history(dimensionKey?: string, aggregate: 'month' | 'day' = 'month', from?: string, to?: string, limit = 20): Promise<{ data: AbilityHistoryPoint[] }> {
    const params = new URLSearchParams({ aggregate, limit: String(limit) })
    if (dimensionKey) params.set('dimension_key', dimensionKey)
    if (from) params.set('from', from)
    if (to) params.set('to', to)
    return request<{ data: AbilityHistoryPoint[] }>('GET', `${BASE}/history?${params}`)
  }

  async dimensionsMeta(): Promise<{ dimensions: DimensionMeta[] }> {
    return request<{ dimensions: DimensionMeta[] }>('GET', `${BASE}/dimensions-meta`)
  }
}

// ---- Mock implementation ----
export class MockAbilityRepository extends AbilityRepository {
  async list(_isActive?: boolean): Promise<{ data: AbilityDimension[] }> {
    return { data: mockAbilities.map(toAbilityDimension) }
  }

  async get(key: string): Promise<AbilityDimension> {
    const found = mockAbilities.find((d: any) => d.dimensionKey === key || d.key === key)
    if (!found) throw new Error(`Dimension ${key} not found`)
    return toAbilityDimension(found)
  }

  async patch(key: string, patch: Record<string, unknown>): Promise<AbilityDimension> {
    const dim = await this.get(key)
    return { ...dim, ...patch, last_updated_at: new Date().toISOString() } as AbilityDimension
  }

  async toggle(key: string, isActive: boolean): Promise<AbilityDimension> {
    return this.patch(key, { is_active: isActive })
  }

  async history(_dimensionKey?: string, _aggregate: 'month' | 'day' = 'month', _from?: string, _to?: string, _limit = 20): Promise<{ data: AbilityHistoryPoint[] }> {
    return { data: [] }
  }

  async dimensionsMeta(): Promise<{ dimensions: DimensionMeta[] }> {
    const DIMENSION_LABELS: Record<string, { zh: string; en: string }> = {
      tech_depth: { zh: '技术深度', en: 'Technical Depth' },
      architecture: { zh: '架构能力', en: 'Architecture' },
      engineering_practice: { zh: '工程实践', en: 'Engineering Practice' },
      communication: { zh: '沟通表达', en: 'Communication' },
      algorithm: { zh: '算法能力', en: 'Algorithm' },
      business: { zh: '业务理解', en: 'Business Acumen' },
    }
    const SUB_KEY_LABELS: Record<string, Record<string, string>> = {
      tech_depth: { fundamentals: '基础知识', system_design: '系统设计', depth_specialty: '专精深度' },
      architecture: { decomposition: '模块拆解', tradeoffs: '方案权衡', scalability: '可扩展性' },
      engineering_practice: { code_quality: '代码质量', testing: '测试能力', observability: '可观测性' },
      communication: { clarity: '清晰度', structure: '结构化', conciseness: '简洁性' },
      algorithm: { data_structures: '数据结构', complexity: '复杂度分析', edge_cases: '边界处理' },
      business: { domain_knowledge: '行业知识', product_sense: '产品思维', user_empathy: '用户共情' },
    }
    return {
      dimensions: Object.entries(DIMENSION_LABELS).map(([key, labels]) => ({
        key,
        label_zh: labels.zh,
        label_en: labels.en,
        sub_keys: Object.entries(SUB_KEY_LABELS[key] || {}).map(([sk, sl]) => ({
          key: sk,
          label_zh: sl,
        })),
      })),
    }
  }
}

function toAbilityDimension(mock: any): AbilityDimension {
  return {
    id: mock.id || '00000000-0000-7000-8000-000000000000',
    dimension_key: mock.dimensionKey || mock.key || 'tech_depth',
    actual_score: mock.actual ?? mock.actualScore ?? 0,
    ideal_score: mock.ideal ?? mock.idealScore ?? 10,
    sub_scores: mock.subScores || mock.sub_scores || {},
    is_active: mock.isActive ?? mock.is_active ?? true,
    source: 'manual',
    last_updated_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}
