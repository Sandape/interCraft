# Data Model: Resume Center Muji Alignment

**Feature**: 027-resume-center-muji-alignment
**Date**: 2026-06-24 (updated 2026-06-24 for US8/US9)

## 实体变更概览

| 实体 | 变更 | 说明 |
|---|---|---|
| `resume_branches` | 新增 6 列 | `theme_id` + `accent_color`（US3）;`avatar_url` + `avatar_size` + `avatar_position` + `avatar_shape`（US9, 4 列新增） |
| `resume_versions` | 启用现有字段 | `diff_patch` + `base_version_id` 已存在但未实现，本 feature 启用 |
| `LocalHistoryEntry` | 新增（localStorage） | 8 条 FIFO 编辑历史，前端独有 |
| `AIOptimizePatch` | 扩展 | 新增 `accepted` 字段（用户逐项接受/拒绝） |
| `ResumeTheme` | 新增（资源） | 主题 CSS 文件 + 元数据，非数据库实体 |
| `ResumeUIPreference` | 新增（localStorage） | mode + splitRatio + scrollPos，前端独有 |
| `RenderedBlock` | 运行时结构（US8） | 渲染后 DOM 节点携带 `data-block-id` 属性，建立 block↔预览节点映射 |
| `AvatarBlob` | 资源（US9） | 上传后压缩的图片二进制，存对象存储，返回 URL |

---

## 数据库实体

### ResumeBranch（扩展 — US3 + US9）

表 `resume_branches`，新增 6 列：

```python
# backend/app/modules/resumes/models.py
class ResumeBranch(...):
    # ... 现有字段保留 ...
    # US3 主题与颜色
    theme_id: Mapped[str] = mapped_column(String(32), default="default", nullable=False)
    accent_color: Mapped[str] = mapped_column(String(7), default="#39393a", nullable=False)
    # US9 头像设置（4 列）
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)  # 头像图片 URL（NULL=无头像）
    avatar_size: Mapped[int] = mapped_column(Integer, default=120, nullable=False)  # 50-200px
    avatar_position: Mapped[str] = mapped_column(String(16), default="top", nullable=False)  # left/right/top/center/bottom
    avatar_shape: Mapped[str] = mapped_column(String(16), default="circle", nullable=False)  # circle/square/rounded
```

**US3 约束**:
- `theme_id` ∈ {'default', 'blue', 'orange', 'pupple'}（CHECK 约束）
- `accent_color` 匹配 `^#[0-9a-fA-F]{6}$`（CHECK 约束）

**US9 约束**:
- `avatar_url` 长度 ≤ 512，NULL 允许（无头像）
- `avatar_size` ∈ [50, 200]（CHECK 约束）
- `avatar_position` ∈ {'left', 'right', 'top', 'center', 'bottom'}（CHECK 约束）
- `avatar_shape` ∈ {'circle', 'square', 'rounded'}（CHECK 约束）
- 默认值：size=120, position=top, shape=circle（无 URL=不渲染头像）

**迁移**: Alembic `add_theme_and_avatar_to_resume_branch.py`，合并 US3 + US9 迁移（一次 schema 变更）。

### ResumeVersion（启用 diff_patch — US7）

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
- `restore_version(session, version_id)` — 支持从 diff 快照恢复
- AI 触发的版本仍写全量快照

### AIOptimizePatch（扩展 — US5）

```typescript
// src/api/types.ts
interface AIOptimizePatch {
  path: string           // 目标 block 的路径
  op: 'replace' | 'add' | 'remove'
  value: string          // 新值
  oldValue?: string      // 原值（前端填充用于 diff）
  block_id?: string      // US8 增强：block UUID，用于 per-patch 在预览中高亮
  accepted: boolean      // 用户是否接受
}
```

---

## 运行时结构（无数据库）

### RenderedBlock（US8 — 双向定位）

```typescript
// 运行时 DOM 属性，由 renderMarkdown 在每个 block 根元素上注入
// Markdown 源结构 → 渲染后 HTML
//
// ## 项目经验                  →  <h2 data-block-id="uuid-xxx">项目经验</h2>
// 项目内容...                    →  <p data-block-id="uuid-xxx">项目内容...</p>  // 部分 wrapper 共享
//
// 实际策略：heading-block 插件为每个 block 创建 <div class="h<N>_block block"
//          该 div 上设置 data-block-id
// Quick 模式 block click  →  document.querySelector(`[data-block-id="${id}"]`)?.scrollIntoView()
// Preview block click    →  e.currentTarget.dataset.blockId → 反查 Quick/Code 位置
```

**约束**:
- 每个 block 渲染时仅一个根节点带 `data-block-id`（即 heading-block 包装的 div 节点）
- Code 模式下 Monaco 通过 `block_id → md 行号`映射表定位光标（行号在 renderMarkdown 时计算并缓存到 block metadata）
- PDF 渲染器剥离 `data-block-id` 属性（后端 sanitize 步骤）

### AvatarBlob（US9 — 头像资源）

```typescript
// 上传时序：前端 → 后端 /upload/avatar → 对象存储（本地 backend/static/uploads/avatars/）→ 返回 URL
// 写入：resume_branches.avatar_url = url，avatar_size/position/shape 同步更新
// 删除：avatar_url 设为 NULL，但 avatar_size/position/shape 保留（用户偏好）
```

**约束**:
- 前端预检：文件类型 ∈ {png, jpg, webp}，文件大小 ≤ 2MB
- 后端校验：再次检查（防止绕过前端的请求）
- 服务端压缩：Pillow 压缩到 ≤ 500KB，quality=85
- 图片存储：本地 `backend/static/uploads/avatars/{user_id}/{branch_id}.{ext}`，开发环境用本地；生产用 S3/OSS（v2 阶段用本地即可）
- 头像 URL 失效时（图片被删），PDF 渲染跳过（不抛错），前端显示破图占位

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
- 每条 ≤ 100KB，超出跳过写入
- localStorage 配额满时静默失败

### ResumeUIPreference

```typescript
// src/lib/resume-ui-pref.ts
interface ResumeUIPreference {
  mode: 'quick' | 'code'
  splitRatio: number       // 20-80，默认 50
  scrollPos: number        // 预览区滚动位置（px）
}

// 存储：localStorage key `rs-ui-pref-{branchId}`
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
  isColorCustomizable: boolean
}
```

**资源**: `public/themes/{default,blue,orange,pupple}.css`，从木及搬运。
**加载**: 运行时 `fetch(cssUrl)` → 注入 `<style id="rs-themes-data">`。

---

## 实体关系图

```
ResumeBranch (1) ──< ResumeBlock (N)
   │                    │
   │                    ├── order_index (fractional indexing)
   │                    └── data-block-id (US8 渲染时属性，运行时)
   │
   ├──< ResumeVersion (N) ──< ResumeVersion (base, self-ref for diff)
   │       ├── is_full_snapshot=True → snapshot_json
   │       └── is_full_snapshot=False → diff_patch + base_version_id
   │
   ├── theme_id → ResumeTheme (资源)
   ├── accent_color → --bg CSS 变量
   ├── avatar_url → AvatarBlob (对象存储, US9)
   ├── avatar_size/position/shape → 内联 style (US9)
   │
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

### 双向定位状态（US8）

```
idle
  ↓ 用户点击 Quick block / Code 行号 / Preview block
scrolling
  ↓ 平滑滚动到目标 + 1.5s 高亮动画
highlighting
  ↓ 动画结束
idle
  ↓ 期间再次点击
interrupted → 取消旧动画 → scrolling（新一轮）
```

### 头像设置状态（US9）

```
empty (无头像)
  ↓ 上传图片
uploading
  ↓ 成功
configured (avatar_url 存在 + size/position/shape 设置)
  ↓ 调整任一设置
adjusting (PATCH 持久化)
  ↓ 成功
configured
  ↓ 删除
empty (但 size/position/shape 偏好保留)
```

---

## 校验规则

- `theme_id` 必须在 `ResumeTheme` 注册表中（default/blue/orange/pupple）
- `accent_color` 必须匹配 `^#[0-9a-fA-F]{6}$`
- `avatar_size` ∈ [50, 200]
- `avatar_position` ∈ {left, right, top, center, bottom}
- `avatar_shape` ∈ {circle, square, rounded}
- 头像文件类型 ∈ {png, jpg, webp}，大小 ≤ 2MB（上传时）
- `LocalHistoryEntry.markdown` ≤ 100KB
- `ResumeUIPreference.splitRatio` ∈ [20, 80]
- `AIOptimizePatch.path` 格式 `blocks[N].field`，N 为有效 block 索引
- 版本 diff 对比的两个版本必须属于同一 branch

---

## 兼容性

- 旧数据（无 `theme_id` / `accent_color` / 头像字段）迁移后默认 `default` / `#39393a` / 无头像
- 旧的全量快照版本保持可用
- 现有 `style_preference` 字段保留
- localStorage 键名带 `branchId` 隔离
- US8 双向定位是新增能力，旧数据无影响（block_id 渲染时即时生成）
- US9 头像设置对旧数据无影响（默认无头像，旧 PDF 导出无头像）

