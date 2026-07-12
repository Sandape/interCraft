export const publicDemoData = {
  candidate: '示例候选人',
  targetRole: '产品经理',
  targetCompany: '星河科技',
  counts: {
    resumes: 3,
    interviews: 2,
    jobs: 4,
    mistakes: 14,
    dimensions: 6,
  },
  rootResume: {
    title: '根简历 · 职业素材库',
    summary: '5 年用户研究、增长实验与跨团队协作经验',
    signals: ['用户研究', '增长实验', '数据分析', '项目推进'],
  },
  job: {
    title: '高级产品经理',
    company: '星河科技',
    signals: ['B 端产品', '商业化', '数据驱动', '跨团队协同'],
  },
  derivedResume: {
    title: '星河科技 · 岗位定制简历',
    matchScore: 82,
    strengths: ['用户洞察与增长实验形成完整案例', '跨团队项目有明确结果指标'],
    gaps: ['B 端商业化经历证据不足', '缺少复杂项目决策过程'],
    suggestions: ['补充续费率提升的归因口径', '突出一次关键取舍及复盘'],
  },
  abilities: [
    { label: '产品判断', score: 8.1 },
    { label: '数据分析', score: 7.4 },
    { label: '协作推进', score: 8.3 },
    { label: '商业理解', score: 6.2 },
    { label: '表达沟通', score: 7.8 },
    { label: '复盘成长', score: 7.1 },
  ],
} as const
