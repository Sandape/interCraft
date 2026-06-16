# API Contracts: Personal Ability Profile

| Contract | File | Description |
|---|---|---|
| Dashboard | [profile.md](./profile.md) | 能力画像仪表盘(聚合 + 趋势) |
| Share Link | [share.md](./share.md) | 分享链接 CRUD + 公开访问 |
| PDF Export | [export.md](./export.md) | PDF 导出触发 + 状态查询 |
| Admin View | [admin.md](./admin.md) | 管理员跨用户查看 |

**Base Path**: `/api/v1/ability-profile`

**Auth**: Bearer access (except `/share/{token}` = 无认证)

**Error Codes**: 遵循项目标准 — 401/403/404/422/429/500

**RLS**: 全部写路径强制 `SET LOCAL app.user_id`
