# Contract: Interview Scoring（量纲 + 简历关联 + 中文恢复 + 能力同步）

**Spec refs**: FR-011 / FR-012 / FR-013 / FR-014 / FR-015 / SC-004 / SC-005
**Defects**: #6 面试未关联简历 / #7 面试恢复英文 / #8 0-10 vs 0-100 / #9 能力画像未更新
**Decisions**: R-007 / R-008 / R-009 / R-002

---

## A. 量纲统一 0-10（缺陷 #8 / FR-013）

```text
全应用统一规则：
  - 面试报告总分       → "X.X / 10"，"满分 10"
  - 能力画像维度分     → "X.X / 10"
  - Dashboard 综合能力 → "X.X / 10"
禁止规则：
  - 任何位置禁止出现 "X / 100" 形式
  - 不做 0-100 换算
```

**修改点**：
- `src/pages/InterviewReport.tsx` — 报告卡 `total / 10` + "满分 10"
- `src/pages/AbilityProfile.tsx` — 维度分 `actual_score / 10`
- `src/pages/Dashboard.tsx` — 综合能力卡 `value / 10`（不再 0-100）

---

## B. 面试启动关联简历（缺陷 #6 / FR-011）

### 表单契约

```tsx
// src/pages/InterviewLive.tsx setup phase
<form onSubmit={startInterview}>
  <input name="position" required />
  <input name="company" required />
  <Select
    name="branch_id"
    label="使用简历（可跳过）"
    options={branches.map(b => ({ value: b.id, label: b.title }))}
    placeholder="不关联简历"
    clearable
  />
  <Button type="submit">开始面试</Button>
</form>
```

### 提交契约

```ts
// src/api/interviews.ts
async function startInterview(input: {
  position: string
  company: string
  branch_id: UUID | null  // 新增
  job_id?: UUID            // 可选，与 job 关联
}) {
  return POST('/interview-sessions', input)
}
```

**后端**：`POST /interview-sessions` 接受 `branch_id`（已存在 schema）。

### 无简历引导

```text
Given useResumeBranches() 返回空数组
When 打开面试 setup 表单
Then 「使用简历」控件禁用，提示「暂无可用简历，是否先创建？」
And 跳转按钮 → /resume/new
```

---

## C. 恢复中文文案（缺陷 #7 / FR-012）

```ts
// src/pages/InterviewLive.tsx:549 替换
// 旧:  `Restored ${n} answers, ${m} questions, ${k} scores.`
// 新:  `已恢复 ${n} 道回答，${m} 道题目，${k} 个评分`
- 文案存 src/lib/i18n/zh-CN.ts:interview.restore
- 不在前端 console 或页面正文泄露内部日志
```

---

## D. 能力画像同步（缺陷 #9 / FR-015）— 唯一后端改动

### 后端实现

```python
# backend/app/modules/interviews/service.py
# 在 complete_session() 末尾（参考其现有方法）追加：
async def _sync_ability_dimensions(self, session_id: UUID, user_id: UUID) -> None:
    """Aggregate this session's per-dimension mean score and patch ability_dimensions."""
    from app.modules.ability_profile.repository import AbilityProfileRepository
    from app.modules.abilities.repository import AbilityDimensionRepository
    from app.modules.abilities.schemas import ALLOWED_DIMENSION_KEYS
    from decimal import Decimal

    # 1. 聚合该 session 每 dim 的题均分（0-10）
    rows = await self.repo.session.execute(
        text("""
            SELECT q.dimension_key, AVG(s.score)::numeric(4,2) AS mean_score
            FROM interview_questions q
            JOIN interview_scores s ON s.question_id = q.id
            WHERE q.session_id = :session_id
            GROUP BY q.dimension_key
        """),
        {"session_id": session_id},
    )
    for dimension_key, mean_score in rows:
        if dimension_key not in ALLOWED_DIMENSION_KEYS:
            continue
        ability_repo = AbilityDimensionRepository(self.repo.session)
        await ability_repo.patch(user_id, dimension_key, {
            "actual_score": Decimal(str(mean_score)),
            "source": "interview",
        })
    # commit 由 complete_session 的现有事务负责
```

### 触发点

```text
complete_session() →
  ... 现有评分汇总 / 报告生成 ...
  → await self._sync_ability_dimensions(session.id, user_id)  # 新增
  → commit
```

### 写入不变量

- `actual_score` ∈ [0.00, 10.00]（与 Q1 一致）
- `source = "interview"`，与 `self_assess` 的 `"manual"` / Coach 的 `"coach"` 区分
- 维度不在 `ALLOWED_DIMENSION_KEYS` 白名单 → 跳过（防御）

---

## 测试契约

### E2E（`e2e/interview/setup-resume-pick.spec.ts`）

```text
- 有 1 份简历 → 打开面试 setup → 「使用简历」下拉列出该简历 → 提交带 branch_id
- 无简历 → 打开面试 setup → 控件禁用 + 看到「暂无可用简历」
```

### E2E（`e2e/interview/restore-zh-text.spec.ts`）

```text
- 进行中面试 → 强制刷新 → 顶部显示「已恢复 N 道回答，...」无 "Restored"
```

### E2E（`e2e/interview/scoring-scale-0-10.spec.ts`）

```text
- 完成面试 → 报告卡显示 "X.X / 10" + "满分 10"
- 巡检 Dashboard / AbilityProfile：所有能力分显示 "X.X / 10"，无 "/ 100"
```

### E2E（`e2e/interview/ability-sync.spec.ts`）

```text
1. 登录 → 新建简历 → 启动面试 → 提交 5 道题答案
2. 完成后立即打开 /ability-profile
3. 断言：≥1 个维度 actual_score > 0
4. 断言：DB 行 ability_dimensions 存在 source='interview' 的新行
```

### 集成测试（`backend/tests/integration/test_interview_to_ability_sync.py`）

```text
1. 创建 user + branch + 5 题面试
2. 提交答案 → complete_session()
3. 断言：GET /ability-profile/dashboard 返回 dim 分数 > 0
4. 断言：DB 行 source='interview' 的 ability_dimensions 行数 == 题目涉及 dim 数
```

---

## 验收对应

- FR-011 ✓ 简历可关联
- FR-012 ✓ 中文文案
- FR-013 ✓ 0-10 统一
- FR-014 ✓ 满分 10 文案
- FR-015 ✓ 能力画像同步
- SC-004 ✓ 100% 能力分 > 0
- SC-005 ✓ 100% 无 0-100 表达
