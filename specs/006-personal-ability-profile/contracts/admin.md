# Admin View Contract

## 1. `GET /api/v1/ability-profile/admin/{user_id}`

**用途**:管理员只读查看指定用户的能力画像。

**Auth**: Bearer access + admin role

**响应 200**: 同 `/api/v1/ability-profile/dashboard` 的响应结构。

**说明**:
- 该端点返回的数据结构与用户端 dashboard 完全一致
- 响应中额外包含 `viewed_user_id` 和 `viewed_user_name` 字段,方便管理员识别
- 所有编辑/删除/分享管理操作在 UI 层面不可见(FR-017)
- 每次访问记录结构化日志: `ability_profile.admin_viewed`

**错误**:
| 状态码 | 场景 |
|---|---|
| 403 | 非管理员用户调用此端点 |
| 404 | 目标用户不存在 |

## 权限校验

管理员角色由现有鉴权系统的角色检查机制判定。当前项目标准:
- `user.role = 'admin'` 在 JWT claims 或 DB 中标记
- 本端点通过 `require_admin` 依赖注入保护
- 非管理员调用返回 403
