# User Profile Endpoints (M04)

> 用户资料(基础字段)的读写。敏感凭据(`user_credentials`)Phase 1 不开放 API,Phase 2 启用。

## 共享类型

```ts
type PublicUser = {
  id: string;               // uuid v7
  email: string;            // 只读
  display_name: string | null;
  title: string | null;
  years_of_experience: number | null;
  target_role: string | null;
  bio: string | null;
  subscription: "free" | "pro" | "enterprise";
  created_at: string;       // ISO 8601
  updated_at: string;
}

type PatchUser = {
  display_name?: string;
  title?: string;
  years_of_experience?: number;
  target_role?: string;
  bio?: string;
}
```

---

## 1. `GET /api/v1/users/me`

**用途**:取当前用户(供前端启动时拉一次)。

**Auth**:Bearer access

**响应 200**:
```json
{
  "user": { /* PublicUser */ }
}
```

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 / token 失效 |
| 404 | `user.not_found` | user 已被软删(理论上不会,401 优先) |

---

## 2. `PATCH /api/v1/users/me`

**用途**:更新基础资料。**不能**改 email / password / subscription(各自有专门端点,Phase 1 暂未实现)。

**Auth**:Bearer access

**请求**:
```json
{
  "display_name": "林浩然",
  "title": "高级前端工程师",
  "years_of_experience": 3,
  "target_role": "高级前端工程师",
  "bio": "5 年前端工程经验，关注工程化与性能优化。"
}
```

**字段校验**:
| 字段 | 规则 | 错误码 |
|---|---|---|
| `display_name` | ≤ 64 字符 | `validation.range` |
| `title` | ≤ 128 字符 | `validation.range` |
| `years_of_experience` | 0-50 整数 | `validation.range` |
| `target_role` | ≤ 128 字符 | `validation.range` |
| `bio` | ≤ 1000 字符 | `validation.range` |

**响应 200**:
```json
{
  "user": { /* 更新后的 PublicUser */ }
}
```

**错误**:
| 状态 | code | 触发 |
|---|---|---|
| 401 | `auth.token_*` | 未登录 |
| 422 | `validation.*` | 字段校验失败 |

---

## 3. `PATCH /api/v1/users/me/credentials` *(Phase 2 启用,Phase 1 仅落表)*

> Phase 1 不实现此端点。Phase 2 启动时按 M04 §4 + spec FR-005 实现,加解密走 `app/core/crypto.py`。
> 预期响应 schema:
```json
{
  "user_credentials": {
    "id_card_masked": "110***********1234",
    "real_name_masked": "林**",
    "salary_range": "30-50k"
  }
}
```

## 4. `POST /api/v1/auth/oauth/{provider}/callback` *(MVP 不实现,留占位)*

> OOS-6:第三方 OAuth 不在 Phase 1。Phase 1 仅在 `app/modules/auth/api.py` 留空路由(返回 501),Phase 1.5+ 评估。
> 占位响应:返回 501 Not Implemented
```json
{
  "error": {
    "code": "not_implemented",
    "message": "第三方登录暂未启用",
    "request_id": "..."
  }
}
```
