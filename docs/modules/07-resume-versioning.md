# M07 · 简历版本管理

> 状态: draft · 所属领域: C · 优先级: P0
> 引用原文档: §3.2 (resume_versions), §6.3

## 1. 需求摘要

实现简历版本快照与回滚:手动「保存版本」、AI 优化后自动快照、每 30 分钟定时快照;重要版本存完整快照,自动版本存 diff(JSON Patch RFC 6902);任意版本可回滚 → 创建新分支指向该版本;每次快照记录作者 / 触发 / 时间。

## 2. 验收标准

- [ ] `POST /api/v1/resume-branches/{id}/versions` 手动保存(完整快照 + label)
- [ ] `GET /api/v1/resume-branches/{id}/versions` 列出所有版本(简略字段)
- [ ] `GET /api/v1/resume-branches/{id}/versions/{version_no}` 单版本详情(自动还原 diff)
- [ ] `POST /api/v1/resume-branches/{id}/versions/{version_no}/rollback` 回滚 → 创建新分支
- [ ] ARQ 定时任务:每 30 分钟自动快照所有活跃编辑中的分支
- [ ] 存储策略:手动 / AI / 每 10 次自动 → 完整;其他 → diff
- [ ] diff 还原:递归找最近完整版本 + 应用 patch 链
- [ ] 审计字段:`author_type` (user/ai), `trigger` (manual/auto/ai), `actor_id`

## 3. 依赖与被依赖关系

**强依赖**: M06(resume_blocks)、M03(ARQ Worker)
**弱依赖**: M16(AI 优化后自动 trigger)
**被以下模块依赖**: M16(snapshot 工具)、M21(导出)、M23(前端历史版本 UI)
**外部依赖**: `jsonpatch`(RFC 6902 库)

## 4. 数据模型

**`resume_versions` 表(基于 A9 修订后)**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
branch_id UUID NOT NULL FK(resume_branches.id)
version_no INT NOT NULL  -- 单分支内递增
label TEXT NULL  -- 用户自定义(如 "投递 A 公司前")
is_full_snapshot BOOL NOT NULL  -- A9 新增
snapshot_json JSONB NULL  -- is_full_snapshot=true 时填
base_version_id UUID NULL FK(resume_versions.id)  -- A9 新增
diff_patch JSONB NULL  -- A9 新增,RFC 6902 patch 数组
author_type TEXT NOT NULL  -- user / ai
actor_id UUID NULL  -- user_id 或 agent_run_id
trigger TEXT NOT NULL  -- manual / auto / ai
created_at  -- Mixin(immutable 不需 updated_at)
```

**约束**:
- 同一 branch 内 `(branch_id, version_no)` 唯一
- `is_full_snapshot=true → snapshot_json NOT NULL, diff_patch IS NULL`
- `is_full_snapshot=false → snapshot_json IS NULL, diff_patch NOT NULL, base_version_id NOT NULL`

**索引**:
- `(branch_id, version_no DESC)` 加速「最新版本」查询
- `(branch_id, is_full_snapshot DESC, version_no DESC)` 加速「最近 full snapshot」查询(diff 还原起点)

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/resume-branches/{id}/versions` | 版本列表(简略,不含 snapshot/diff) |
| POST | `/api/v1/resume-branches/{id}/versions` | 创建快照(默认 full) |
| GET | `/api/v1/resume-branches/{id}/versions/{version_no}` | 单版本(自动还原) |
| POST | `/api/v1/resume-branches/{id}/versions/{version_no}/rollback` | 回滚 → 创建新分支 |

**工具**(LangGraph,见 M14):
- `save_resume_version(branch_id, snapshot, version_label) → {version_id}` 供 M16 用

## 6. 关键设计点

- **完整快照触发**:① 用户手动 ② AI 生成后 ③ 每第 10 次自动 ④ 用户初始化分支
- **自动快照频率**:30 分钟,但仅在「分支被编辑过 + 上次快照超过 30 分钟」时触发
- **diff 还原算法**:
  ```python
  def restore(version):
      if version.is_full_snapshot:
          return version.snapshot_json
      base = restore(get(version.base_version_id))
      return apply_patch(base, version.diff_patch)
  ```
- **回滚语义**:不破坏当前编辑轨迹 → 创建新分支(`parent_id = original branch`,blocks 复制自目标版本)
- **空间优化**:连续 5 次自动版本无实质改动 → 跳过快照(diff 为空)
- **collapsed 状态不进快照**:`resume_blocks.collapsed` 在生成 snapshot 时被剔除(参见 §6.2)

## 7. 待澄清

- **[A9]** diff 字段已落实
- 「重要版本」的判定算法是否纳入 UI 提示用户:推荐 ① 后端自动 ② 前端可看到「这是一个重要版本」徽章

## 8. 实现提示

- 文件: `backend/app/api/v1/resume_versions.py`、`backend/app/services/resume_version_service.py`、`backend/app/workers/tasks/auto_snapshot.py`
- 复用: M03 ARQ;`jsonpatch` 库
- 与 mockData 关系: `mockData.ts` 有 `versionCount`,需从此模块返回(`GET /resume-branches` 联合查询版本数量)
