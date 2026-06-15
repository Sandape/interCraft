# Content Contract: Resources & Help

## GET /api/v1/resources

获取资源列表(仅已发布)。

| Parameter | Type | Default | Description |
|---|---|---|---|
| `category` | string | - | Filter: `interview_tips`/`resume_guide`/`tech_prep` |
| `tag` | string | - | Filter by tag |
| `content_type` | string | - | Filter: `article`/`video`/`template` |
| `limit` | int | 20 | 每页条数 |
| `offset` | int | 0 | 分页偏移 |

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "系统设计面试准备指南",
      "summary": "覆盖常见系统设计题目的解题框架和最佳实践",
      "category": "tech_prep",
      "tags": ["系统设计", "面试准备"],
      "content_type": "article",
      "read_time_minutes": 15,
      "sort_order": 1,
      "created_at": "2026-06-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

## GET /api/v1/resources/{id}

获取资源详情。

**Response 200**:
```json
{
  "id": "uuid",
  "title": "系统设计面试准备指南",
  "summary": "覆盖常见系统设计题目的解题框架和最佳实践",
  "category": "tech_prep",
  "tags": ["系统设计", "面试准备"],
  "content_type": "article",
  "content": "# 系统设计面试准备\n\n## 核心框架\n...",
  "read_time_minutes": 15,
  "related_resources": [
    {"id": "uuid", "title": "相关资源标题"}
  ],
  "created_at": "2026-06-01T00:00:00Z"
}
```

**Errors**: 404 (not found / not published)

---

## GET /api/v1/help/faq

获取 FAQ 列表。

| Parameter | Type | Default | Description |
|---|---|---|---|
| `category` | string | - | Filter: `account`/`interview`/`resume`/`subscription`/`technical` |

**Response 200**:
```json
{
  "categories": [
    {
      "category": "account",
      "label": "账号相关",
      "items": [
        {
          "id": "uuid",
          "question": "如何注销账号?",
          "category": "account",
          "sort_order": 1
        }
      ]
    }
  ]
}
```

---

## GET /api/v1/help/faq/{id}

获取 FAQ 详情(含答案)。

**Response 200**:
```json
{
  "id": "uuid",
  "question": "如何注销账号?",
  "answer": "前往 **Settings → 安全** 点击「注销账号」,经过 7 天冷静期后,系统将在 90 天后自动清除您的数据。冷静期内可随时取消。",
  "category": "account",
  "sort_order": 1,
  "created_at": "2026-06-01T00:00:00Z"
}
```

---

## GET /api/v1/help/search

搜索 FAQ 和资源。

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | string | (required) | 搜索关键词 |
| `scope` | string | `all` | `faq`/`resources`/`all` |
| `limit` | int | 10 | 每页条数 |

**Response 200**:
```json
{
  "faq": [
    {
      "id": "uuid",
      "question": "如何注销账号?",
      "category": "account",
      "score": 0.95
    }
  ],
  "resources": [
    {
      "id": "uuid",
      "title": "系统设计面试准备指南",
      "category": "tech_prep",
      "score": 0.85
    }
  ]
}
```
