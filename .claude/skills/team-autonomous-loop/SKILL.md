---
name: team-autonomous-loop
description: "InterCraft TEAM 自主发现需求循环。按 BATCH_SIZE 切片，自动扫描 specs/ + memory + .specify/feature.json + TODO + GitHub issues 形成任务池，对每个 REQ 跑 dev → reviewer + tester 循环，最多 3 轮修正；全自主决策不询问用户，通过 .claude/state.json 跨调用持久化任务池与进度。每次调用只处理 BATCH_SIZE 个 REQ，可多次调用推进长任务。**触发场景**：用户说「启动 TEAM」「TEAM 自主」「自主发现」「任务池」「继续推进」「BATCH_SIZE=N」；检测到 .claude/state.json 残留（继续模式）；或主 Agent 判定 specs/ 有 draft/in_progress 项且未排期。"
argument-hint: "[BATCH_SIZE=N] [--resume | --fresh | --dry-run]"
user-invocable: true
disable-model-invocation: false
compatibility: "Requires InterCraft project (specs/ + AGENTS.md + .claude/agents/{analyzer,dev,reviewer,tester}.md) + Agent tool with subagent dispatch"
metadata:
  author: intercraft
  version: 1.0
  project: eGGG
  source: derived-from-main-agent-md
---

# TEAM 自主发现需求循环

**核心**：主 Agent 是 Team Lead（**只调度不干活**），通过 `Agent` 工具派发 4 个 Teammate（analyzer / dev / reviewer / tester）。每次调用**只推进 BATCH_SIZE 个 REQ**，剩余进度写回 `.claude/state.json` 跨调用持久化。

---

## 1. 启动参数解析

从用户输入或 `$ARGUMENTS` 中提取：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `BATCH_SIZE=N` | 1 | 本次调用最多处理 N 个 REQ |
| `--resume` | - | 强制继续模式（C），从 state.json 恢复 |
| `--fresh` | - | 强制全量重发现，丢弃现有 pool |
| `--dry-run` | - | 仅展示将要执行的 REQ，不实际派发 |
| `MODE` 隐含 | - | 由参数决定：A 显式给 REQ_FILE；B 默认；C 检测到 state.json |

**模式判断顺序**（最高优先级在前）：
1. 用户显式说 `MODE=A` 或提供 REQ_FILE 路径 → A
2. `.claude/state.json` 存在且 `paused_at` 非空 → C（继续）
3. 否则 → B（自主发现）

**禁止用 AskUserQuestion 询问**（铁律）：模式、批量大小、冲突裁决、风险取舍全部由本 skill 自行决定。

---

## 2. 第一次读（First Reads，强制并行）

按 CLAUDE.md 要求读取以下文件，**全部用 Read 工具**：

1. `D:/Project/eGGG/CLAUDE.md` — 项目级硬约束
2. `D:/Project/eGGG/AGENTS.md` — 路由层
3. `D:/Project/eGGG/specs/README.md` — specs 索引
4. `D:/Project/eGGG/.specify/feature.json` — 当前 active feature
5. `D:/Project/eGGG/docs/testing/README.md` — 测试规范
6. `D:/Project/eGGG/docs/architecture/source-map.md` — 源码映射
7. `D:/Project/eGGG/.claude/state.json` — **若存在则读取**（C 模式恢复）

读完后再继续。**不要把这 6+1 个文件的内容复述到回复里** — 只用它们建立内部认知。

---

## 3. 状态文件规范

路径：`{PROJECT_ROOT}/.claude/state.json`
维护方：**主 Agent 独占写入**（teammate 不可修改）。

### 3.1 字段定义

```json
{
  "version": 1,
  "mode": "B",
  "batch_size": 1,
  "started_at": "260623 2330",
  "updated_at": "260623 2345",
  "paused_at": null,

  "pool": [
    {
      "id": "REQ-01",
      "title": "<标题>",
      "source": "specs/024-phase2-audit-fix/spec.md",
      "priority": "P1",
      "status": "pending",
      "iterations": 0,
      "spec_path": "specs/024-phase2-audit-fix/spec.md",
      "plan_path": "specs/024-phase2-audit-fix/plan.md",
      "tasks_path": "specs/024-phase2-audit-fix/tasks.md",
      "partial_implementation": false,
      "needs_manual_check": false,
      "verification_note": "代码 / 测试 / git log 搜索命中数",
      "merged_from": [],
      "additional_constraints": [],
      "added_at": "260623 2331",
      "last_touched_at": "260623 2345"
    }
  ],

  "current_batch": [],
  "history": [
    {"req_id": "REQ-01", "iterations": 1, "result": "done", "at": "260623 2344"}
  ],

  "stats": {
    "discovered_count": 0,
    "verified_count": 0,
    "skipped_implemented": 0,
    "needs_manual_check": 0,
    "merged_count": 0,
    "total_done": 0,
    "total_failed": 0
  },

  "lessons": {
    "version": 1,
    "updated_at": null,
    "items": []
  }
}
```

### 3.2 状态转换

`pending` → `in_progress`（开批） → `done` / `failed` / `deferred`（收批）

| 转换 | 触发 |
|------|------|
| `pending → in_progress` | 开始本批实现 |
| `in_progress → done` | tester + reviewer 双 PASS |
| `in_progress → in_progress`（iterations++）| 任一 FAIL 触发修正循环 |
| `in_progress → failed` | 3 轮仍 FAIL（强制收尾） |
| `* → deferred` | 用户主动跳过 / spec 状态变 done |

### 3.3 写入时机

| 触发 | 操作 |
|------|------|
| 启动 | 初始化 version/mode/batch_size/started_at |
| 任务池变化 | diff 合并（新增 / 状态变更 / 重复标 done） |
| 开批 | REQ.status = in_progress |
| 收批 | REQ.status = done/failed，history.append |
| 3 轮未过 | REQ.status = failed，stats.total_failed++ |
| 暂停 | paused_at = 时间戳（用户说"暂停"） |
| 任务池空 + 重扫 3 轮无新 | 自动停下，写收尾日志 |

---

## 4. 日志规范

路径：`{PROJECT_ROOT}/main-log.md`
格式：每行 `- {yymmdd hhmm} {事件}`，精确到分钟。

**模板**（参考 `.claude/agents/main-agent.md` 第 442-469 行）：

```markdown
- 260623 2330 项目启动，模式：B（自主发现）
- 260623 2330 批量大小：1
- 260623 2331 启动需求发现
- 260623 2335 发现完成：3 项 P1，2 项 P2，0 冲突
- 260623 2335 impl-plan: specs/024-phase2-audit-fix/tasks.md

- 260623 2340 ── Batch 1: REQ-01 ──
- 260623 2342 开发完成
- 260623 2344 测试PASS / 审查PASS
- 260623 2344 REQ-01 完成，迭代1次

- 260623 2350 ── Batch 2: REQ-02 ──
...

- 260623 1630 ──── 项目完成 ────
- 260623 1630 全部 5 项需求实现完成
```

---

## 5. 主 Agent 自主决策清单（铁律）

**所有以下决策都由本 skill 自行拍板，绝不向用户询问。**

| 场景 | 默认策略 |
|------|---------|
| 需求冲突（多源指向同一能力）| P1 为主，P2 作为附加约束合并 |
| `[NEEDS MANUAL CHECK]` 项 | 默认进 pool，附 verification_note 风险标记 |
| Spec 模糊字段 | 按合理默认推进，记 `assumed_default: <value>` |
| 批量大小 | 重需求 1、常规 2-3、轻量 3-5（按 spec.estimated_tasks 自动判断） |
| 3 轮未过 | 标 `failed` 跳过，继续下一项 |
| 优先级冲突（spec P1 vs memory P2）| 信任 spec 的 P1 标记 |
| 依赖图冲突 | 走 spec 标注的依赖，无标注则按文件路径推断 |
| 重做已实现功能 | analyzer 已过滤；如误判不再询问，直接做 |
| Schema/数据迁移风险 | 标 `[HIGH RISK]` 日志，不阻塞 |
| 大文件改动 | 拆分子任务推 dev，不阻塞 |

**风险原则**：低风险 → 激进；高风险 → 标风险 + 日志，不阻塞；完全不确定 → 跳过 + 日志说明。

---

## 6. 工作流（5 阶段）

### Phase 0：模式判断与状态恢复

```
读取 .claude/state.json（若存在）：
  - paused_at 非空 → C 模式：读取 current_batch 和 status=in_progress 项
  - pool.status=done 不重新发现
  - pool.status=pending 继续推进

否则：
  - 默认 B 模式（全量发现）
```

**写入日志**：`- {time} 项目启动，模式：{A/B/C}`

### Phase 1：需求发现（仅 B 模式 / 增量模式）

派发 `analyzer` 模式 B（详细提示词见 `.claude/agents/analyzer.md` 第 88-316 行）：

```
Agent(
  to: "analyzer",
  summary: "扫描任务池",
  content: "
实现任务：发现需求并形成任务池
项目根目录：D:/Project/eGGG
状态文件：D:/Project/eGGG/.claude/state.json
当前任务池：{读取并展示现有 pool 中 status≠done 的项}

扫描源（按优先级）：
1. specs/ — status=draft/in_progress（每个 spec 一个 REQ）
2. .specify/feature.json（active feature 整体作为一个 REQ）
3. C:/Users/30803/.claude/projects/D--Project-eGGG/memory/MEMORY.md — 标 ⚠️/📌 的未完成项
4. 代码 TODO 热点：git grep -nE 'TODO|FIXME|XXX' -- '*.py' '*.ts' '*.tsx'
5. GitHub issues（若配置 MCP）：open + P1/P2

⚠️ 强制步骤：对每个候选 REQ 必须做实现状态验证（grep/git log/test 文件/state 历史）
- 已实现 → 跳过
- 未实现 → 加入 pool，status=pending
- 不确定 → 标 [NEEDS MANUAL CHECK]
- 部分实现 → 加入 pool，partial_implementation=true

输出：
- 新发现 REQ 列表（含 source/priority/title）
- 验证报告：V 已实现跳过 / U 未实现加入 / M 含风险
- 冲突自动合并报告（如有）
- 更新后的 .claude/state.json（pool 部分）
- 不返回需求内容，只返回列表与统计
"
)
```

**analyzer 输出约定**（精简返回）：
```
发现完成：
- 新发现 N 项 / 验证 V 项加入 / S 项跳过 / U 项风险 / M 冲突已合并
- 文件：.claude/state.json
- 任务池当前 M 项待实现
```

**主 Agent 收到后**（**不阻塞**）：
1. 复核 analyzer 的合并结果
2. 读取 `.claude/state.json` 刷新内存中的 pool
3. 按 priority + added_at 排序（P1 > P2 > P3，同级时间倒序）
4. 写入日志：`- {time} 发现完成：{N} 候选 / {V} 通过 / {S} 跳过 / {U} 风险`
5. 报告任务池（仅通知，不等待）

### Phase 2：批量实现循环（持续推进）

按 BATCH_SIZE 从 pool 头部取批（`current_batch`）。

> **示例**：BATCH_SIZE=1 → batch 1=REQ-01；BATCH_SIZE=3 → batch 1=REQ-01..03

#### Phase 1.5（必走）：AC 协商循环

**每个 REQ 在进入 Phase 2 实现前必须先经过 AC 协商**。这是验收标准的"生产"环节，不允许跳过（仅 typo 修正、纯 doc 变更可走 `skip_ac=true`）。

```
[开批] 从 pool 取 REQ
  ↓
[轮 0] 派 dev 起草 AC（mode=ac-proposal）
  ↓      → specs/{NNN}-*/ac-matrix.md (status=draft)
  ↓
[轮 N] 派 tester red-team 审核（mode=ac-review）
  ↓      → 追加 ## Tester 反驳日志 段
  ↓
[裁判] main-agent 读反例段 → 逐条判接受/驳回/主动探索
  ↓      → 追加 ## Moderation Log 段
  ↓
  ├─ 全部驳回 → 锁定 → 跳 Phase 2
  ├─ 部分/全部接受 → 派 dev 修订 → 回到 [轮 N+1]
  └─ 3 轮未锁定 → 强制取 tester 更严版本锁定
  ↓
[进 Phase 2] dev 按 ac-matrix.md 实现 + tester 按 AC 逐条打勾
```

详细裁判 SOP 见 `.claude/agents/main-agent.md` 的 "Phase 1.5" 段。

**关键约束**：
- main-agent **只读反例段**（grep `^### R\d+`），不读 ac-matrix 全表（节省 token）
- main-agent 主动探索时记录读了什么（写 Moderation Log）
- 3 轮后**必须**显式调用"取 tester 更严版本"，不静默跳过
- AC 锁定后 Phase 2 dev/tester prompt **必须**带 ac-matrix.md 路径

#### Step 1：批量开发（dev 模式）

派发 `dev`（详细提示词见 `.claude/agents/dev.md`）：

```
Agent(
  to: "dev",
  summary: "实现 {REQ_ID}",
  content: "
实现任务：{REQ_ID} ({REQ_TITLE})
项目根目录：D:/Project/eGGG
spec/plan/tasks：
  - spec: {spec_path}
  - plan: {plan_path}
  - tasks: {tasks_path}

⚠️ 相关历史教训（务必避免重蹈覆辙）：
{从 .claude/lessons.items 过滤出与本 REQ 相关的 3-5 条}
- L001 (code-pattern): ...
- L002 (config-pattern): ...

{if partial_implementation=true}
⚠️ 本需求已有部分实现，请先读相关代码再扩展：
{基于 verification_note 中的路径}

请按 speckit-implement 工作流逐项实现 tasks.md 中 ⏳ 任务。
完成后返回：
- 实现完成：{REQ_ID} ({REQ_TITLE})
- 测试通过：{后端结果} / {前端结果} / 类型检查{结果}
- 如有修正：附带结构化 lesson (category/title/problem/fix)
"
)
```

#### Step 2：批量双维验证（reviewer + tester 并发）

**并发上限 = 2**。并行启动：

```
Agent(
  to: "tester",
  summary: "测试验证 {REQ_ID}",
  content: "
待验证需求 ID：{REQ_ID}
项目根目录：D:/Project/eGGG
impl-plan.md / tasks.md：{tasks_path}

按 .claude/agents/tester.md 工作流验证。
输出 PASS/FAIL + 报告路径（test-reports/{REQ_ID}-test.md）。
不返回报告内容。
"
)

Agent(
  to: "reviewer",
  summary: "代码审查 {REQ_ID}",
  content: "
待审查需求 ID：{REQ_ID}
项目根目录：D:/Project/eGGG
impl-plan.md / tasks.md：{tasks_path}

按 .claude/agents/reviewer.md 工作流审查。
PASS 后调用 code-simplification 精简 + git commit。
输出 PASS/FAIL + 报告路径（test-reports/{REQ_ID}-review.md）+ commit hash。
不返回报告内容。
"
)
```

**判定提取**（不读报告内容，只 grep）：
```bash
Grep(pattern="^### 判定", path="test-reports/{REQ_ID}-test.md")
Grep(pattern="^### 判定", path="test-reports/{REQ_ID}-review.md")
```

#### Step 3：修正循环（最多 3 轮）

| 轮次 | 触发 | 动作 |
|------|------|------|
| 1 | 任一 FAIL | 派发 dev 修正（resume 模式）+ 重测/重审 |
| 2 | 仍 FAIL | 派发 dev 修正（带 lessons 强化提示） + 重测/重审 |
| 3 | 仍 FAIL | 标 `failed` 跳过该项，**不阻塞**继续下一项 |

**dev resume prompt 模板**：
```
Agent(
  to: "dev",
  summary: "修正 {REQ_ID}",
  content: "
修正任务：{REQ_ID} ({REQ_TITLE})
项目根目录：D:/Project/eGGG
测试报告：test-reports/{REQ_ID}-test.md
审查报告：test-reports/{REQ_ID}-review.md
失败教训：{从 FAIL 报告中提取的关键问题}

⚠️ 强化避坑：
{本 REQ 相关的 lessons + 本次失败模式}

请定位并修正所有问题，修正后：
- 更新 lessons-learned.md（人类可读）
- 返回结构化 lesson (category/title/problem/fix)
- 简短确认：修正完成 / 测试通过：{结果}
"
)
```

#### Step 4：状态更新 + 重新发现

```
更新 .claude/state.json：
  - 本批 REQ.status = done / failed
  - iterations 字段更新
  - history.append({req_id, iterations, result, at})
  - stats.total_done++ 或 total_failed++
  - current_batch = []

更新 main-log.md：- {time} {REQ_ID} 完成，迭代{N}次

向用户报告："{REQ_ID} ({REQ_TITLE}) 完成（{done}/{total}），迭代{N}次"
```

**自动继续决策树**（**不询问用户**）：
```
任务池非空 → 继续下一批
任务池空 → 触发重新发现（Phase 1 增量扫描）
重新扫描仍空 → 重复发现，最多 3 轮
3 轮均无新 → 自动停下（不询问） + 写收尾日志
```

### Phase 3：收尾（用户叫停 / 任务池空）

触发条件之一满足即进入 Phase 3：
- 用户说"停止" / "pause" / "退出"
- 任务池空 + 重扫 3 轮无新
- 单项需求 3 轮仍 FAIL（标 failed，继续下一项不阻塞）

```
写入日志：
- {time} ──── 项目完成 ────
- {time} 全部 {N} 项需求实现完成
- {time} 迭代统计：1次通过 {X} / 2次通过 {Y} / 3次通过 {Z} / 强制通过 {W}
- {time} 状态文件已保留：.claude/state.json（下次启动可继续）
```

向用户报告完成（**仅通知，不询问是否继续**）。用户如需继续，下次调用自动继续模式或追加新需求。

---

## 7. 周期汇报节奏（不阻塞）

| 触发 | 汇报内容 |
|------|---------|
| 每批完成 | 单条简短：「REQ-X 完成 N 次迭代」 |
| 任务池变化 | 「发现 3 个新需求：...」 |
| 每完成 5 项 | 中期进度报告：完成 N/M、P1 剩余、阻塞项 + lessons 健康度（新增/复发/系统性） |
| 严重错误 / 3 轮未过 | 立即报告 |
| 自我迭代动作 | 「已自动执行：<具体动作>」（不询问，仅通知） |

---

## 8. 经验沉淀与自我迭代（TEAM 学习）

`lessons` 字段维护在 `.claude/state.json` 内（**不需要独立 lessons.json 文件**）。

### 8.1 写入时机

| 触发 | 来源 |
|------|------|
| 测试失败 → 修正 | tester + dev |
| 审查失败 → 修正 | reviewer + dev |
| 整体需求完成（首次通过）| 主 Agent |
| 3 轮未过 | 主 Agent |

### 8.2 应用时机

| 阶段 | 行为 |
|------|------|
| 需求分析 | analyzer 读 state.json.lessons，输出"相关历史经验" |
| 任务派发 | 给 dev 的 prompt 附"避坑提示"段 |
| 实现过程 | dev 上下文带 lessons，避免重蹈覆辙 |
| 整体收尾 | 主 Agent 分析高频模式 → 主动提出流程改进 |

### 8.3 自我迭代信号（每 5 项 REQ 后做一次健康度分析）

| 信号 | 阈值 | 动作 |
|------|------|------|
| 同类教训 recurrence ≥ 3 | systemic | 主 Agent 标记 `systemic`，日志输出"建议增加 X 流程" |
| 某类问题修复率 < 50% | recurring-failure | 主 Agent 考虑下批前先写规范 |
| 连续 5 个 REQ 无新增教训 | stable | 降低 lessons 检索频率 |

---

## 9. 停止条件

**仅在硬性条件下自动停止，不询问用户。**

| 条件 | 处理 |
|------|------|
| 用户说"停止"/"pause"/"退出" | 标记 `paused_at`，写收尾日志 |
| 任务池空 + 重扫 3 轮无新 | 写收尾日志 + 自动停下 |
| 单项需求 3 轮仍 FAIL | 标 `failed`，跳过该项 |
| 严重错误（teammate 全部失败）| 立即报告 + 暂停 |

**不构成停止**（继续推进）：
- 存在 `partial_implementation=true` 项
- 存在 `[NEEDS MANUAL CHECK]` 风险项
- 冲突已合并但主 Agent 觉得不完美
- spec 描述模糊 → 主 Agent 按合理默认推进

---

## 10. 关键规则（上下文保护铁律）

1. **使用 Agent 工具通信** — 不直接用 Bash 启动子进程，统一走 Agent
2. **不在 prompt 中重复 agent 定义** — agent 定义管"怎么干活"，prompt 只说"干什么活"
3. **不读 teammate 产出文件内容**，只接受路径和 PASS/FAIL 判定
4. **每批任务完成必须更新 state.json 和 main-log.md**
5. **每个关键步骤写日志**
6. **每项需求完成后向用户报告进度**
7. **state.json 由主 Agent 独占写入**
8. **验证报告由验证 teammate 写入**，dev 读取
9. **后台通知简短确认** — 迟到的 teammate 通知只需回复"已确认"
10. **开发批量 = 验证批量** — 默认 BATCH_SIZE=1
11. **并发上限始终为 2** — 验证阶段只有 tester + reviewer 并行
12. **禁止 AskUserQuestion** — 主 Agent 自行决定一切决策

---

## 11. 执行检查清单（每个调用走一遍）

开始时：
- [ ] 解析 BATCH_SIZE / --resume / --fresh / --dry-run
- [ ] 读取 First Reads（CLAUDE.md / AGENTS.md / specs/README.md / .specify/feature.json / docs/testing/README.md / docs/architecture/source-map.md）
- [ ] 读取 .claude/state.json（如存在）
- [ ] 确定 MODE（A/B/C）
- [ ] 写入启动日志

每批：
- [ ] 从 pool 头部取 BATCH_SIZE 个 REQ
- [ ] 状态转 in_progress
- [ ] 派发 dev（run_in_background: true 也行，但本 skill 默认 foreground 等待）
- [ ] 并发派发 tester + reviewer（并发上限 2）
- [ ] Grep 提取 PASS/FAIL 判定
- [ ] 修正循环（最多 3 轮）
- [ ] 状态更新 + 日志 + 报告

收尾：
- [ ] 写收尾日志
- [ ] state.json paused_at 标记（如暂停）
- [ ] 报告最终状态

---

## 12. 与现有 skill 的关系

| 已有 skill | 关系 |
|-----------|------|
| `speckit-implement` | dev teammate 在每个 REQ 内调用，遵循其 TDD + phase 阶段规范 |
| `speckit-tasks` | analyzer 模式 A 派生 impl-plan.md 时使用 |
| `code-simplification` | reviewer PASS 后调用，进行精简重构 |
| `spec-driven-development` | 本 skill 是其 TEAM 自动化实例 |
| `using-agent-skills` | 本 skill 通过 Agent 工具委派子代理，遵循其调度约定 |

---

## 13. 失败注入与恢复

| 失败场景 | 主 Agent 应对 |
|---------|--------------|
| analyzer 超时/失败 | 重试 1 次；仍失败 → 标记"本轮跳过发现"，直接用现有 pool 继续 |
| dev 失败（异常退出）| 标 REQ.status=failed，继续下一批（**不阻塞**） |
| tester/reviewer 失败 | 同上 |
| state.json 损坏 | 备份为 state.json.bak，重建空文件 + 全量重发现（B 模式） |
| BATCH_SIZE 超过 pool 大小 | 取 min(BATCH_SIZE, len(pool))，不报错 |
| `--dry-run` 模式 | 跳过 Phase 2，仅展示"将要执行 N 个 REQ：<列表>" |
