# HTTP API Contracts — REQ-048

**Date**: 2026-07-07
**Purpose**: Document HTTP endpoints added/modified by Interview Mode Split + Doubao Card Export

---

## C-1. POST /api/v1/interviews — Start Interview (modified)

> Existing endpoint, extended for mode selection.

### Request

```json
{
  "position": "高级前端工程师",
  "company": "字节跳动",
  "branch_id": "uuid | null",
  "job_id": "uuid | null",
  "difficulty": "medium",
  "mode": "quick_drill | full | doubao",
  "max_questions": 10 | 15,           // only when mode=full; ignored for quick_drill/doubao
  "use_variants": true | false         // only when mode=quick_drill; default false (R22: 不传或 false 必须走原题重考 — FR-031 合同硬约束)
}
```

### Response 200

```json
{
  "session_id": "uuid",
  "thread_id": "uuid",
  "mode": "quick_drill",
  "max_questions": 5,                  // forced for quick_drill
  "error_question_ids": ["uuid", ...], // only when quick_drill
  "next_step": "interview_live"        // | "card_preview" for doubao
}
```

### Response 422

```json
{
  "detail": [{
    "loc": ["body", "mode"],
    "msg": "INSUFFICIENT_ERROR_POOL",
    "ctx": {"available": 3, "required": 5}
  }]
}
```

**Validation**:
- `mode='quick_drill'` + user error_count < 5 → 422 `INSUFFICIENT_ERROR_POOL`
- `mode='full'` + `max_questions` not in [10, 15] → 422 `INVALID_MAX_QUESTIONS`
- `mode='doubao'` + `use_variants=true` → 422 `INVALID_COMBINATION` (变体仅 quick_drill 适用)

> **豆包模式 session 行说明**：当 `mode='doubao'` 时，`interview_sessions` 表**仍创建 1 行**（用于响应中 `session_id` 回传前端调 `/api/v1/interviews/{session_id}/card`），MODE_GUARD 在 Planner 子图完成后立即早停，**不进入** `question_gen` / `score_llm` / `report` 节点。

---

## C-2. GET /api/v1/interviews/{session_id}/card — Doubao Card Render (new)

> Renders a JD + InterviewPlan card for 「豆包面试」mode.

### Request Query

| Param | Type | Default | Notes |
|---|---|---|---|
| `size_variant` | `4_3 \| 9_16` | `4_3` | 4:3 (1080×810) or 9:16 (1080×1920) |
| `format` | `jpg \| png` | `jpg` | PNG 用于设计 review，JPG 用于下载 |
| `cache_key` | `string \| null` | session_id | 复用已渲染的卡片 |

### Response 200

```
Content-Type: image/jpeg
Content-Length: <bytes>
Content-Disposition: attachment; filename="doubao-card-{session_id}-4x3.jpg"
X-Card-Render-Duration-Ms: 1245
X-Card-Size-Variant: 4_3
X-Card-Cache-Hit: false
Cache-Control: public, max-age=604800

<binary JPEG data>
```

### Response 422 (Planner not ready)

```json
{"detail": "INTERVIEW_PLAN_NOT_READY"}
```

### Response 500 (render failure)

```json
{"detail": "CARD_RENDER_FAILED", "trace_id": "uuid"}
```

**Side effect**:
- INSERT INTO analytics_events (event_type='doubao_card_rendered', payload={size_variant, duration_ms, cache_hit, file_size_bytes})

---

## C-3. POST /api/v1/interviews/quick-drill/preview — Preview Drill Selection (new)

> Lets the user see which 5 questions would be selected before committing. Returns dimension distribution and JD alignment score.

### Request

```json
{
  "job_id": "uuid | null",
  "position": "高级前端工程师",
  "company": "字节跳动"
}
```

### Response 200

```json
{
  "candidates": [
    {
      "source_question_id": "uuid",
      "dimension": "tech_depth",
      "question_text_preview": "请描述 React Hooks 的实现原理...",
      "score": 4,
      "last_practiced_at": "2026-07-01T10:30:00Z",
      "jd_alignment_score": 0.87
    }
  ],
  "dimension_distribution": {"tech_depth": 2, "architecture": 2, "engineering_practice": 1},
  "cache_key": "drill_cache:{user_id}:{key_hex}",  // R18: key_hex = sha256(jd_text + error_pool_hash)[:32]
  "cache_ttl_seconds": 300
}
```

---

## C-4. GET /api/v1/interviews/mode-recommendation — Recommend Mode (new)

> Optionally suggest mode based on user history (e.g., "你最近 3 次面试有 8 道错题，建议尝试快速补漏").

### Response 200

```json
{
  "recommended_mode": "quick_drill",
  "error_count": 8,
  "recent_low_score_count": 5,
  "rationale_zh": "你最近 3 次面试有 5 道低分错题（<6 分），建议快速补漏",
  "rationale_en": "You have 5 low-scoring error questions (<6) in recent interviews; quick_drill recommended."
}
```

---

## C-5. Embedding Service Internal HTTP API (new sub-service)

> Independent Python process, called by FastAPI via internal HTTP.

### POST /embed

**Request**:
```json
{"texts": ["string1", "string2", ...], "model": "bge-small-zh-v1.5"}
```

**Response 200**:
```json
{
  "embeddings": [[0.012, -0.034, ...], ...],  // list of 512-dim vectors
  "model": "bge-small-zh-v1.5",
  "duration_ms": 234
}
```

**Response 503** (model not loaded): `{"detail": "MODEL_NOT_LOADED"}`

### POST /rerank

**Request**:
```json
{
  "query": "分布式事务",
  "documents": [{"id": "uuid", "text": "如何解决分布式事务的一致性问题？"}, ...],
  "model": "bge-reranker-v2-m3"
}
```

**Response 200**:
```json
{
  "ranked": [
    {"id": "uuid", "score": 0.92},
    {"id": "uuid", "score": 0.87},
    ...
  ],
  "model": "bge-reranker-v2-m3",
  "duration_ms": 1123
}
```

### GET /health

**Response 200**:
```json
{"status": "ok", "models_loaded": ["bge-small-zh-v1.5", "bge-reranker-v2-m3"], "uptime_seconds": 12345}
```

---

## C-6. Card Render Service Internal HTTP API (new sub-service)

> Independent Node.js 22 process or FastAPI BackgroundTasks.

### POST /render

**Request**:
```json
{
  "interview_plan": {
    "target_company": "字节跳动",
    "target_position": "高级前端工程师",
    "interview_difficulty": "medium",
    "tech_stack": ["React", "TypeScript"],
    "focus_areas": [{"area": "技术深度 — React 底层原理", "weight": 0.3, "reason": "..."}],
    "suggested_questions": ["请描述 React Hooks 的实现原理", "..."],
    "tips": ["关注候选人实际决策过程"]
  },
  "requirements_md_summary": "本次面试基于岗位招聘需求生成题目。原始需求 (300 字):\n\n...",
  "size_variant": "4_3 | 9_16",
  "estimated_duration_minutes": 30
}
```

**Response 200**:
```json
{
  "image_base64": "iVBORw0KGgo...",
  "size_variant": "4_3",
  "file_size_bytes": 234567,
  "duration_ms": 1245,
  "rendered_at": "2026-07-07T12:34:56Z",
  "cache_hash": "sha256:abc123..."
}
```

---

## C-7. WebSocket Events (extended)

> Existing WS endpoint at `/api/v1/ws/interview/{session_id}`. Add new event types.

### Outbound: `interview.mode_selected`

```json
{
  "type": "interview.mode_selected",
  "session_id": "uuid",
  "mode": "quick_drill | full | doubao",
  "max_questions": 10 | 15 | 5 | null,
  "timestamp": "ISO8601"
}
```

### Outbound: `interview.drill_candidates_loaded`

```json
{
  "type": "interview.drill_candidates_loaded",
  "session_id": "uuid",
  "candidates": [{"source_question_id": "uuid", "dimension": "tech_depth"}, ...],
  "cache_hit": false,
  "duration_ms": 2345,
  "timestamp": "ISO8601"
}
```

### Outbound: `interview.card_ready` (doubao mode)

```json
{
  "type": "interview.card_ready",
  "session_id": "uuid",
  "image_url": "/api/v1/interviews/{session_id}/card?size_variant=4_3",
  "size_variant": "4_3",
  "file_size_bytes": 234567,
  "timestamp": "ISO8601"
}
```

---

## C-8. Error Codes (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `INSUFFICIENT_ERROR_POOL` | 422 | quick_drill 模式错题数 < 5 |
| `INVALID_MAX_QUESTIONS` | 422 | full 模式 max_questions 不在 [10, 15] |
| `INVALID_COMBINATION` | 422 | doubao + use_variants=true 等无效组合 |
| `INTERVIEW_PLAN_NOT_READY` | 422 | Planner 子图未完成，无法生成卡片 |
| `CARD_RENDER_FAILED` | 500 | 卡片渲染服务故障 |
| `EMBEDDING_SERVICE_DOWN` | 503 | embedding service 健康检查失败 |
| `RERANK_SERVICE_DOWN` | 503 | reranker service 健康检查失败（已降级） |