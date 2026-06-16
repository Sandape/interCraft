# Share Link Contracts

## 1. `POST /api/v1/ability-profile/share`

**用途**:生成新的分享链接。

**Auth**: Bearer access

**请求体**:
```json
{
  "pin": "1234",
  "expires_in_hours": 48
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pin` | string(4) | 否 | 4 位数字 PIN;不填则无密码 |
| `expires_in_hours` | int(1-720) | 否 | 过期时间;不填则永不过期 |

**校验**:
- `pin`: 若传,必须为 4 位数字
- `expires_in_hours`: 1-720 范围(30 天)

**响应 201**:
```json
{
  "data": {
    "id": "uuid-v7",
    "token": "uuid-v7",
    "url": "https://example.com/shared/uuid-v7",
    "has_pin": true,
    "expires_at": "2026-06-18T10:00:00Z",
    "created_at": "2026-06-16T10:00:00Z"
  }
}
```

**业务规则**:
- 每人活跃(未撤销+未过期)分享链接 ≤ 10
- 超过限制时返回 429 + "Active share links limit reached"

---

## 2. `GET /api/v1/ability-profile/share`

**用途**:列出当前用户的所有分享链接(含已撤销/已过期)。

**Auth**: Bearer access

**响应 200**:
```json
{
  "data": [
    {
      "id": "uuid-v7",
      "token": "uuid-v7",
      "url": "https://example.com/shared/uuid-v7",
      "has_pin": true,
      "expires_at": "2026-06-18T10:00:00Z",
      "revoked_at": null,
      "access_count": 5,
      "last_accessed_at": "2026-06-16T12:00:00Z",
      "status": "active",
      "created_at": "2026-06-16T10:00:00Z"
    }
  ]
}
```

`status` 枚举: `active` / `expired` / `revoked`

---

## 3. `DELETE /api/v1/ability-profile/share/{id}`

**用途**:撤销指定的分享链接。

**Auth**: Bearer access

**响应 204**: 无内容

**说明**:逻辑撤销(设置 `revoked_at = now()`),不物理删除。

---

## 4. `GET /api/v1/ability-profile/share/{token}`

**用途**:公开访问分享的能力画像(无认证)。

**Auth**: 无

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pin` | string(4) | 否 | PIN 验证;若链接设置了 PIN 则必填 |

**响应 200**:
```json
{
  "data": {
    "owner": {
      "name": "张三",
      "title": "高级后端工程师"
    },
    "generated_at": "2026-06-16T10:00:00Z",
    "dimensions": [
      {
        "key": "tech_depth",
        "label_zh": "技术深度",
        "actual_score": 6.5
      }
    ]
  }
}
```

**错误**:
| 状态码 | 场景 |
|---|---|
| 404 | token 不存在/已撤销/已过期 |
| 401 | PIN 缺失或不正确(如果设置了 PIN) |

**副作用**:
- 记录 `profile_views` 行(ip_prefix, user_agent, pin_verified)
- 更新 `profile_share_links.last_accessed_at` 和 `access_count`

**速率限制**: 同一 IP 10 次/分钟
