# Quickstart Validation: REQ-063 派生满页校准

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Contracts**: [contracts/](./contracts/)

## Prerequisites

- Backend + worker + Redis + PostgreSQL 可用；Playwright Chromium 已安装
- 存在可用根简历与带 JD 的岗位（或使用既有 demo 账号夹具）
- 前端 `npm run dev`；后端 API 可达

## Scenario A — 真实测量取代字符估算（P1）

1. 触发一键派生，目标 **1** 页，素材明显超过一页字符估算边界但预览会到 2 页的样例（或固定 fixture markdown）。
2. 等待 run `succeeded` 或 `needs_guidance`。
3. **Expect**:
   - `artifacts.page_report.measured` 等于编辑器打开后的预览页数（允许校准后变为 1）
   - `page_report` 含 `last_page_fill_ratio` 与 `decision`
   - **Fail if**: `measured` 仍可由「仅字符长度」解释且与预览不一致却标成功

## Scenario B — 近失配先行距（P1）

1. Fixture：目标 1，初稿测量 2 页且末页 fill ≤ 1/3。
2. **Expect** 策略序列以 `tighten_line_height` 开头；若行距成功压回 1 页且 fill ≥ 2/3 → `succeeded`，且未不必要调用 prune。
3. 行距触底仍 2 页 → 出现 `agent_prune` 或 `needs_guidance`。

## Scenario C — 过空末页 Bad Case（P1/P2）

1. Fixture：目标 2，初稿 measured=2 且 fill &lt; 1/3。
2. **Expect**:
   - 首个决策为 `agent_expand`（跳过靠行距「凑满」）
   - `resume_page_bad_cases`（或等价查询）存在 `kind=budget_underestimate`
   - 扩写有来源；无来源则 `needs_guidance`，不编造

## Scenario D — 列表与保存回写（P1）

1. 打开任一派生简历，记下预览页数 P。
2. 对照简历中心「实际 x 页」。
3. 若故意编辑使分页变为 P'，保存。
4. **Expect**: 列表实际页数 = P'；纯打开不保存不得刷出无意义新版本风暴。

## Scenario E — PDF 终裁（P1）

1. 成功派生（目标=实际=预览）。
2. 导出 PDF，独立清点页数 = 目标。
3. （可选）注入不匹配：导出门禁 422 `PAGE_COUNT_MISMATCH`，DB `actual_page_count` 更新为 PDF 页数。

## Automated gates (as implemented)

```text
cd backend && uv run pytest -q backend/tests/unit/resume_derive/test_calibrate_decision.py
cd backend && uv run pytest -q backend/tests/unit/resume_derive/test_page_measure_contract.py
npm run test -- src/modules/resume/pagination/__tests__/fill-ratio.test.ts
npm run e2e -- tests/e2e/063-derive-page-fill.spec.ts
```

## Evidence

将运行日志、截图、PDF 页数核对写入 `docs/evidence/063-derive-page-fill/`（勿堆在仓库根目录）。
