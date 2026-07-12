# Implementation Plan: 派生简历满页校准与真实页数一致 (REQ-063)

**Branch**: `063-derive-page-fill` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/063-derive-page-fill/spec.md`

## Summary

把派生页数校准从「字符估算」升级为「真实分页测量 + 末页填充率决策 + PDF 终裁」：目标 N 页时，成功稿必须页数严格等于 N 且末页充实（默认填充率 ≥ 2/3）；近失配先调行距，结构失配再 Agent 剪枝/扩写；过空末页直接扩写并记 Bad Case；编辑保存回写 `actual_page_count`，纠正列表与打开后不一致。

技术方案（详见 [research.md](./research.md)）：

1. 扩展前端 `paginateMarkdownHtml` 返回末页填充率；后端校准循环通过 Playwright 执行同源测量脚本，废除 `_estimate_pages` 字符启发式作为真相。
2. 新增确定性决策器（spacing → prune/expand → guidance）驱动 `calibrate_pages`；Agent 仅在决策器要求时改写正文。
3. 丰富 `page_report`；稀疏满页初稿写入可检索 Bad Case；保存 API 接受预览页数回写派生 `actual_page_count`。
4. 保留既有 PDF `/Count` 导出门禁为终裁，冲突时回写真实 PDF 页数。

## Technical Context

**Language/Version**: TypeScript (strict) + React 18 (frontend); Python 3.12 (backend)

**Resolved Dependencies**: 沿用仓库现有 lockfile — Playwright（backend PDF/测量）、pypdf（PDF 页数）、既有 Markdown 渲染与 `paginateMarkdownHtml`、LangGraph derive graph、ARQ `execute_resume_derive`

**Dependency Support**: Playwright / pypdf / LangGraph 已在 REQ-055/导出路径生产使用；本特性不新增未支持的核心依赖。测量脚本与编辑器分页同源，避免双算法漂移。

**Storage**: PostgreSQL — 扩展 `resume_derive_runs.artifacts` / 派生 `derive_meta` 中的 `page_report`；新增轻量表或 JSONB 集合承载 page Bad Case（见 data-model）；`resumes_v2.actual_page_count` 语义改为真实测量/回写

**Testing**: pytest（决策器单测、测量契约、校准集成）；Vitest（填充率、保存回写）；Playwright E2E（列表页数=预览；满页样例；导出硬门禁）

**Target Platform**: Web app + Linux/Windows 可跑的 backend worker（需 Chromium for Playwright）

**Project Type**: Full-stack web feature（`src/` + `backend/app/`）

**Performance Goals**:
- 单轮 HTML 真实测量（Playwright）P95 ≤ 3s（暖进程/复用 browser）
- 校准自动轮次 ≤ 5（继承 REQ-055）；行距扫预设 ≤ 现有 LINE_HEIGHT_PRESETS 次数
- 导出 PDF 页数检查额外开销 ≤ 2s（既有）

**Constraints**:
- 成功态：`measured == target` 且 `last_page_fill_ratio ≥ COMFORT`（默认 2/3）
- 行距不得低于主题可读下限
- 禁止编造；扩写仅根简历/已确认补充事实
- 打开浏览不得强制写库风暴；保存/防抖持久化才回写
- PDF 终裁不可削弱

**Scale/Scope**:
- 4 user stories；17 FRs；触达 derive calibrate、pagination、resumes_v2 save/export、列表展示
- 1 次小迁移（Bad Case 表或可空 JSONB 字段）；无新用户向导

**Risk Classification**: **R2**（Agent 改写简历正文 + 模型调用）；行距/页数回写为 R1；只读测量为 R0

**Operation Risk Matrix**:
| Operation | Risk |
|---|---|
| 分页测量 / 列表读页数 | R0 |
| 行距自动调整、actual_page_count 回写 | R1 |
| Agent 剪枝/扩写、Bad Case 落库、多轮校准 | R2 |

**Execution Model**: 既有 ARQ `execute_resume_derive` + LangGraph `resume_derive` 内 `calibrate_pages` 节点；编辑器保存为同步 HTTP

**AI/Agent State**: 复用 `ResumeDeriveState`；扩展 `page_report` 形状；校准轮次/策略序列写入 artifacts；剪枝/扩写须过 source validator

**External Dependencies**: LLM（剪枝/扩写）；Playwright Chromium（测量）；无新渠道

**Observability & Privacy**: 结构化日志含 `run_id`、`decision`、`last_page_fill_ratio`、`calibrate_round`；Bad Case 属用户私有数据，租户隔离继承 derive

**Migration & Rollout**: expand：新增 Bad Case 存储 + page_report 字段向后兼容；旧派生行在下次保存时用预览页数回写 actual；导出门禁行为不变。回滚：可 feature-flag 回退到仅 PDF 门禁 + 旧 calibrate（不推荐长期）

**Operational Release Unit**: `resume_derive` + `resumes_v2` export；继承既有导出/派生控制面

## Constitution Check

*SCREEN before Phase 0; re-check after Phase 1 design.*

| Gate | Applicability / inherited control | Pre-screen | Post-design | Evidence link |
|---|---|---|---|---|
| Boundaries & composition roots | 测量/决策在 domain；Agent node 薄编排；HTTP 仅 save/export | CLEAR | PASS | research R1–R3；Project Structure |
| Typed contracts & authorization | page_report / save preview_page_count / 错误码 | CLEAR | PASS | [contracts/](./contracts/) |
| Async, transactions & process isolation | 校准在 ARQ worker；Playwright 进程隔离 | CLEAR | PASS | research R1 |
| Durable dispatch & concurrency ownership | 继承 derive run；不新增长任务类型 | CLEAR | PASS | 复用 `resume_derive_runs` |
| LangGraph state & compatibility | 扩展 page_report；N-1 旧 run 可读 | CLEAR | PASS | data-model；derive-agent contract |
| Agent safety & data lifecycle | 反编造、轮次上限、Bad Case 生命周期随用户数据 | CLEAR | PASS | research R2–R4；spec FR-009/016 |
| Test-first & evaluation | 决策表单测 + 满页样例 + E2E | CLEAR | PASS | [quickstart.md](./quickstart.md) |
| Observability, release & dependency support | 日志字段 + 既有 Playwright 支持 | CLEAR | PASS | research R5 |

Deviation Register: 无（本特性无 APPROVED DEVIATION）。

## Project Structure

### Documentation (this feature)

```text
specs/063-derive-page-fill/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── page-measure.md
│   ├── calibrate-decision.md
│   └── openapi-page-fill.yaml
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
backend/app/
├── modules/resume_derive/
│   ├── page_count.py              # [KEEP] PDF /Count
│   ├── page_measure.py            # [NEW] Playwright 真实分页 + fill ratio
│   ├── calibrate_decision.py      # [NEW] 确定性决策器
│   ├── bad_cases.py               # [NEW] Bad Case 写入/查询
│   ├── service.py                 # [MODIFY] 成功/引导态 actual 语义
│   └── schemas.py                 # [MODIFY] page_report 形状
├── agents/nodes/resume_derive/
│   └── calibrate_pages.py         # [MODIFY] 接测量 + 决策器；删字符估算真相
├── modules/resumes_v2/
│   └── api.py / schemas.py        # [MODIFY] save 回写 preview→actual
└── workers/tasks/resume_derive.py # [MODIFY] 落库 measured 来自 page_report

src/modules/resume/
├── pagination/
│   ├── markdown-pages.ts          # [MODIFY] lastPageFillRatio / per-page fill
│   ├── types.ts                   # [MODIFY]
│   └── measure-bundle.ts          # [NEW] 可供 Playwright 注入的测量入口（若需要）
├── derive/
│   ├── PageControlPanel.tsx       # [MODIFY] 展示填充率/策略（可选 P2）
│   └── target-pages.ts            # [MODIFY] 废弃 3200 字作为权威预算
└── v2/
    ├── api/index.ts               # [MODIFY] save 传 preview_page_count
    └── store/…                    # [MODIFY] 保存时带上 pageCount

tests/
├── backend/tests/unit/resume_derive/test_calibrate_decision.py
├── backend/tests/unit/resume_derive/test_page_measure_contract.py
├── src/modules/resume/pagination/__tests__/fill-ratio.test.ts
└── tests/e2e/063-derive-page-fill.spec.ts
```

**Structure Decision**: 扩展既有 InterCraft 全栈布局；不新建产品模块边界。测量与决策为 `resume_derive` 内可单测 library；校准 node 只编排。

## Deviation Register

> 无 post-design APPROVED DEVIATION。
