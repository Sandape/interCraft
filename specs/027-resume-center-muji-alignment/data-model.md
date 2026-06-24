# Data Model: Resume Center Muji Alignment

**Feature**: 027-resume-center-muji-alignment
**Date**: 2026-06-24

## 实体变更概览

| 实体 | 变更 | 说明 |
|---|---|---|
| `resume_branches` | 新增 2 列 | `theme_id` (VARCHAR 32) + `accent_color` (VARCHAR 7) |
| `resume_versions` | 启用现有字段 | `diff_patch` + `base_version_id` 已存在但未实现，本 feature 启用 |
| `LocalHistoryEntry` | 新增（localStorage） | 8 条 FIFO 编辑历史，前端独有 |
| `AIOptimizePatch` | 扩展 | 新增 `accepted` 字段（用户逐项接受/拒绝） |
| `ResumeTheme` | 新增（资源） | 主题 CSS 文件 + 元数据，非数据库实体 |
| `ResumeUIPreference` | 新增（localStorage） | mode + splitRatio + scrollPos，前端独有 |

---

## 数据库实体

### ResumeBranch（扩展）

表 `resume_branches`，新增 2 列：

```python
# backend/app/modules/resumes/models.py — 新增字段
class ResumeBranch(...):
    # ... 现有字段保留 ...
    theme_id: Mapped[str] = mapped_column(String(32), default="default", nullable=False)
    accent_color: Mapped[str] = mapped_column(String(7), default="#39393a", nullable=False)
```

**约束**:
- `theme_id` ∈ {'default', 'blue', 'orange', 'pupple'}（CHECK 约束，未来可扩展）
- `accent_color` 匹配 `^#[0-9a-fA-F]{6}$`（CHECK 约束）
- 默认值：`theme_id='default'`, `accent_color='#39393a'`（木及默认主题色）

**迁移**: Alembic `add_theme_to_resume_branch.py`，`ADD COLUMN ... DEFAULT ... NOT NULL`（旧数据自动填默认值）。

### ResumeVersion（启用 diff_patch）

表 `resume_versions`，现有字段已支持 diff，本 feature 实现 diff 快照写入：

```python
# backend/app/modules/versions/models.py — 现有字段（无 schema 变更）
class ResumeVersion(...):
    is_full_snapshot: Mapped[bool]  # True=全量, False=diff
    snapshot_json: Mapped[dict | None]  # 全量快照
    base_version_id: Mapped[str | None]  # diff 基线版本
    diff_patch: Mapped[dict | None]  # diff patch（JSONB）
```

**约束**（已存在）:
- `is_full_snapshot=True` ⇒ `snapshot_json` NOT NULL, `diff_patch` NULL, `base_version_id` NULL
- `is_full_snapshot=False` ⇒ `diff_patch` NOT NULL, `base_version_id` NOT NULL, `snapshot_json` NULL

**本 feature 实现**:
- `create_diff_snapshot(branch, base_version, current_blocks)` — 计算 diff 写入
- `restore_version(session, version_id)` — 支持从 diff 快照恢复（回放 diff on base）
- AI 触发的版本仍写全量快照（简化，diff 快照主要用于手动版本间存储优化）

### AIOptimizePatch（扩展）

前端类型扩展（`src/api/types.ts`）：

```typescript
interface AIOptimizePatch {
  path: string           // 目标 block 的路径，如 "blocks[2].content_md"
  op: 'replace' | 'add' | 'remove'
  value: string          // 新值
  oldValue?: string      // 原值（前端填充用于 diff 展示）
  accepted: boolean      // 用户是否接受（默认 false，新增字段）
}
```

---

## 前端实体（localStorage）

### LocalHistoryEntry

```typescript
// src/lib/local-history.ts
interface LocalHistoryEntry {
  markdown: string       // 完整 Markdown
  theme_id: string       // 主题标识
  accent_color: string   // 主题强调色 HEX
  timestamp: number      // epoch ms
}

// 存储：localStorage key `rs-history-{branchId}`
// 策略：FIFO，最多 8 条
// 写入时机：编辑停顿 2s 后（防抖）
```

**约束**:
- 最多 8 条，超出移除最旧（FIFO shift）
- 每条 ≤ 100KB（Markdown 限制），超出跳过写入
- localStorage 配额满时静默失败（不影响编辑主流程）

### ResumeUIPreference

```typescript
// src/lib/resume-ui-pref.ts
interface ResumeUIPreference {
  mode: 'quick' | 'code'
  splitRatio: number       // 20-80，默认 50
  scrollPos: number        // 预览区滚动位置（px）
}

// 存储：localStorage key `rs-ui-pref-{branchId}`
// 读取时机：编辑器挂载
// 写入时机：mode 切换 / splitRatio 拖拽结束 / scroll 停顿 500ms
```

---

## 资源实体（非数据库）

### ResumeTheme

```typescript
// src/lib/resume-themes/registry.ts
interface ResumeTheme {
  id: 'default' | 'blue' | 'orange' | 'pupple'
  name: string           // 中文显示名
  defaultColor: string   // 默认强调色 HEX
  cssUrl: string          // /themes/${id}.css
  isColorCustomizable: boolean  // 是否支持 color picker（default 主题是灰色，可改）
}
```

**资源**: `public/themes/{default,blue,orange,pupple}.css`，从木及搬运。

**加载**: 运行时 `fetch(cssUrl)` → 注入 `<style id="rs-themes-data">`。

**切换**: 替换 `<style>` innerHTML，设置 `document.body.style.setProperty('--bg', accent_color)`。

---

## 实体关系图

```
ResumeBranch (1) ──< ResumeBlock (N)
   │                    │
   │                    └── order_index (fractional indexing)
   │
   ├──< ResumeVersion (N) ──< ResumeVersion (base, self-ref for diff)
   │       │
   │       ├── is_full_snapshot=True → snapshot_json
   │       └── is_full_snapshot=False → diff_patch + base_version_id
   │
   ├── theme_id → ResumeTheme (资源)
   ├── accent_color → --bg CSS 变量
   └── localStorage:
       ├── rs-history-{id} → LocalHistoryEntry[8]
       └── rs-ui-pref-{id} → ResumeUIPreference
```

---

## 状态转换

### AI 优化状态机

```
idle
  ↓ start()
starting
  ↓ thread 创建
polling (轮询指数退避)
  ↓ status=waiting_interrupt
waiting_patches (显示 patch 列表，用户逐项勾选)
  ↓ applySelected()
applying
  ↓ 成功
done (新版本已创建)
  ↓ 或
timeout (60s 超时)
  ↓ 或
error (AI 失败)
  ↓ retry
polling
```

### Block DnD 状态

```
idle
  ↓ dragStart
dragging (本地顺序即时更新)
  ↓ dragEnd
syncing (PATCH reorder)
  ↓ 成功
idle
  ↓ 失败
retrying (最多 3 次)
  ↓ 仍失败
rollback (恢复原顺序) + 提示"同步失败"
```

---

## 校验规则

- `theme_id` 必须在 `ResumeTheme` 注册表中（default/blue/orange/pupple）
- `accent_color` 必须匹配 `^#[0-9a-fA-F]{6}$`
- `LocalHistoryEntry.markdown` ≤ 100KB
- `ResumeUIPreference.splitRatio` ∈ [20, 80]
- `AIOptimizePatch.path` 格式 `blocks[N].field`，N 为有效 block 索引
- 版本 diff 对比的两个版本必须属于同一 branch

---

## 兼容性

- 旧数据（无 `theme_id` / `accent_color`）迁移后默认 `default` / `#39393a`
- 旧的全量快照版本保持可用（`is_full_snapshot=True` 不变）
- 现有 `style_preference` 字段保留（与 `theme_id` 正交：style 决定布局，theme 决定视觉）
- localStorage 键名带 `branchId` 隔离，不同分支互不干扰
