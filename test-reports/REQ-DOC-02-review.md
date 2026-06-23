# 审查报告 REQ-DOC-02

## 第 1 次审查

### 判定：FAIL

文档与代码现状严重不一致：FR-011 Evidence/Notes 错误描述 selectinload 用途，且实际实现存在冗余查询；SC-002 可测量结果（P95）未实测且 spec "≤ 2 SQL" 阈值超标，应改 partial。

| # | 严重度 | 维度 | 位置 | 原因 | 修改建议 |
|---|--------|------|------|------|----------|
| 1 | 严重 | 后端文档准确性 / 代码冗余 | `specs/022-perf-observability-enhancement/requirements-status.md` FR-011 行（对应代码 `backend/app/modules/resumes/repository.py:33-38`） | Notes 称 "selectinload loads relationship data for serialization"，但 `list_branches` 流程（`api.py:50-70` list_branches → `_branch_out` → `ResumeBranchOut`）从不访问 `branch.versions` / `branch.blocks`：`_branch_out` 仅读标量字段（`branch.id` / `branch.name` / …），`ResumeBranchOut` schema 无 `versions` / `blocks` 字段（已 grep 确认），counts 完全来自 `get_counts_batch`。selectinload(versions)+selectinload(blocks) 加载的关系数据未被使用，是 2 条冗余查询。实际查询数 5 = 1(list) + 2(selectinload) + 2(batch COUNT)，若移除 selectinload 可降至 3 = 1 + 2(batch COUNT)。spec FR-011 只允许两种实现：聚合子查询（单次往返）或 "selectinload + 内存聚合"（selectinload 加载后用 `len()` 计数）。dev 实现是第三种冗余路径："selectinload + 独立 COUNT 查询"，不属于 spec 允许的任一方案。 | 二选一：(a) 移除 `list_for_user` 中的 `selectinload(versions)` + `selectinload(blocks)`，仅保留 `get_counts_batch`，查询数降为 3；(b) 保留 selectinload，改用 `len(branch.versions)` / `len(branch.blocks)` 在内存聚合，移除 `get_counts_batch`，查询数降为 3。两种方案都仍超 ≤ 2 阈值但更接近。同时修正 FR-011 Notes：删除 "selectinload loads relationship data for serialization" 这句错误描述，改写为准确反映所选方案的说明。 |
| 2 | 严重 | SC 状态判定一致性 | `specs/022-perf-observability-enhancement/requirements-status.md` SC-002 行 | SC-002 可测量结果 "P95 ≤ 300ms" 从未实测（dev 自述 "Exact P95 not benchmarked in CI"）。spec Independent Test 与 Acceptance Scenario 2 明确要求 "≤ 2 SQL"，实际 5 条。dev 标 done 仅以 "O(N)→O(1) 达成" 为由，但 P95 是 spec 的 measurable outcome，未实测即无法判定 done。对照 023 模板：FR-025 因 "Not directly verified by a unit test, but covered indirectly" 标 partial，SC-002 同属"未直接验证、仅间接证据"情形，应保持一致标 partial。 | SC-002 Status 由 `done` 改为 `partial`；Notes 保留现有透明披露（P95 未实测 + 5 > 2 SQL），但结论应反映"部分达成"。或补一次实际 P95 benchmark（10 分支 × 3 版本 × 5 块场景）写入 Evidence，达标后可保持 done。 |

---

### 已核实通过的项（无问题）

- **指标计数 18**：`backend/app/core/metrics.py` `__all__` 实际 18 项（12 existing HTTP/Auth/Resume/Lock/Outbox + 6 new 022 LLM-quota/Checkpointer/WS/ARQ）。任务 brief 写 19 系误算 import 行。18 ≥ 15 满足 FR-046，9 类覆盖满足 SC-005。dev 非显然决策 #1 正确。
- **FR-023 CONCURRENTLY 标 partial**：`backend/migrations/versions/0012_022_error_questions_compound_index.py` 确实用 `if_not_exists=True` 但无 `postgresql_concurrently=True`，Alembic auto-transaction 阻塞 CONCURRENTLY。partial 标记合理。dev 非显然决策 #3 正确。
- **commit 引用**：init commit `0282157` 存在（git log --all 确认）；023 commit `dcae326` 含 `backend/app/core/metrics.py | 42 +++`，commit message 明确 "core/metrics.py carries 022 metric definitions (llm_quota_*, ws_*, arq_jobs_*) … co-resident in the working tree and committed together to keep 023 self-contained"，dev 引文准确（仅用 … 省略中间段落）。REQ-MERGE-01 working-tree 状态准确：`llm_client.py` / `resumes/api.py` / `resumes/repository.py` / `App.tsx` / `vite.config.ts` 均 modified，`0012_022_error_questions_compound_index.py` + 4 个测试文件均 untracked（`??`）。dev 非显然决策 #4 正确。
- **4 个 log 注入点**：`llm_client.py` L205 / L222 / L235 / L275 实测确认 `_current_request_id()` 注入。
- **FR-004 ARQ on_job_start**：`backend/app/workers/main.py:31-35` `on_job_start` hook 用 `ctx["job_id"]` 绑定 request_id，与 dcae326 commit message "ARQ worker on_job_start hook for request_id traceability" 一致。
- **spec 条目完整性**：6 US + 31 FR + 7 SC 全部覆盖，无遗漏无多余。FR 编号连续（001-005 / 010-013 / 020-023 / 030-033 / 040-046 / 050-052 / 060-063），SC 编号 001-007。
- **测试文件**：4 个测试文件全部存在且有实质测试（`test_request_id_middleware.py` 3 cases / `test_llm_client_request_id.py` 4 cases / `test_metrics_collectors.py` 6 metric 定义断言 / `test_022_error_questions_index.py` 2 cases 含 EXPLAIN Index Scan 断言）。
- **样式一致性**：表头 `| Requirement | Summary | Status | Evidence | Notes |` 与 021/023 一致；partial 标记方式与 023 FR-025 一致；evidence 引用格式（文件路径 + 行号）与 021/023 一致。

---

### 重审指引

重审时只需验证：
1. FR-011 Notes 是否修正，selectinload 冗余是否移除（或改用 len() 内存聚合）
2. SC-002 Status 是否改为 partial（或补 P95 benchmark 数据）

---

## 第 2 次审查（重审）

### 判定：PASS

#### 上次问题复核

| # | 上次问题 | 当前状态 | 验证证据 |
|---|---------|---------|---------|
| 1 | FR-011 Notes 描述 selectinload 用于序列化但代码从不访问 branch.versions/blocks；实际 5 查询（1 list + 2 selectinload + 2 batch COUNT），spec 只允许 (a) 聚合子查询 或 (b) selectinload + 内存聚合 | ✅ 已修复 | (a) `repository.py:list_for_user` 移除 selectinload（`grep -rn selectinload backend/` 0 命中）；保留 `get_counts_batch` 用 GROUP BY COUNT 只返回 count tuple（不实例化 ORM 对象、不传输整行）；查询数 5→3（1 list + 2 batch COUNT）。(b) FR-011 Notes 重写为准确描述方案 A："`list_for_user` issues a single SELECT (no eager-load); `get_counts_batch` 2 GROUP BY COUNT queries supply version/block counts. Approach: list query + batch COUNT (the spec's 'single roundtrip' alternative — the SELECT returns scalar branch rows and counts come from 2 separate GROUP BY queries, not from in-memory `len()` on eagerly-loaded relationships). selectinload was removed during REQ-DOC-02 review because `list_branches` → `_branch_out` → `ResumeBranchOut` never accesses `branch.versions` / `branch.blocks`"。4 处 stale selectinload 引用全部改为 past tense 描述（L24/L34/L61/L121）。方案 A 属 spec FR-011 (a) 聚合子查询的变体（aggregate on SQL side via GROUP BY COUNT，分 2 次执行而非 1 次 JOIN+OVER()），round-1 review 明确允许此路径。dev 称 GROUP BY COUNT 比 len() 轻量成立：A 只返回 count tuple（10 分支 × 2 = 20 行 count 数据），B 需加载 30 version + 50 block 整行 + ORM 实例化才能 len()。 |
| 2 | SC-002 Status done 但 P95 未实测，与 023 FR-025 partial 模板不一致 | ✅ 已修复 | Status 由 done 改 partial；Notes 引用 023 FR-025 模板："Marked `partial` (consistent with 023 FR-025's 'Not directly verified by a unit test, but covered indirectly' treatment)"；透明披露 "P95 ≤ 300ms is a measurable outcome that has not been directly verified in CI" + "Spec acceptance scenario 2's '≤ 2 SQL' threshold is still exceeded (actual 3 > 2)"。 |

#### 零回归验证

- 后端全量：406 passed + 26 skipped（与 round-1 修正前一致，零回归）
- resumes 专项：29 passed + 8 skipped（包括 e2e_phase1 中 resumes 路径）
- mypy：1 pre-existing error（`repository.py:89` `get` 签名与 `BaseRepository` 不兼容），`git stash` 验证 HEAD 版本同位置同错误（L47），非本次引入
- 前端：`src/api/types.ts:82-83` + `src/pages/Dashboard.tsx:269` + `src/pages/ResumeList.tsx:199` 仍消费 `version_count` / `block_count` 标量字段，无 break

#### 代码改动合理性评估

- 方案 A（移除 selectinload + 保留 get_counts_batch）vs 方案 B（selectinload + len()）：dev 选 A 的理由成立——GROUP BY COUNT 只返回 count tuple，方案 B 需加载全部 version/block 行 + 实例化 ORM 对象才能 len()，A 更轻量
- N+1 消除：`api.py:list_branches` 从 per-branch `get_block_count` + `get_version_count`（2N）改为 `get_counts_batch`（2），O(N)→O(1) 达成
- 无新风险暴露：grep `.versions` / `.blocks` 在 resumes 模块外仅命中 repository.py 注释 + service.py 自身调用（`self.blocks` / `self.versions` 是 service 层 repository 实例，非 ORM 关系），无其他路径依赖 branch.versions/blocks 预加载
- spec FR-011 符合度：方案 A 是 (a) 聚合子查询的变体（aggregate on SQL side via GROUP BY COUNT，分 2 次执行而非 1 次 JOIN+OVER()）。round-1 review 明确允许此路径。spec 的"single roundtrip"措辞是宽松语言（selectinload 路径本身也是 2+ roundtrips），方案 A 与 spec 允许的 (b) selectinload 路径同样是 3 roundtrips，不构成 spec 违反

#### lessons-learned 第6轮准确性

`lessons-learned.md` 第6轮条目"文档因果声明须对照代码逐行验证——selectinload 声称「为序列化加载」实际从未被访问"准确反映本次失败模式：
- 问题诊断（dev 写文档时的因果推断未对照代码验证）准确
- 修复路径（选方案 A 而非 B，理由 GROUP BY COUNT 比 len() 轻量）准确
- 适用场景与避免建议（文档因果声明须 grep 上下游验证、measurable outcome 未实测须标 partial）有可操作性

#### 轻微建议（非阻塞）

- `api.py:64` 注释 `# 022: batch counts (2 SQL roundtrips total, vs 2N before).` 中 "total" 措辞略歧义——可读为"总查询 2 条"（实际 3 条：1 list + 2 batch）。FR-011 Notes 在 requirements-status.md 已准确写明 "Actual query count: 1 (list) + 2 (batch COUNT) = 3 total"，但 inline 注释建议改为 `# 022: batch counts in 2 SQL roundtrips (vs 2N per-branch COUNT before).` 以避免误读
- 后续若补 P95 benchmark（10 分支 × 3 版本 × 5 块场景）使 SC-002 达 done，可同步更新 Evidence 列写入实测数据
