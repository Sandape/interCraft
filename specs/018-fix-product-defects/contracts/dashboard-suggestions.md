# Contract: Dashboard Suggestions（真实数据 + 三档渐进披露）

**Spec refs**: FR-003 / FR-004 / FR-005 / SC-011
**Defect**: #2 Dashboard 假数据
**Decision**: R-006

---

## 行为契约

### 档位规则（Q2 锁定）

| 档位 | 触发条件 | 渲染内容 |
|---|---|---|
| 0 | 无面试 / 无简历 / 无错题 / 无投递 | CTA: 「完成首场面试以获取建议」+ 跳转按钮 |
| 1 | ≥1 场面试 且 简历/错题/投递 三项中 <2 项 | 单场面试要点 + 关联简历提示（如本次失分维度） |
| 2 | ≥3 场面试 且 简历+错题+投递 齐全 | 全局综合建议（能力维度趋势 / 简历优化 / 错题强化） |

### 硬约束

- **任何档位下 MUST NOT 出现占位文案**：`"字节跳动简历分支"`、`"系统设计失分 3 次"`、`"+14"`、`"76% 复用"` 等字面量全部删除
- **任何档位下 MUST NOT 出现"全局"措辞**（仅档位 2 允许）
- 数据源全部走 `useAbilities()` + `useInterviewSessions()` + `useResumeBranches()` + `useJobs()` + `useErrorQuestions()`

### 选择器契约

```ts
// src/hooks/useDashboardSuggestions.ts （新增）
type Tier = 0 | 1 | 2
type Suggestions = {
  tier: Tier
  blocks: Array<
    | { kind: 'cta'; cta: { label: string; to: string } }
    | { kind: 'interview_focus'; sessionId: UUID; dim: string; branchTitle: string | null }
    | { kind: 'global'; abilities: AbilitySummary; resumeHints: string[]; errorHints: string[] }
  >
}
function useDashboardSuggestions(): Suggestions
```

### 组件契约

```tsx
// src/pages/Dashboard.tsx
const { tier, blocks } = useDashboardSuggestions()
// 渲染：blocks.map(b => <SuggestionBlock {...b} />)
// 不再硬编码任何 "AI 优化摘要" 卡片
```

### 数据流（避免硬编码）

```text
useAbilities()           → abilities.dimensions[].actual_score
useInterviewSessions()   → sessions.filter(s => s.status === 'completed')
useResumeBranches()      → branches
useErrorQuestions()      → errors
useJobs()                → jobs
                          ↓
                   档位选择器 (selector)
                          ↓
              tier + blocks (typed payload)
```

---

## 测试契约

### E2E（`e2e/dashboard/no-fake-suggestions.spec.ts`）

```text
- 新注册账号访问 /dashboard → 见到档位 0 CTA，无任何 "字节跳动"/"系统设计"/"+14" 文案
- 完成 1 场面试后访问 /dashboard → 见到档位 1 提示，内容引用该场面试真实信息
- 完成 3 场面试 + 简历 + 错题 + 投递齐全 → 见到档位 2 全局建议
```

### 单元测试（`src/pages/__tests__/Dashboard.test.tsx`）

```text
- 三个 fixture 覆盖档位 0/1/2
- 断言：不出现 "字节跳动"/"系统设计"/"失分 N 次" 等字面量
- 断言：档位 0 渲染 CTA；档位 1 不渲染 "全局" 措辞；档位 2 至少包含 2 类 hint
```

---

## 验收对应

- FR-003 ✓ 无占位
- FR-004 ✓ 档位 0/1/2 渐进式
- FR-005 ✓ 数据源可注入（hooks）
- SC-011 ✓ 三档可测量
