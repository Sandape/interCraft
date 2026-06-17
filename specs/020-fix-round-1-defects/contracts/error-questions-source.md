# Contract: Error Questions — Source Fields (FIX-001 / FIX-003 / FIX-004 / FIX-005)

This contract supersedes §2 of
`specs/019-cross-module-linking/contracts/error-questions-source.md` for the
fields below. Other sections of the 019 contract remain valid.

## 1. Affected Defects

| Defect | Issue | Fix |
|---|---|---|
| D-002 (P0) | `CreateErrorQuestionInput` silently drops `source_session_id` and `source_question_id` on POST. | Add the fields to the Pydantic schema (`data-model.md` §3). |
| D-003 (P1) | `clear-source` is `POST` in implementation, `PATCH` in contract. | Backend implements `PATCH`; frontend migrated. |
| D-004 (P1) | Filter param is `?filter[source]=` in implementation, `?source=` in contract. | Both accepted; `?source=` is canonical. |
| D-013 (P1) | `clear-source` is not idempotent — second call returns 200 instead of `400 source_already_cleared`. | Service-layer pre-check (this contract §3.2). |

## 2. Write Schema (FIX-001)

`POST /api/v1/error-questions`

Request body:

```json
{
  "dimension": "communication",
  "question_text": "请描述一下 TCP 三次握手",
  "answer_text": "客户端发送 SYN, 服务端返回 SYN+ACK, 客户端再 ACK",
  "reference_answer_md": "标准答案见 RFC 793",
  "score": 4,
  "tags": ["network", "tcp"],
  "source_session_id": "11111111-1111-1111-1111-111111111111",
  "source_question_id": "22222222-2222-2222-2222-222222222222"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `dimension` | string | yes | unchanged |
| `question_text` | string | yes | unchanged |
| `answer_text` | string \| null | no | unchanged |
| `reference_answer_md` | string \| null | no | unchanged |
| `score` | int \| null | no | unchanged |
| `tags` | string[] \| null | no | unchanged |
| `source_session_id` | UUID \| null | no | **NEW in 020** — nullable UUID; round-trips |
| `source_question_id` | UUID \| null | no | **NEW in 020** — nullable UUID; round-trips |

Response body (201): same as 019 contract §1.1, with the two new fields
populated when supplied.

## 3. Clear-Source Endpoint (FIX-003, FIX-004)

### 3.1 Method and Path

`PATCH /api/v1/error-questions/{id}/clear-source`

Replaces the previous `POST` form. `POST` is removed from the backend (returns
`405 Method Not Allowed`). The frontend `useErrorQuestionMutations.ts` is
updated to call `PATCH`.

### 3.2 Idempotency (FIX-003)

The endpoint is **idempotent in the strong sense**: only the first call
mutates state; subsequent calls are rejected with a typed error.

| State before call | Response | DB after call |
|---|---|---|
| `source_session_id` or `source_question_id` non-NULL | `200 OK` with the updated error question | both `source_*` set to `NULL` |
| Both `source_session_id` and `source_question_id` already `NULL` | `400 Bad Request` with `{"error": {"code": "source_already_cleared", "message": "..."}}` | unchanged |

### 3.3 Implementation Sketch (Backend)

```python
@router.patch("/{id}/clear-source", response_model=ErrorQuestionOut)
async def clear_source(id: UUID, user: CurrentUser, svc: ErrorService = Depends()):
    return await svc.clear_source(id, user.id)
```

```python
# backend/app/modules/errors/service.py
async def clear_source(self, id: UUID, user_id: UUID) -> ErrorQuestion:
    current = await self.repo.get(id, user_id)
    if current is None:
        raise HTTPException(status_code=404, detail="not_found")
    if current.source_session_id is None and current.source_question_id is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "source_already_cleared",
                    "message": "该错题已经没有自动来源",
                }
            },
        )
    return await self.repo.clear_source(id, user_id)
```

## 4. Source Filter (FIX-005)

`GET /api/v1/error-questions?source=auto|manual|all`

The query parameter is `source` (canonical) **or** `filter[source]`
(deprecated alias). The response is identical for both. The frontend
`ErrorQuestionRepository.ts` is migrated to `?source=` and the `filter[...]`
alias will be removed in a future release.

| Value | Meaning | SQL filter |
|---|---|---|
| `auto` | auto-deposited from interview | `source_session_id IS NOT NULL` |
| `manual` | hand-entered by user | `source_session_id IS NULL` |
| `all` (default) | no filter | (no extra clause) |

## 5. Test Cases (Round-2)

| ID | File | Description | Anchor |
|---|---|---|---|
| STRICT-01 | `tests/e2e/round-2/pydantic-strictness.spec.ts` | POST with valid `source_session_id` and `source_question_id` → 201 and response includes the values. | FIX-001 |
| STRICT-02 | `tests/e2e/round-2/pydantic-strictness.spec.ts` | GET the same record → 200 and `source_session_id` non-NULL. | FIX-001 |
| CONTRACT-01 | `tests/e2e/round-2/contract-parity.spec.ts` | `PATCH /error-questions/{id}/clear-source` → 200 and source fields NULL. | FIX-004 |
| CONTRACT-02 | `tests/e2e/round-2/contract-parity.spec.ts` | Second `PATCH clear-source` on the same id → 400 `source_already_cleared`. | FIX-003 |
| CONTRACT-03 | `tests/e2e/round-2/contract-parity.spec.ts` | `GET /error-questions?source=auto` → only rows with `source_session_id IS NOT NULL`. | FIX-005 |
| CONTRACT-04 | `tests/e2e/round-2/contract-parity.spec.ts` | `GET /error-questions?source=manual` → only rows with `source_session_id IS NULL`. | FIX-005 |
| CONTRACT-05 | `tests/e2e/round-2/contract-parity.spec.ts` | `GET /error-questions` (no filter) → both kinds present. | FIX-005 |
| D4 (Round-1) | `tests/e2e/round-1/full-error-source.spec.ts` | Same as CONTRACT-02 but via UI; rerun for regression. | FIX-003 |
| D5 (Round-1) | `tests/e2e/round-1/full-error-source.spec.ts` | Clear-source then assert badge disappears; rerun for regression. | FIX-008 |
| S5 (Round-1) | `tests/e2e/round-1/smoke.spec.ts` | Auto-deposit round produces a row with source fields; rerun for regression. | FIX-001 |

## 6. Migration Notes

- The FastAPI alias for `?source=` is `Query(alias="source")` with a
  Pydantic `Field(alias="filter[source]")` fallback. Both work; logging a
  `DeprecationWarning` (not user-facing) for the bracket form is a
  follow-up.
- The `POST /api/v1/error-questions/{id}/clear-source` route is removed in
  the same commit. The frontend has its own mutation function; only the
  HTTP verb changes.
