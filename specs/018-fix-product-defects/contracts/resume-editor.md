# Contract: Resume Editor (新建可编辑 + 空态不假 AI)

**Spec refs**: FR-006 / FR-007 / FR-010 / SC-001
**Defects**: #3 新建简历只读 / #4 空简历假 AI 摘要
**Decisions**: R-005 / R-014

---

## 行为契约

### A. 新建简历可编辑（缺陷 #3）

```text
Given  用户点击 "新建简历" 按钮，提交 position/branch
When   POST /resume-branches 返回 201 + branchId
Then   前端立即 useLock('resume_branch', branchId).acquire()
And    跳转到 /resume/:branchId
And    编辑器 isReadOnly = false
And    "+ 添加块" 入口可见且可点击
And    代码模式 textarea 可输入
```

### B. 只读原因显式化（FR-007）

```text
Given  编辑器 isReadOnly = true
When   用户查看编辑器
Then   顶部显示可读原因：以下之一
       - 「当前用户未持有该简历的写权限」
       - 「网络异常，无法申请锁（点击重试）」
       - 「简历被其他设备编辑中」
And    永远不显示裸 "只读" 文字
```

### C. 空简历不假 AI 摘要（缺陷 #4 / FR-010）

```text
Given  resume_branch.blocks.length === 0
When   用户查看 AIOptimizePanel
Then   渲染空态：「添加简历块以获取 AI 优化建议」+ 跳转「去添加块」按钮
And    不调用 POST /agents/resume-optimize
And    不显示 "LCP 1.4s" / "76% 复用" / "+14" / "当前 86" 等字面量
```

---

## 锁协议

```ts
// src/lib/lock/useLock.ts (已存在，本特性强化时序)
- acquire() → POST /locks { entity_type: 'resume_branch', entity_id: branchId }
- isOwner() → 当前用户持有该 entity 的锁
- release() → DELETE /locks
- 后端 isReadOnly = !isOwner (已在 Phase 3 实现)
```

### 关键时序（修复后）

```text
新建分支
  → POST /resume-branches (201)
  → POST /locks (acquire, 200)
  → navigate('/resume/:id')
  → ResumeEditor 挂载
  → GET /resume-branches/:id 拿到 isReadOnly = false
```

---

## 测试契约

### E2E（`tests/e2e/018-fix-product-defects/resume/new-resume-editable.spec.ts`）

```text
1. 登录 → 点击 "新建简历" → 填写标题 → 提交
2. 跳转后断言：编辑器不在只读态
3. 断言：可见 "+ 添加块" 入口
4. 点击 "+ 添加块" → 断言块创建成功
5. 切到代码模式 → 断言 textarea 可输入
```

### E2E（`tests/e2e/018-fix-product-defects/resume/empty-resume-no-fake-ai.spec.ts`）

```text
1. 登录 → 新建空简历 → 进入编辑器
2. 断言：AIOptimizePanel 显示空态，不含 "LCP" / "76%" / "+14" 等字面量
```

### 单元（`src/components/resume/__tests__/AiOptimizePanel.test.tsx`）

```text
- 传入 blocks=[] → 渲染空态，不调用 optimize API
- 传入 blocks=[1 个] → 渲染优化摘要面板
```

---

## 验收对应

- FR-006 ✓ 新建默认可写
- FR-007 ✓ 只读原因可读
- FR-010 ✓ 空态不假数据
- SC-001 ✓ 100% 新建可编辑
