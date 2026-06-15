# API Contracts: Phase 6 — 全局能力收尾

| Contract | Service | Key Endpoints |
|---|---|---|
| [Account](./account.md) | M20 用户生命周期 + M21 导入导出 | 注销/取消注销/导出/导入/状态查询 |
| [Audit](./audit.md) | M22 审计可观测 | audit_logs 查询(用户端 + admin) |
| [Subscription](./subscription.md) | 订阅与配额 | 方案列表/当前方案/配额状态 |
| [Content](./content.md) | Resources & Help | 资源列表/详情/FAQ 分类/搜索 |

**Base URL**: `/api/v1`

**认证**: 所有端点(除标注外)需要 `Authorization: Bearer <token>` header。沿用 Phase 1 JWT 机制。

**RLS**: 用户级端点通过 `SET app.user_id` 自动过滤。admin 端点通过 `User.role = 'admin'` 鉴权。

**错误格式** (沿用 Phase 1):
```json
{
  "detail": "错误描述",
  "code": "ERROR_CODE"
}
```
