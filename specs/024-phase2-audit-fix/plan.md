# Implementation Plan: Phase 2 (M5-M11) spec/code 偏差审计与修复

**Branch**: `024-phase2-audit-fix` | **Date**: 2026-06-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-phase2-audit-fix/spec.md`

## Summary

补齐 v1 Phase 2 模块的 6 项 spec/code 偏差：(1) M9 Offer 字段未实现（4 列 + 迁移 + service + UI）；(2) M9 `status_history` 字段名前后端不一致（前端对齐后端 `{from, to, at, note}`）；(3) M9 `JobsDetailPanel` 80% FR 缺失（时间线/编辑/推进/删除/Offer 区/activities）；(4) M9 outbox 未接入（4 类写操作走 outbox）；(5) M7 `archived` 状态过度实现（移除第 4 态 + FSM 回归 3 态 + reset）；(6) M8 PIN/ProfileView 过度实现 + PDF 导出语义偏差（决策移除 PIN/ProfileView，PDF 改同步直接下载）。零业务逻辑改动（除移除 archived + PIN/ProfileView），零契约改动（除新增 4 个 Offer 字段 + 移除 `archived_at` 列），既有 E2E 零回归。

**PIN/ProfileView 决策（plan 阶段落地）**: **移除**。理由：(a) v1 spec 006 已发布且无 FR 覆盖，属过度实现；(b) 保留需补 spec FR + 评估 PIN 暴力破解安全性，scope 蔓延；(c) 移除代码量小（`pin_hash` 列 + `ProfileView` 表 + 几个 service 函数）；(d) 若后续真有需求，走 v2.1 独立 feature spec 流程。spec 006 不追加 FR，仅清理代码。

## Technical Context

**Language/Version**: Python 3.11 (backend) + TypeScript 5.x (frontend)

**Primary Dependencies**: FastAPI 0.110+, SQLAlchemy 2.x, Alembic, ARQ; React 18, react-query 5.x, Vite 5.x, TailwindCSS; 既有 `src/lib/outbox/` 基础设施（用于 resume 模块）

**Storage**: PostgreSQL 15+

**Testing**: pytest (backend), Vitest (frontend), Playwright (E2E round-1 + round-2)

**Target Platform**: Linux server + modern browser

**Project Type**: Web service + SPA

**Performance Goals**: 不退化（本 feature 是偏差修复，无性能目标）

**Constraints**: 不改既有 API 契约（除新增 4 个 Offer 字段 + 移除 `archived_at`）；不破坏既有 E2E；不改动 M5/M6/M10/M11

**Scale/Scope**: M7 错题本 + M8 能力画像 + M9 岗位追踪 3 个模块

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ Pass | Offer 字段集中在 jobs 模型；outbox 复用既有 `src/lib/outbox/`；FSM 收敛到 `errors/service.py` 单一 source of truth；PIN/ProfileView 移除后 ability_profile 边界更清晰 |
| II. CLI Interface | ✅ Pass | 本 feature 是偏差修复，不新增 CLI；既有 CLI 不受影响 |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | 每 US 先写测试：Offer 字段用 API 契约测试；status_history 用前端 typecheck + 组件测试；archived 用 422 断言测试；outbox 用离线 E2E；PDF 用同步下载断言 |
| IV. Integration & Synchronization Testing | ✅ Pass | Offer 字段端到端（DB → API → UI）；outbox 离线→恢复 E2E；FSM 转换用真实 PostgreSQL + RLS 验证；PDF 同步生成用真实能力画像数据 |
| V. Observability | ✅ Pass | 非法 FSM 转换记录 warning 日志；outbox dead letter 记录 error；PDF 导出耗时记录 info 日志 |

**Gate Result**: PASS — 无违规项，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/024-phase2-audit-fix/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── jobs-offer-fields.md      # 新增 Offer 字段契约
│   ├── status-history-fields.md  # 字段名对齐契约
│   ├── error-fsm.md              # 错题状态机契约
│   └── ability-profile-pdf.md    # PDF 同步下载契约
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── jobs/
│   │   │   ├── models.py          # 修改: 新增 4 列 offer_*
│   │   │   ├── service.py          # 修改: PATCH 接受 offer_*; status_history 已用 {from,to,at,note}
│   │   │   └── api.py             # 修改: PATCH/GET 返回 offer_*
│   │   ├── errors/
│   │   │   ├── models.py          # 修改: 移除 archived_at 列
│   │   │   ├── service.py         # 修改: VALID_TRANSITIONS 移除 archived, 仅 3 态 + reset
│   │   │   └── api.py             # 修改: PATCH status 对 archived 返回 422
│   │   └── ability_profile/
│   │       ├── models.py          # 修改: 移除 pin_hash 列, 移除 ProfileView 表
│   │       ├── service.py         # 修改: 移除 PIN 校验逻辑, PDF 导出改同步
│   │       └── api.py             # 修改: 移除 PIN 校验中间件, PDF 端点同步返回
├── alembic/versions/
│   ├── xxxx_add_jobs_offer_fields.py      # 新增
│   ├── xxxx_drop_error_questions_archived_at.py  # 新增
│   └── xxxx_drop_ability_profile_pin_profileview.py  # 新增
└── tests/
    ├── unit/
    │   ├── test_jobs_offer_fields.py       # 新增
    │   ├── test_error_fsm.py              # 新增
    │   └── test_ability_profile_pdf_sync.py  # 新增
    └── integration/
        ├── test_jobs_offer_e2e.py          # 新增
        └── test_outbox_jobs_offline.py    # 新增

frontend/
├── src/
│   ├── repositories/
│   │   └── JobRepository.ts     # 修改: status_history 字段名对齐, offer_* 字段扩展
│   ├── components/jobs/
│   │   ├── JobsDetailPanel.tsx  # 重写: 时间线/编辑/Offer/activities
│   │   ├── JobTimeline.tsx      # 修改: 字段名对齐
│   │   └── JobOfferEditor.tsx   # 新增: Offer 区编辑组件
│   ├── pages/
│   │   └── Jobs.tsx             # 修改: 4 类写操作走 outbox
│   └── lib/outbox/
│       └── jobs.ts              # 新增: 岗位写操作 outbox 适配
└── tests/
    └── unit/
        ├── test_jobs_detail_panel.test.tsx  # 新增
        └── test_outbox_jobs.test.ts        # 新增
```

**Structure Decision**: 严格遵循既有模块化结构。Offer 字段集中在 jobs 模型；outbox 复用既有 `src/lib/outbox/`；FSM 修改在 `errors/service.py`；PIN/ProfileView 移除涉及 ability_profile 模型 + service + api 三层。

## Implementation Strategy

### Phase A — M9 Offer 字段 + JobsDetailPanel (US1, 大改)

**目标**: 补齐 spec 014 FR-018/019/020/021，JobsDetailPanel 覆盖 FR-002/003/009/019/025。

1. TDD: 先写 `test_jobs_offer_fields.py` 断言:
   - `jobs` 表含 4 列 `offer_salary_text` / `offer_contact_name` / `offer_contact_info` / `offer_deadline_at`。
   - `PATCH /api/v1/jobs/{id}` 在 status=`offered` 或 `accepted` 时接受这 4 列。
   - `GET /api/v1/jobs/{id}` 返回这 4 列（null 或值）。
2. 生成 Alembic 迁移 `add_jobs_offer_fields.py`: 4 列 nullable text/timestamptz。
3. 修改 `jobs/models.py` / `service.py` / `api.py`。
4. 前端 TDD: 先写 `test_jobs_detail_panel.test.tsx` 断言渲染时间线 / 编辑按钮 / Offer 区 / activities。
5. 重写 `JobsDetailPanel.tsx`: 5 大区域（basic info / timeline / edit mode / offer section / activities）。
6. 新增 `JobOfferEditor.tsx`: Offer 区编辑组件，校验 `offer_deadline_at` 不能早于今天。

### Phase B — M9 outbox 接入 (US2, 大改)

**目标**: 4 类岗位写操作走 outbox，离线兜底。

1. TDD: 先写 `test_outbox_jobs.test.ts` 断言:
   - 创建/编辑/推进/删除 4 类操作入队 outbox。
   - 离线状态下操作不报错，UI 显示「待同步」。
   - 网络恢复后 FIFO flush。
   - dead letter 重试 3 次后标记。
2. 新增 `src/lib/outbox/jobs.ts`: 4 类操作的 enqueue 适配。
3. 修改 `Jobs.tsx`: 用 outbox 替换直接 react-query mutation。
4. 集成测试 `test_outbox_jobs_offline.py`: 端到端离线→恢复场景。

### Phase C — M9 status_history 字段名对齐 (US3, 小改)

**目标**: 前端字段名对齐后端 `{from, to, at, note}`。

1. 修改 `JobRepository.ts`: `status_history` 类型定义改用 `{from, to, at, note}`。
2. 修改 `JobTimeline.tsx`: 读取 `entry.from` / `entry.to` / `entry.at` / `entry.note`。
3. 运行 `npm run typecheck`，确认无类型错误。
4. 跑既有 E2E 涉及岗位时间线的用例，无回归。

### Phase D — M7 archived 状态移除 (US4, 小改)

**目标**: FSM 回归 spec 016 授权的 3 态 + reset。

1. TDD: 先写 `test_error_fsm.py` 断言:
   - `fresh→practicing→mastered + reset` 路径成功。
   - `fresh→archived` / `practicing→archived` / `mastered→archived` / `practicing→fresh` 返回 422。
2. 修改 `errors/service.py`: `VALID_TRANSITIONS` 移除所有 `archived` 相关转换，仅保留 3 条路径。
3. 生成 Alembic 迁移 `drop_error_questions_archived_at.py`: 移除 `archived_at` 列。
4. 修改 `errors/api.py`: PATCH status 对非法转换返回 422 + warning 日志。
5. 修改 `errors/models.py`: 移除 `archived_at` 字段。

### Phase E — M8 PIN/ProfileView 移除 + PDF 同步 (US5 + US6)

**目标**: 移除过度实现 + PDF 对齐 spec「直接下载」。

1. TDD: 先写 `test_ability_profile_pdf_sync.py` 断言:
   - `GET /api/v1/ability-profile/export-pdf` 同步返回 PDF（Content-Type + Content-Disposition）。
   - 响应时间 ≤ 3s。
   - 不走 ARQ 任务队列。
2. 修改 `ability_profile/service.py`: PDF 导出改同步生成（既有 reportlab / weasyprint），移除 `enqueue_job` 调用（service.py:419-420）。
3. 修改 `ability_profile/api.py`: `export-pdf` 端点同步返回 `Response(content=pdf, media_type="application/pdf")`。
4. 移除 ARQ PDF 任务函数（或保留为「批量导出」独立功能，单次导出走同步）。
5. 生成 Alembic 迁移 `drop_ability_profile_pin_profileview.py`:
   - 移除 `ability_profile_shares.pin_hash` 列。
   - 移除 `profile_views` 表（DROP TABLE）。
6. 修改 `ability_profile/models.py`: 移除 `pin_hash` 字段 + `ProfileView` 类。
7. 修改 `ability_profile/service.py`: 移除 PIN 校验逻辑（service.py:277, 352-356）+ ProfileView 记录逻辑。
8. 修改 `ability_profile/api.py`: 移除 PIN 校验中间件，分享链接访问仅校验 `expires_at` / `revoked_at`。
9. 前端分享链接管理 UI 移除 PIN 设置 + 访问次数展示（若有）。

### Phase F — 跨切面验证 + 回归

**目标**: 既有 E2E 零回归 + SC 全部达成。

1. 跑 round-1 + round-2 E2E（21/21）+ 后端单测 + 前端 vitest。
2. 验证 SC-001~008: Offer 字段端到端、JobsDetailPanel 5 区域、outbox 离线兜底、字段名一致、FSM 3 态、PIN/ProfileView 移除、PDF 同步下载、E2E 零回归。

## Complexity Tracking

> 无 Constitution Check 违规，本节为空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
