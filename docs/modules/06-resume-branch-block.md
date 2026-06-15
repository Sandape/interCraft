# M06 · 简历分支 & 块

> 状态: draft · 所属领域: C · 优先级: P0
> 引用原文档: §3.2 (resume_branches, resume_blocks), §6.1, §6.2

## 1. 需求摘要

落地简历的核心数据结构:树形分支(`resume_branches`)+ Notion 式块(`resume_blocks`),支持分支继承(浅拷贝 → 深拷贝)、块拖拽排序(字符串分数)、折叠/展开状态、JD 匹配度评分字段。本模块**只做 CRUD**,版本快照交给 M07,AI 优化交给 M16。

## 2. 验收标准

- [ ] `GET /api/v1/resume-branches` 列出当前用户所有分支(支持 `is_main / is_pinned` 过滤)
- [ ] `POST /api/v1/resume-branches` 新建分支,可指定 `parent_id`(浅拷贝继承)
- [ ] `POST /api/v1/resume-branches/{id}/refresh-from-parent` 重新拉取核心简历最新版本(深拷贝覆盖)
- [ ] `GET /api/v1/resume-branches/{id}/blocks` 块列表,按 `order_index` 升序
- [ ] `POST /api/v1/resume-branches/{id}/blocks` 新建块,自动计算 order_index
- [ ] `PATCH /api/v1/resume-blocks/{id}` 部分更新(标题 / 内容 / collapsed)
- [ ] `PATCH /api/v1/resume-blocks/{id}/reorder` 拖拽排序,接受 `prev_id / next_id`,后端计算新 order_index
- [ ] `DELETE /api/v1/resume-blocks/{id}` 软删除
- [ ] 浅拷贝优化:新建分支时仅 INSERT 一条 `resume_branches`,blocks 不复制;首次编辑某块时才 INSERT 该块到新分支(写时复制)
- [ ] 标记 submitted 时,触发 M10 的 `create_interview_prep_task`(参见 A12)

## 3. 依赖与被依赖关系

**强依赖**: M02(表)、M05(RLS 启用)
**弱依赖**: M07(版本管理)、M10(任务联动)、M12(悲观锁)
**被以下模块依赖**: M07(版本管理 sample)、M16(Resume Optimize Agent)、M21(导入导出)、M23(前端)
**外部依赖**: 无

## 4. 数据模型

**`resume_branches` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
parent_id UUID NULL FK(resume_branches.id)  -- 树形
name TEXT NOT NULL
company TEXT NULL
position TEXT NULL
status TEXT NOT NULL  -- draft / optimizing / ready / submitted / archived (A12 决议)
match_score NUMERIC(5,2) NULL  -- 0.00-100.00
is_main BOOL NOT NULL DEFAULT false
is_pinned BOOL NOT NULL DEFAULT false
last_edited_at TIMESTAMPTZ NOT NULL DEFAULT now()
created_at / updated_at / deleted_at  -- Mixin
```

**`resume_blocks` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin,允许 RLS)
branch_id UUID NOT NULL FK(resume_branches.id)
type TEXT NOT NULL  -- heading / summary / experience / project / skill / education
title TEXT NULL
content_md TEXT NOT NULL  -- Markdown 原文
content_html TEXT NULL  -- 派生缓存(可后台生成)
meta JSONB NULL  -- 自由扩展(如 experience 的公司/职位/起止)
order_index TEXT NOT NULL  -- 字符串分数(如 "a0", "a1", "a0V")
collapsed BOOL NOT NULL DEFAULT false  -- 不进版本快照
created_at / updated_at / deleted_at
```

**索引**:
- `resume_branches (user_id, is_main DESC, last_edited_at DESC)`
- `resume_blocks (branch_id, order_index)`

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/resume-branches` | 分支列表(过滤/排序) |
| POST | `/api/v1/resume-branches` | 新建(可继承 parent) |
| GET | `/api/v1/resume-branches/{id}` | 单分支详情 |
| PATCH | `/api/v1/resume-branches/{id}` | 部分更新(name, status, ...) |
| DELETE | `/api/v1/resume-branches/{id}` | 软删除 |
| POST | `/api/v1/resume-branches/{id}/refresh-from-parent` | 从父分支重拉(覆盖) |
| GET | `/api/v1/resume-branches/{id}/blocks` | 块列表 |
| POST | `/api/v1/resume-branches/{id}/blocks` | 新建块 |
| PATCH | `/api/v1/resume-blocks/{id}` | 部分更新 |
| PATCH | `/api/v1/resume-blocks/{id}/reorder` | 拖拽排序 |
| DELETE | `/api/v1/resume-blocks/{id}` | 软删除块 |

**WebSocket**: 无(锁状态由 M12 推送)
**工具**: 无(由 M14+M16 调用 `query_resume_blocks`)

## 6. 关键设计点

- **写时复制(COW)**:新建分支时不复制 blocks,通过 `is_inherited` 视图查父分支;首次编辑某块时执行 `INSERT INTO resume_blocks SELECT ... FROM resume_blocks WHERE branch_id=parent`
- **order_index 字符串分数**:fractional-indexing 算法(`fractional-indexing` 或自研),拖拽时计算 `prev.order_index < new < next.order_index`
- **content_html 派生缓存**:用户写 Markdown,后台异步渲染 HTML(后续 ARQ 任务,M06 阶段可同步渲染兜底)
- **block.type 与 meta 配对**:`experience` 的 meta 含 company/role/period;`skill` 的 meta 含 tags[];前端需统一 schema(可考虑 jsonschema 校验)
- **status 触发器**:`PATCH /resume-branches/{id}` 修改 status 为 `submitted` 时,调用 `TaskService.create_interview_prep_task(branch)`(应用层,见 A12)
- **悲观锁集成**(M12 接入): 编辑器开锁 + 心跳;本模块的 PATCH 路由需校验持锁,无锁返回 423

## 7. 待澄清

- **[A12]** status 枚举:本模块决议 `draft / optimizing / ready / submitted / archived`;触发器走应用层
- **[A13]** 表头隐含字段已落实
- **浅拷贝继承的 UI 表达**:前端需明确显示「继承自核心」标识(M23 协调)

## 8. 实现提示

- 文件: `backend/app/api/v1/resumes.py`、`backend/app/services/resume_service.py`、`backend/app/repositories/resume_repo.py`、`backend/app/domain/resumes.py`
- 复用: M02 的 BaseRepository、M03 的限流(`/blocks` 写入接口可加速率限)
- 与 mockData 关系:
  - `mockData.ts:19-102` `ResumeBranch` → 直接落地
  - `mockData.ts:105-166` `ResumeBlock` → 直接落地
  - 注意 `status: 'draft'|'optimizing'|'ready'|'submitted'` 与决议保持一致
  - `versionCount` 字段:M07 实现,本模块预留 read-only 列(或聚合视图)
