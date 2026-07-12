# Research: REQ-063 派生满页校准

**Date**: 2026-07-12
**Spec**: [spec.md](./spec.md)

## R1 — 真实页数测量的单一真相源

**Decision**:
1. **编辑器与校准循环**共用同一套分页测量语义（扩展现有 `paginateMarkdownHtml`：返回 `pageCount` + `lastPageFillRatio` + 可选每页 `fillRatio`）。
2. **后端校准**通过 Playwright 加载预览 HTML，执行同源测量（注入测量 bundle 或等价 evaluate），得到 `PageMeasureResult`。
3. **导出**继续用 PDF `/Count`（`count_pdf_pages`）作终裁；成功导出后可回写 `actual_page_count`。
4. **废除** `calibrate_pages._estimate_pages`（3200 字/页）作为 `actual_page_count` / 成功判定的真相。

**Rationale**: 现网缺陷正是字符估算与 A4 预览分叉（PHASE9 证据：actual=1 但 preview=2）。规格 FR-001/AC-M* 要求真实测量；REQ-055 research R4 已选「HTML 循环 + PDF 门禁」，实现未落地 HTML 侧。

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| 仅修列表文案 / 打开时重算不改校准 | 不解决「假成功 1 页」与满页质量 |
| 每轮校准都出 PDF 再数页 | 过慢过贵；保留为可选终检 |
| Python 重写分页估高 | 必与前端漂移 |
| 纯 jsdom 无布局引擎 | 无法可靠量高度 |

**Implementation note**: Worker 侧复用已有 Playwright；优先 browser 上下文复用。测量失败 → 运行失败/引导，不得回退静默字符估算成功。

---

## R2 — 行距 vs Agent：决策表与阈值

**Decision**: 引入确定性纯函数 `decide_calibrate_action(target, measure, thresholds) -> decision`：

| 条件 | Decision |
|------|----------|
| `measured == target` 且 `fill ≥ COMFORT`（默认 2/3） | `pass` |
| `measured > target` 且 `fill ≤ SPARSE`（默认 1/3） | `tighten_line_height` → 失败则 `agent_prune` |
| `measured > target` 且溢出大（多 ≥2 页或 fill 高仍超） | `agent_prune`（可跳过或少试行距） |
| `measured == target` 且 `SPARSE ≤ fill < COMFORT` | `adjust_line_height_for_fill` → 失败则 `agent_expand` |
| `measured == target` 且 `fill < SPARSE` | `agent_expand` + **`record_bad_case=budget_underestimate`** |
| `measured < target` | `agent_expand`（行距放松仅辅助，禁止靠拉大行距「假满页」） |
| 轮次耗尽 / 行距触底仍失败 / 无素材 | `needs_guidance` |

行距扫描复用前端 `LINE_HEIGHT_PRESETS` 与可读下限；不得低于下限。

**Rationale**: 规格 US1 与用户明确的近失配/过空分流；确定性表可单测，Agent 只做内容手术。

**Alternatives considered**: 总是先 Agent；总是先行距；无填充率只看页数 — 均无法同时满足「满满当当」与成本/反编造。

---

## R3 — `actual_page_count` 与保存回写

**Decision**:
1. 派生落库：`actual_page_count = page_report.measured`（真实测量）；仅 `status=succeeded` 且通过充实门禁时允许导出。
2. `needs_guidance`：写入真实 `measured`（可 ≠ target），**禁止**把 actual 伪造成 target。
3. 派生简历 **PUT/PATCH 保存**：若请求带 `preview_page_count`（或 data.metadata.markdown.pageCount），所有者保存时同步 `actual_page_count`。
4. **禁止**仅因 GET/打开编辑器而写库；允许「保存时」或用户触发的显式同步修正存量。

**Rationale**: FR-011–013；避免只读脏写。

**Alternatives considered**: 打开即自动 PATCH — 易造成并发与无意义写入。

---

## R4 — Bad Case 存储

**Decision**: 新增 `resume_page_bad_cases` 表（或等价可查询存储），最小字段：`id, user_id, run_id, derived_resume_id?, target, measured, last_page_fill_ratio, theme_id, decision, outcome, created_at`。同时把摘要写入该次 `page_report.bad_case_ref`。

**Rationale**: FR-016 / SC-006 要求可检索；仅埋在 JSONB 不利于运营统计。

**Alternatives considered**: 只写 artifacts JSONB — 难聚合；外发评测系统 — 超 scope。

---

## R5 — 观测与门槛配置

**Decision**:
- 阈值 `SPARSE=1/3`、`COMFORT=2/3` 作为配置常量（环境/设置可覆盖），首发验收用默认。
- Metrics/logs：`derive_calibrate_decision_total{decision}`、`page_measure_seconds`、既有 `calibrate_rounds`、`export_page_mismatch_total`。
- Feature flag（可选）：`DERIVE_REAL_PAGE_MEASURE=1` 便于灰度和紧急回退（回退不得恢复「估算当成功」为默认长期行为）。

**Rationale**: 规格 Assumptions；运维可调参而不改代码。

---

## R6 — 与 REQ-055/059 边界

**Decision**: 本特性只升级测量、决策、回写与 Bad Case；不重做选岗向导、建议面板 IA、反编造校验器（继续调用既有 source validator）。PDF 门禁逻辑保留并确保冲突回写。

**Rationale**: Non-Goals；降低范围风险。
