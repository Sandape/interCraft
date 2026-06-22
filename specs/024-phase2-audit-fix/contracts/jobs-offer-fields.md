# Contract: Jobs Offer Fields

**Feature**: 024-phase2-audit-fix
**Related FRs**: FR-001 ~ FR-008

## Endpoint: PATCH /api/v1/jobs/{id}

**新增请求字段** (仅在 status=`offered` 或 `accepted` 时可写入):

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `offer_salary_text` | string | No | 自由文本，≤ 100 字符 |
| `offer_contact_name` | string | No | ≤ 50 字符 |
| `offer_contact_info` | string | No | ≤ 200 字符（电话/邮箱/微信等）|
| `offer_deadline_at` | ISO 8601 datetime | No | 不能早于当前时间 |

**Behavior**:
- status 不在 `offered` / `accepted` 时，传 offer_* 字段返回 422「Offer 字段仅可在 offered/accepted 状态下写入」。
- `offer_deadline_at` 早于当前时间返回 422「截止日期不能早于今天」。

## Endpoint: GET /api/v1/jobs/{id}

**响应新增字段**:

```json
{
  "id": "uuid",
  "title": "前端工程师",
  "company": "Acme Inc",
  "status": "offered",
  "status_history": [...],
  "offer_salary_text": "30K-50K/月",
  "offer_contact_name": "HR 张女士",
  "offer_contact_info": "hr@example.com / 13800138000",
  "offer_deadline_at": "2026-06-29T00:00:00Z",
  "created_at": "...",
  "updated_at": "..."
}
```

- 所有 offer_* 字段始终在响应中（null 或具体值）。
- 字段顺序: 4 个 offer_* 字段紧跟 `status_history` 之后，`created_at` 之前。

## Endpoint: GET /api/v1/jobs (列表)

列表响应**不包含** offer_* 字段（避免 N+1 + 隐私字段暴露）。仅 `GET /api/v1/jobs/{id}` 详情接口返回。

## Frontend UI Contract

`JobsDetailPanel.tsx` 5 大区域:

1. **Basic Info**: title / company / salary_range_text / status（编辑模式下可改 input）
2. **Timeline**: `status_history` 倒序展示，每条显示 from→to / note / at
3. **Edit Mode**: 切换按钮，basic info 变 input，提供保存/取消；未保存切换页面弹 unsaved-changes 警告
4. **Offer Section**: 仅在 status=offered/accepted 时显示，4 个 offer 字段可编辑
5. **Activities**: 投递/面试/offer 三类活动列表，每条含 timestamp + note

## Testing

- 单测 `test_jobs_offer_fields.py`:
  - PATCH 在 status=offered 时接受 4 字段 → 200。
  - PATCH 在 status=fresh 时传 offer_* → 422。
  - GET 返回 4 字段（null 或值）。
  - `offer_deadline_at` 早于今天 → 422。
- 集成 `test_jobs_offer_e2e.py`:
  - 创建岗位 → 推进到 offered → 录入 Offer 字段 → 查询验证持久化。
- 前端 `test_jobs_detail_panel.test.tsx`:
  - 渲染 5 大区域断言。
  - Offer 区仅在 status=offered/accepted 时显示。
