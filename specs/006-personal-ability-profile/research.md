# Phase 0 Research: Personal Ability Profile

**Status**: Phase 0 output · **Date**: 2026-06-16 · **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 0. 上下文

本特性在 Phase 2 已有的 `ability_dimensions` 系统之上构建可视化层。所有未在 spec 中明确的技术选型,在此记录决议。

继承决策(从 Phase 1 + Phase 2 research 继承,不再重复研究):

| # | 决策 | 来源 |
|---|---|---|
| D-1 | 后端 = FastAPI + SQLAlchemy 2.0 async + asyncpg | Phase 1 D-1 |
| D-2 | DB = PostgreSQL 15 | Phase 1 D-2 |
| D-3 | 前端 = TypeScript strict + React 18 + Vite + TailwindCSS + Zustand + React Query | Phase 1 D-13 |
| D-4 | RLS = `SET LOCAL app.user_id` + 所有业务表启用 | Phase 1 D-10 |
| D-5 | 鉴权 = JWT (access 15min + refresh 7d) | Phase 1 D-6 |
| D-6 | 队列 = ARQ (PDF 异步生成) | Phase 1 D-3 |
| D-7 | 6 能力维度 = tech_depth / architecture / engineering_practice / communication / algorithm / business | Phase 2 D-15 |
| D-8 | 评分范围 0-10 (actual_score + ideal_score 模型,非 spec 中 1-5 自评模型) | Phase 2 ability_dimensions 现有模型 |

## 1. 本特性需研究的技术选择

### R-1: 前端雷达图库

**问题**:spec FR-001 要求雷达图(radar/spider chart)。项目已有 recharts,需确认是否支持雷达图。

**研究**:recharts 5.x 提供 `RadarChart` + `PolarGrid` + `PolarAngleAxis` + `Radar` 组件,支持多 Radar 叠加(actual vs ideal vs self-assessed)。

**决议**:使用 recharts RadarChart。

- 同一张雷达图叠加 2~3 条 Radar:<actual> / <ideal> / <self-assessed(可选)>
- 前端数据转换:从 `GET /api/v1/ability-dimensions` 返回的 6 行记录映射为 recharts 数据格式
- 优势:零新增依赖,与项目已有图表样式一致

### R-2: 后端 PDF 生成方案

**问题**:spec FR-018 要求导出 PDF(含雷达图)。纯服务端 PDF 库无法渲染 React 图表组件。

**研究方案评估**:

| 方案 | 优点 | 缺点 |
|---|---|---|
| playwright-python (headless Chromium) | 真实渲染,与前端雷达图完全一致 | 需安装 Chromium 二进制,文件较大 |
| weasyprint HTML → PDF | 轻量 | 无法渲染 JS 图表 |
| 后端用 matplotlib/pyplot 重绘雷达图 | 无需浏览器 | 与前端样式不一致,双重维护 |

**决议**:使用 playwright-python 渲染前端页面。

- PDF 生成时,构造一个无头 HTML 页(或调用已有前端 build) → `page.pdf()`
- PDF 生成任务通过 ARQ 异步排队,避免阻塞 API
- 预生成 PDF 可缓存 1 小时(相同数据不重复渲染)
- Chromium 二进制通过 `playwright install chromium` 安装,CI/Docker 中预装

### R-3: 分享链接安全模型

**问题**:spec 假设分享链接基于 UUID 不可猜测性,无需额外认证。

**分析**:UUID v7 具有 122 bit 随机性,暴力猜测概率极低(< 2^(-122))。若需更高安全性可加 optional PIN。

**决议**:
- 默认:UUID v7 token 作为 bearer token
- 可选:用户可设置 4 位数字 PIN(分享链接访问时需输入)
- 速率限制:同一 IP 对分享链接的访问 ≤ 10次/分钟
- 日志:每次访问记录 timestamp + IP(前两段)+ user-agent

### R-4: 前端路由设计

**问题**:新增页面的路由路径。

**决议**:

| 路径 | 页面 | 认证 |
|---|---|---|
| `/ability-profile` | 能力画像仪表盘 | 需要登录 |
| `/ability-profile/:abilityKey` | 单能力详情 + 历史趋势 | 需要登录 |
| `/shared/:shareToken` | 分享只读页 | 公开(无认证) |
| `/shared/:shareToken?pin=xxxx` | 分享页(PIN 保护) | 公开(需 PIN) |

### R-5: 评分聚合实现

**问题**:spec 澄清 Q3 决定按时间衰减加权平均,但未指定具体衰减函数。

**决议**:线性衰减。

```
weight_n = 1 + (n - 1) * decay_factor
// decay_factor = 0.2 (最近一次权重最高,最早一次权重最低)
// 归一化: weighted_avg = sum(score_n * weight_n) / sum(weight_n)
```

示例:3 次评分 [3.0, 3.5, 4.0] → 权重 [1.0, 1.2, 1.4] → 加权平均 ≈ 3.56

此方案在 `scripts/verify-profile-aggregation.mjs` 中作为 CLI 验证。

---

## 2. 关键整合点

### Phase 2 ability_dimensions 读路径

本特性**不修改**现有 `ability_dimensions` API,而是通过新模块 `ability_profile` 封装对已有数据的聚合和展示:

```
GET  /api/v1/ability-dimensions          (已有) → 前端直接消费用于雷达图
POST /api/v1/ability-dimensions/{key}/patch (已有) → 自评走此端点
GET  /api/v1/ability-dimensions/history   (已有) → 成长曲线数据
```

新端点:

```
GET    /api/v1/ability-profile/dashboard  → 聚合数据(含趋势计算)
POST   /api/v1/ability-profile/share      → 生成分享链接
DELETE /api/v1/ability-profile/share/{id} → 撤销分享链接
GET    /api/v1/ability-profile/share/{token} → 公开访问(无认证)
POST   /api/v1/ability-profile/export     → 触发 PDF 导出
GET    /api/v1/ability-profile/exports/{id} → 查询导出状态/下载
GET    /api/v1/ability-profile/admin/{user_id} → 管理员查看
```

---

## 3. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解 |
|---|---|---|---|
| Playwright Chromium 在 CI/Docker 中安装失败 | 中 | PDF 导出不可用 | 回退方案:服务端用 matplotlib 生成静态雷达图作为 PDF 替代 |
| 分享链接被爬虫大规模遍历 | 低 | 数据泄露 | IP 速率限制 + 可选 PIN + 监控异常访问模式 |
| recharts RadarChart 在大量维度时性能下降 | 低 | 仪表盘加载慢 | 限制 6 维度(已有上限),远低于 recharts 性能瓶颈 |
