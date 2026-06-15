# Resume Versions Endpoints (M07)

> 简历版本快照 + 回滚。完整快照 + diff(JSON Patch RFC 6902)混合存储(plan DEC-4)。
> 跨端 parity 测试:后端 `jsonpatch` ↔ 前端 `fast-json-patch` 同一 fixture 输出一致。

## 共享类型

```ts
type ResumeVersionSummary = {
  id: string;
  branch_id: string;
  version_no: number;
  label: string | null;
  is_full_snapshot: boolean;
  trigger: "manual" | "auto" | "ai";
  author_type: "user" | "ai";
  actor_id: string | null;
  created_at: string;
}

type ResumeVersionDetail = ResumeVersionSummary & {
  // 自动还原后的完整内容(无论底层是 full snapshot 还是 diff 还原)
  snapshot: {
    branch: {
      id: string;
      name: string;
      company: string | null;
      position: string | null;
      status: "draft" | "optimizing" | "ready" | "submitted" | "archived";
    };
    blocks: Array<{
      id: string;
      type: ResumeBlock["type"];
      title: string | null;
      content_md: string;
      meta: Record<string, any> | null;
      order_index: string;
      // collapsed 不入快照(M07 §6)
    }>;
  };
  // diff 链信息(供调试,UI 不展示)
  _diff_chain?: {
    base_version_id: string;
    patches_applied: number;
  };
}

type CreateVersionInput = {
  label?: string;                    // 用户备注
  // is_full_snapshot: Phase 1 总是 true(手动保存 = 完整快照)
  // 自动化(30 分钟一次)的 diff 快照由 ARQ 任务创建
}

type RollbackResponse = {
  new_branch: ResumeBranch;          // 新创建的分支,继承目标版本内容
  new_branch_id: string;
}
```

---

## 1. `GET /api/v1/resume-branches/{branch_id}/versions`

**用途**:列出某分支所有版本(简略字段,不含 snapshot)。

**Auth**:Bearer access

**查询参数**:
| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `cursor` | string | - | 游标分页 |
| `limit` | int 1-100 | 20 | |
| `order_by` | enum | `-version_no` | `-version_no` / `-created_at` |

**响应 200**:
```json
{
  "data": [ /* ResumeVersionSummary[] */ ],
  "pagination": {
    "next_cursor": "opaque_or_null",
    "has_more": false
  }
}
```

**Phase 1 行为**:不返回 snapshot 字段(节省带宽)。前端要看 snapshot → 走 §3 单版本端点。

---

## 2. `POST /api/v1/resume-branches/{branch_id}/versions`

**用途**:手动保存一个完整快照版本。

**Auth**:Bearer access

**请求**:
```json
{
  "label": "投递字节前定稿"
}
```

**逻辑**:
1. 取当前分支的所有 blocks(完整)
2. 取当前 branch 字段
3. 构造 `snapshot_json`(参见 data-model §7)
4. 分配 `version_no = max(version_no) + 1`(单分支内递增,事务保证)
5. 插入 `resume_versions` 记录:`is_full_snapshot=true, snapshot_json=..., trigger=manual, author_type=user, actor_id=<user_id>`

**响应 201**:
```json
{
  "version": { /* ResumeVersionSummary */ }
}
```

**副作用**:
- 创建版本记录
- 不影响当前 blocks 内容(snapshot 是「历史」,编辑流继续)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | branch 不存在 |
| 422 | `validation.range` | label 长度 > 256 |

---

## 3. `GET /api/v1/resume-branches/{branch_id}/versions/{version_no}`

**用途**:取单版本详情,自动还原 snapshot(无论底层是 full snapshot 还是 diff 链)。

**Auth**:Bearer access

**响应 200**:
```json
{
  "version": { /* ResumeVersionDetail */ }
}
```

**还原算法**(M07 §6 伪代码):
```python
def restore(version_id) -> dict:
    v = get_version(version_id)
    if v.is_full_snapshot:
        return v.snapshot_json
    base = restore(v.base_version_id)  # 递归
    return jsonpatch.apply_patch(base, v.diff_patch)
```

**递归深度保护**:`MAX_RESTORE_DEPTH = 100`(超出说明数据腐败,返回 500 + `version.restore_depth_exceeded`)。

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.version_not_found` | version_no 不存在 |
| 500 | `version.restore_depth_exceeded` | diff 链超过 100 步 |

---

## 4. `POST /api/v1/resume-branches/{branch_id}/versions/{version_no}/rollback`

**用途**:回滚到指定版本 → **创建新分支**继承该版本内容(不破坏原分支)。

**Auth**:Bearer access

**请求**:
```json
{
  "name": "字节跳动 · 高级前端 · 回滚 v3"  // 可选,默认 "回滚自 {原分支名} @ v{version_no}"
}
```

**逻辑**:
1. 还原目标 version 的 snapshot
2. 创建新分支(`parent_id = 当前 branch.id`)
3. 批量插入 snapshot 中的 blocks 到新分支(`user_id` 设为当前 user)
4. 创建初始化版本(完整快照,label 标记为「回滚自 v{version_no}」)
5. 返回新分支

**响应 200**:
```json
{
  "new_branch": { /* ResumeBranch */ },
  "new_branch_id": "uuid"
}
```

**Edge case 行为**:
- **E7**(源版本已被删除):目标 `version_no` 不存在 → 404 `resume.version_not_found`(无需单独处理)
- **E4**(submitted 后回滚):允许,新分支继承 `status` 字段(若目标版本是 submitted,新分支也是 submitted)
- **跨分支回滚**:允许,新分支 `parent_id` 指向**当前分支**,不是原 version 的分支(M07 §6 决议)

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 404 | `resume.not_found` | branch 不存在 |
| 404 | `resume.version_not_found` | version_no 不存在 |
| 500 | `version.restore_depth_exceeded` | diff 链过深 |

---

## 5. ARQ 自动快照任务(Phase 1 占位,30 分钟一次)

**目的**:spec FR-012 「自动保存版本(>10 分钟未操作)」

**Phase 1 简化**:**不**启用 10 分钟未操作自动快照(避免增加 LLM / Diff 算法调用频次)。仅落 ARQ 任务框架:

```python
# backend/app/modules/versions/auto_snapshot.py
@worker_task
async def auto_snapshot_branch(ctx, branch_id: str) -> dict:
    """30 分钟一次 cron。Phase 1 仅占位,Phase 2 启用智能触发(10 分钟未操作)。"""
    # TODO(Phase 2): 检测 last_edited_at - last_version_created_at > 10 min
    # TODO(Phase 2): 计算当前 blocks 与最近 full snapshot 的 diff
    # TODO(Phase 2): 若 diff 为空,跳过
    # TODO(Phase 2): 写入 resume_versions(is_full_snapshot=false, diff_patch=...)
    return {"branch_id": branch_id, "skipped": True, "reason": "phase 1 placeholder"}
```

**Worker 注册**(`backend/app/workers/main.py`):
```python
class WorkerSettings:
    functions = [
        auto_snapshot_branch,
        # M04 月度配额重置(Phase 1 落任务,Phase 2 启用)
        # monthly_quota_reset,
    ]
    cron_jobs = [
        # Phase 1:每 30 分钟跑一次 auto_snapshot_branch
        # 实际:仅占位,Phase 2 替换为智能判断
    ]
```

**ARQ 启动**:`uv run arq app.workers.main.WorkerSettings`(本地)或 docker-compose `worker` 服务。

---

## 6. JSON Patch 端到端 parity(plan DEC-4 + 宪法 IV)

**测试**:`backend/tests/integration/test_jsonpatch_parity.py`

**fixture**:
- 同一组 base snapshot + 新 blocks
- 后端 `python-jsonpatch.make_patch(base, new)` → 期望 patch
- 前端 `fast-json-patch.compare(base, new)` → 期望 patch
- 两者必须深度相等(serialize 后 byte-equal)

**运行时**:
- 后端 `apply_patch` / `make_patch` → 来自 `jsonpatch` 库
- 前端 `applyPatch` / `compare` → 来自 `fast-json-patch` 库
- 算法标准 RFC 6902,两端实现都是该标准 reference implementation,理论上完全一致
- 实际项目中发现 fast-json-patch 默认按 object key 排序,需要测试覆盖

**Phase 1 测试**:
- 单测:后端 10 个 case
- 集成:跨端 5 个 case(同一 fixture 跑两端,写一个 `parity_report.md` 报告)

---

## 7. snapshot 字段剔除规则(M07 §6)

**进入 snapshot 的字段**:
- branch.name / company / position / status
- block.id / type / title / content_md / meta / order_index

**不进入**:
- block.collapsed(纯 UI 状态,M07 §6 决议)
- branch.is_main / is_pinned(分支关系属性,非内容)
- user_id / created_at / updated_at / deleted_at
- 任何密码 / 凭据相关字段
