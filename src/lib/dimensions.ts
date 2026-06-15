/**
 * 面试维度英文 key → 中文标签
 * 单一来源：同时被 InterviewReport 页面和 ReportCard 组件使用
 */
export const DIMENSION_LABELS: Record<string, string> = {
  tech_depth: '技术深度',
  architecture: '架构能力',
  engineering_practice: '工程实践',
  communication: '沟通表达',
  algorithm: '算法思维',
  business_understanding: '业务理解',
}

/** 未命中映射时回退到 key 本身（不显示 "undefined"） */
export function dimensionLabel(key: string): string {
  return DIMENSION_LABELS[key] ?? key
}
