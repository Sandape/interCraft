# Implementation Plan: Personal Ability Profile

**Branch**: `006-personal-ability-profile` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

**Input**: Feature specification from `specs/006-personal-ability-profile/spec.md`

---

## Summary

在 Phase 2 已有的能力维度(ability_dimensions)之上构建**用户端能力画像可视化层**:雷达图展示 actual vs ideal 6 维度分数、自评 UX 增强(替代现有 PATCH 端点)、成长曲线、可分享只读链接、PDF 导出、管理员只读查看。不修改现有的 ability_dimensions 数据模型或写入路径,只增加 3 张新表(profile_share_links、profile_views、export_logs)。

技术决策(基于 research.md):
- 前端雷达图:recharts (已存在于项目依赖中,直接使用 PolarGrid + PolarAngleAxis + Radar)
- 前端成长曲线:recharts LineChart
- PDF 导出:后端 playwright-python (headless Chromium 渲染前端组件截图)
- 分享链接:UUID v7 token + optional expiry,无额外认证

---

## Technical Context

**Language/Version**:
- 后端:Python 3.11+(已有项目标准)
- 前端:TypeScript 5.6 strict mode(已有项目标准)

**Primary Dependencies**:

| 层 | 依赖 | 类型 | 说明 |
|---|---|---|---|
| 后端 - PDF | `playwright` | 新增 | headless 浏览器渲染 PDF |
| 前端 - 图表 | `recharts` | 已有 | RadarChart + LineChart |
| 前端 - 日期 | `date-fns` | 已有 | 日期格式化 |

**Storage**: PostgreSQL 15(已有) — 新增 3 张表在单次迁移 `0007_ability_profile.py` 中创建。

**Testing**:
- 后端单测:pytest + pytest-asyncio,就近放在 `backend/app/modules/ability_profile/tests/`
- 后端集成:在 `tests/integration/` 新增 profile 相关测试(RLS 隔离、分享链接生命周期)
- 前端单测:vitest + @testing-library/react,`src/**/ability-profile/**/*.test.ts(x)`
- 前端 E2E:playwright,`tests/e2e/sc-ability-profile.spec.ts`

**Target Platform**: 现代桌面浏览器(项目已有标准)。

**Project Type**: Web application (frontend + backend),已有项目追加新模块。

**Performance Goals**:
- 雷达图加载 P95 ≤ 2s(基于已有 ability_dimensions GET 端点)
- PDF 导出 P95 ≤ 8s(含 headless 渲染时间)
- 分享链接生成 ≤ 500ms
- 分享页加载 ≤ 3s

**Constraints**:
- 不修改现有 `ability_dimensions` 表结构或已有 API 契约
- 不引入新的第三方图表库(复用 recharts)
- PDF 生成需在后台 worker 中异步排队,不阻塞 API
- 分享链接无额外认证(基于 UUID 不可猜测性)

**Scale/Scope**:
- 用户画像数:与活跃用户数一致
- 每人分享链接:≤ 10(限制防止滥用)
- PDF 导出频率:≤ 5次/用户/小时(速率限制)
- 前端页面:1 个新增页面(`/ability-profile`)+ 分享页(无壳路由)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

依据 `.specify/memory/constitution.md` v1.0.0 的 5 大原则 + 技术约束 + 工作流,逐条校验:

### 原则 I — Library-First

| 检查点 | 本特性落点 | 状态 |
|---|---|---|
| 后端模块自包含,有 README + 公开 API + 配置 + 示例命令 | `backend/app/modules/ability_profile/` 下独立模块,满足要求 | ✅ |
| 前端特性模块是「库」 | `src/pages/AbilityProfile/` 自包含,内部组件/服务/测试独立 | ✅ |

### 原则 II — CLI Interface

| 检查点 | 本特性落点 | 状态 |
|---|---|---|
| 文本 I/O,`--json` 模式可机读 | CLI 入口 `backend/app/modules/ability_profile/cli.py` | ✅ |
| CLI 退出码有文档 | README 列出 | ✅ |
| 前端核心逻辑可被 CLI 验证 | 雷达图数据聚合逻辑提供 `scripts/verify-profile-aggregation.mjs` | ✅ |

### 原则 III — Test-First

| 检查点 | 本特性落点 | 状态 |
|---|---|---|
| 写测试 → 看红 → 签收 → 最小实现 → 重构 | tasks.md 中测试任务在 impl 任务前 | ✅ |
| UI 任务:组件测试先于组件 | RadarChart 组件测试先于组件实现 | ✅ |

### 原则 IV — Integration & Synchronization

| 检查点 | 本特性落点 | 状态 |
|---|---|---|
| 跨服务通信在真实或内存级适配器上跑通 | `tests/integration/` 起真实 DB 测试 RLS 隔离 + 分享链接生命周期 | ✅ |
| 不允许全部 mock 的快乐路径 | 集成测试 = 真实 DB,前端 E2E = 真实后端 | ✅ |

### 原则 V — Observability

| 检查点 | 本特性落点 | 状态 |
|---|---|---|
| 结构化日志含必要 context | 分享链接生成/撤销/访问、PDF 导出、管理员查看均记录 | ✅ |
| 错误上下文含足够复现信息 | 统一经已有异常包装 | ✅ |

### Technology & Stack Constraints

| 检查点 | 本特性落点 | 状态 |
|---|---|---|
| 前端 TS strict + React 18 + Vite + TailwindCSS | 已有,不新增框架 | ✅ |
| 后端 MUST 暴露 HTTP 契约 | 新增路由挂载到 `/api/v1/ability-profile/*` | ✅ |
| 持久层 MUST 用 SQLAlchemy + Alembic | 新建模型 + 迁移 | ✅ |
| RLS 强制启用 | 新增表均启用 RLS | ✅ |

### Constitution Check 结论

**PASS — 无违规项**。Complexity Tracking 为空。

---

## Project Structure

### Documentation (this feature)

```text
specs/006-personal-ability-profile/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
│   ├── README.md        # 契约总览
│   ├── profile.md       # 能力画像仪表盘契约
│   ├── share.md         # 分享链接契约
│   ├── export.md        # PDF 导出契约
│   └── admin.md         # 管理员查看契约
├── checklists/
│   └── requirements.md  # Spec quality checklist
├── spec.md              # 特性 spec
└── tasks.md             # Phase 2 输出(/speckit-tasks)
```

### Source Code (repository root)

```text
D:\Project\eGGG\
├── backend/
│   ├── app/
│   │   ├── modules/
│   │   │   └── ability_profile/         # 新增模块
│   │   │       ├── __init__.py
│   │   │       ├── README.md
│   │   │       ├── models.py            # ProfileShareLink / ProfileView / ExportLog
│   │   │       ├── schemas.py           # Pydantic request/response
│   │   │       ├── service.py           # 业务逻辑
│   │   │       ├── repository.py        # DB 访问
│   │   │       ├── api.py               # /api/v1/ability-profile/* 路由
│   │   │       ├── cli.py               # 模块 CLI
│   │   │       ├── pdf.py               # Playwright PDF 生成
│   │   │       └── tests/
│   │   │           ├── test_models.py
│   │   │           ├── test_service.py
│   │   │           └── test_api.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       └── ability_profile.py   # 挂载 modules.ability_profile.api
│   │   └── workers/
│   │       └── tasks/
│   │           └── pdf_export.py        # ARQ worker 任务
│   ├── migrations/
│   │   └── versions/
│   │       └── 0007_ability_profile.py   # 新增 3 张表
│   └── tests/
│       └── integration/
│           └── test_ability_profile.py   # RLS + 分享 + 导出集成测试
│
├── src/                                 # 前端 React 项目
│   ├── pages/
│   │   ├── AbilityProfile.tsx           # 新增:能力画像仪表盘(雷达图 + 列表)
│   │   ├── AbilityProfileDetail.tsx     # 新增:单能力详情(历史趋势)
│   │   └── SharedAbilityProfile.tsx     # 新增:分享页(无壳只读)
│   │   ├── AbilityProfile/
│   │   │   ├── RadarChart.tsx           # 雷达图组件
│   │   │   ├── AbilityCard.tsx          # 能力卡片(趋势指示器)
│   │   │   ├── TimelineChart.tsx        # 成长曲线组件
│   │   │   ├── AbilityDetail.tsx        # 能力详情面板
│   │   │   └── ShareDialog.tsx          # 分享链接弹窗
│   │   ├── hooks/
│   │   │   ├── queries/
│   │   │   │   └── useAbilityProfile.ts # React Query hooks
│   │   │   └── mutations/
│   │   │       ├── useSelfAssess.ts     # 自评 mutation
│   │   │       ├── useShareLink.ts      # 生成/撤销分享链接
│   │   │       └── useExportPDF.ts      # PDF 导出 mutation
│   │   └── api/
│   │       └── abilityProfileClient.ts  # API 调用封装
│
├── tests/
│   └── tests/e2e/
│       └── sc-ability-profile.spec.ts   # E2E:查看→自评→分享→导出→管理查看
│
└── scripts/
    └── verify-profile-aggregation.mjs   # CLI:验证评分聚合逻辑
```

**Structure Decision**: Option 2 (Web application) — 延续项目已有结构。后端新增 `ability_profile` 模块,前端新增 `AbilityProfile/` 页面及其子组件。不创建新的顶级目录。

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| (无) | — | — |

---

## Re-evaluation after Phase 1 design

*Phase 1 设计完成,复检 Constitution Check:*

| 原则 | Phase 0 结论 | Phase 1 复检 |
|---|---|---|
| I. Library-First | ✅ | ✅ |
| II. CLI Interface | ✅ | ✅ |
| III. Test-First | ✅ | ✅ |
| IV. Integration & Synchronization Testing | ✅ | ✅ |
| V. Observability | ✅ | ✅ |
| Technology & Stack | ✅ | ✅ |
| Development Workflow | ✅ | ✅ |

**结论**: **PASS — 无新增违规**。

---

## Out of Scope (明确排除)

| 项 | 原因 | 何时引入 |
|---|---|---|
| 修改现有 ability_dimensions 数据模型 | 已有,不需要改 | N/A |
| 新的能力分类 (6 维度已定) | Phase 2 已定义 | N/A |
| 引入新的图表库(使用已有 recharts) | 避免依赖膨胀 | N/A |
| 能力与简历编辑器深度集成 | 澄清 Q2,未来可能 | 后续版本 |
| 移动端 App | 项目标准 | 不在 MVP |
| 多语言支持 | 项目标准 | 不在 MVP |

---

## References

- 完整产品 spec: `specs/001-intercraft-product-spec/spec.md`
- Phase 2 数据模型: `specs/001-intercraft-product-spec/data-model-phase-2.md`
- Phase 2 ability 契约: `specs/001-intercraft-product-spec/contracts/abilities.md`
- Phase 4 面试评分: `specs/003-phase4-interview-agent/spec.md`
- 宪法: `.specify/memory/constitution.md` v1.0.0
- Spec quality checklist: `specs/006-personal-ability-profile/checklists/requirements.md`
