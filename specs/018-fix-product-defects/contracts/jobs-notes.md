# Contract: Job Tracking Notes

**Spec refs**: FR-019 / FR-020 / SC-010
**Defect**: #12 求职记录备注未保存
**Decision**: R-004

---

## 根因

后端 `backend/app/modules/jobs/models.py:36` 字段是 **`notes_md`**（Text nullable）。前端用 `note` / `j.note` 字段名 → 后端 Pydantic `model_dump(exclude_none=True)` 不映射别名 → 静默丢弃。

**零 schema 变更**：只修前端字段映射。

---

## 字段名契约

```ts
// src/types/job.ts (统一字段名)
interface Job {
  id: UUID
  user_id: UUID
  company: string
  position: string
  jd_url: string | null
  branch_id: UUID | null
  status: 'applied' | 'interviewing' | 'offer' | 'rejected' | 'withdrawn'
  status_history: Array<{...}>
  last_status_changed_at: string  // ISO
  notes_md: string | null         // ← 字段名
  created_at: string
  updated_at: string
}

interface CreateJobInput {
  company: string
  position: string
  jd_url?: string | null
  branch_id?: UUID | null
  status?: string
  notes_md?: string | null        // ← 字段名
}

interface PatchJobInput {
  company?: string
  position?: string
  jd_url?: string | null
  branch_id?: UUID | null
  status?: string
  notes_md?: string | null        // ← 字段名
}
```

---

## 前端修改点

```ts
// src/api/jobs.ts
- send POST /jobs with { ...input, notes_md: input.notes_md ?? null }
- send PATCH /jobs/:id with { ...patch, notes_md: patch.notes_md ?? null }
- 读取 j.notes_md 渲染

// src/pages/Jobs.tsx
- 表单 state: notes_md 替代 note
- 列表列: j.notes_md 替代 j.note
- 编辑回填: notes_md 替代 note
- 提交: api.createJob({ ...form, notes_md: form.notes_md?.trim() || null })

// src/repositories/jobs.ts
- JobRepository.create({ ...payload, notes_md: payload.notes_md })
- JobRepository.patch(id, { ..., notes_md })
```

---

## UI 契约

```tsx
// src/pages/Jobs.tsx 添加职位表单
<form>
  <input name="company" required />
  <input name="position" required />
  <input name="jd_url" type="url" />
  <textarea
    name="notes_md"
    placeholder="备注（如：Codex E2E ... 测试投递记录）"
  />
  <Button type="submit">添加</Button>
</form>

// 列表「备注」列
<td>{job.notes_md || '—'}</td>
// 关键：只在 notes_md 真的为空字符串 / null / undefined 时显示「—」
// 不可因字段名错误而显示「—」
```

---

## 测试契约

### 单元（`src/api/__tests__/jobs.test.ts`）

```text
- 创建职位 with notes_md="X" → API 收到 { notes_md: "X" }
- 编辑职位 with notes_md="Y" → API 收到 { notes_md: "Y" }
- 创建职位 without notes_md → API 收到 { notes_md: null }
```

### 契约测试（`backend/tests/contract/test_jobs_notes_field.py`）

```text
- POST /jobs { notes_md: "X" } → DB 行 notes_md = "X"
- GET /jobs/:id 响应 { notes_md: "X" }
- POST /jobs { notes_md: "" } → 接受（空字符串）
- POST /jobs 不含 notes_md → notes_md = NULL
- PATCH /jobs/:id { notes_md: "Y" } → DB 更新
```

### E2E（`e2e/jobs/notes-roundtrip.spec.ts`）

```text
1. 登录 → 打开 Jobs 页
2. 点击「+ 添加职位」→ 填备注 "Codex E2E ... 测试投递记录" → 提交
3. 断言：列表「备注」列显示该文本（非「—」）
4. 点击该职位「编辑」→ 断言：备注字段回填
5. 不修改备注 → 保存 → 断言：列表中仍显示原备注
6. 修改备注为新值 → 保存 → 断言：列表更新
```

---

## 验收对应

- FR-019 ✓ 字段映射修复
- FR-020 ✓ 编辑回填
- SC-010 ✓ 100% 列表非「—」（除非真为空）
