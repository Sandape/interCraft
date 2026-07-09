---
req_id: REQ-034-US8
title: Backend: ship-readiness validation of 5 v2 endpoints (analyze / duplicate / sharing / statistics / public)
status: locked
round: 1
locked_at: 260629 2200
locked_by: negotiation
negotiation_rounds: 1
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
source_gap: memory/req_032_v2_repo_stub_trap.md + 032 ship 时 stub 盘点 + 2026-06-29 actual code 状态盘点
moderation_log: "Round 1: tester red-team 10 反例 (3 blocker / 4 major / 3 minor) — main-agent 10/10 接受，R10 范围澄清 (US8 = ship-readiness validation, 0 stub 在线), 10 修订编码 Phase 2 Implementation Spec 段"
scope_cast: "US8 实际范围 = 5 endpoint [analyze, duplicate, sharing, statistics, public] ship-readiness 验证; spec 行 42 '5 501-stub' 描述过期 (032 Batch 5 已 ship 真实实现, 0 stub 在线); CRUD endpoint ship-readiness 走 11 pytest 文件 (US8 范围外); AI enhancement 不在范围 per spec out-of-scope"
---

# Acceptance Matrix for REQ-034-US8 — Backend replace 5 501-stub endpoints with real implementations

## SC Gaps

- spec.md 行 42 给出 US8 标题"Backend: replace 5 501-stub endpoints with real implementations (analyze / AI enhancement / etc.)" + 来源 `app/modules/resumes_v2/api.py:501 stubs` + 0.5 d + P0。spec §"Acceptance criteria"段（行 64-66）整体写 TBD，未提供具体 SC 编号供 AC 反向溯源。下表来源以"行 42 隐含"标记。
- **范围修正（重要 — 实际 0 stub）**：2026-06-29 实施时 `app/modules/resumes_v2/api.py` 实际状态盘点：
  - **api.py:14 个 endpoint 全部已 ship 真实实现** — list / create / get / update / delete / lock / duplicate / sharing / statistics / analyze (POST) / analysis (GET) / public_view / public_verify_password / public_pdf / export_render（统计共 14 个 + export_render 共 15 个；14 个 resume CRUD 路径 + 1 export 路径 = 15 个）
  - **0 个 501-stub endpoint 在线** — `grep "HTTP_501_NOT_IMPLEMENTED" backend/app/modules/resumes_v2/api.py` 仅 1 hit，在 line 49 的 `_not_implemented()` helper 函数定义体（unused dead code）
  - **0 个 `raise NotImplementedError` 在 repository.py** — `grep "NotImplementedError" backend/app/modules/resumes_v2/repository.py` 0 hits
  - **service.py: 所有方法已 ship** — `create_resume` / `get_resume` / `update_resume` / `delete_resume` / `duplicate_resume` / `set_sharing` / `ensure_statistics_row` / `emit_public_changed` / `analyze_resume` / `get_analysis` / `emit_analysis_completed` 全部真实实现
  - **测试覆盖** — `tests/test_api.py` (T018) + `tests/test_duplicate.py` + `tests/test_analysis.py` + `tests/test_export.py` + `tests/test_public.py` + `tests/test_statistics.py` + `tests/test_sse.py` + `tests/test_us1_e2e.py` + `tests/test_legacy_format.py` + `tests/test_models.py` + `tests/test_repository.py` 共 11 文件已 ship
- **范围修正理由**：spec.md 起草时（2026-06-29 早于 032 Batch 5 ship）有 5 个 501-stub。032 Batch 5 实施时（commit 6354d14 "feat(032): REQ-032 v2 Batch 5 implement ResumeV2Repository"）已将 5 个 endpoint + repository 全部 ship 真实实现。**当前实际 US8 范围 = 0 个 stub 待替换**。Spec 描述与代码状态不一致，**本 AC 矩阵 cast 此范围修正 = 0 stub**。
- **实际 US8 范围 = ship-readiness 验证**（按 [req_032_v2_repo_stub_trap] 教训：ship 前必须 HTTP probe 验证）：
  - SC-8A: **HTTP probe 验证套件** — 0 个 501 stub 在线（`grep` 静态断言 + `curl` 实际请求 + tests 跑通验证）
  - SC-8B: **analyze endpoint 真实 LLM 调用** — DeepSeek V4 Pro 真实接通，3× retry + UPSERT + `analysis.completed` SSE
  - SC-8C: **analyze endpoint 失败路径** — LLM 3 次 retry 全部失败时，store `status='failed'` + `failure_reason` + 不抛 500
  - SC-8D: **get_analysis 真实读 path** — UPSERT 后 1 row 持久化，GET 返回最新 row（not None）
  - SC-8E: **duplicate endpoint 真实 copy** — deep-copy data + new UUIDv7 + `<orig>-copy-N` slug + `（副本）` zh-CN suffix + statistics/analysis 不复制
  - SC-8F: **export/render 真实 render** — PDF/PNG/JPEG 走 027 export gateway `render_resume`，JSON 走 row.data 直接返
  - SC-8G: **sharing endpoint 真实 bcrypt** — 6..64 chars password + bcrypt cost 12 + `is_public=false` 时禁止 password hash
  - SC-8H: **statistics endpoint 真实读 + views/downloads 增量** — public 路径增加 views/downloads，owner 不增（已 ship 实施）
  - SC-8I: **public PDF 真实 content 返回** — 返回 `data` + `render_url` 给客户端
  - SC-8J: **public verify-password 真实 bcrypt 校验** — 错密码返 401 INVALID_PASSWORD
- **跨 endpoint 共享模式**：
  - SC-8K: RLS 鉴权 — 所有 authenticated endpoint 用 `db_session_user_dep`（绑定 `app.user_id` GUC），所有 public endpoint 用 `get_db_session_no_rls`，跨用户读返 404（非 403，避免泄漏存在性）
  - SC-8L: Postgres 落库验证（per [feedback_postgres_mcp_validation]）— 写操作必须用 `mcp__postgres__query` 实查 `resumes_v2` / `resume_statistics_v2` / `resume_analysis_v2` 三张表
  - SC-8M: 错误信封 — 4xx 全部 `{"error": code, "message": ...}` flat shape（沿用 US1 contract），不走全局 `HTTPException` 包装
  - SC-8N: 后端 pytest — 沿用 US5 R6 精简模式：每 endpoint 至少 1 happy path 子 case，跨 ownership/RLS 1 个反向 case，integrity edge 1 个

## AC 矩阵

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-01 | static | **0 个 501-stub 在线**（范围修正）— `git grep -n "HTTP_501_NOT_IMPLEMENTED" backend/app/modules/resumes_v2/api.py` 仅 line 49 helper 函数定义体内 1 hit（dead code unused），无 endpoint 真正返回 501；`git grep -rn "raise NotImplementedError" backend/app/modules/resumes_v2/` 期望 0 hits（repository.py + service.py + api.py 全部 ship） | (1) `git grep -n "HTTP_501_NOT_IMPLEMENTED" backend/app/modules/resumes_v2/api.py` 期望 line 49 唯一 1 hit + 该 line 在 `def _not_implemented()` 函数体（def line 46-54）内（unused dead code）；(2) `git grep -rn "raise NotImplementedError" backend/app/modules/resumes_v2/` 期望 0 hits；(3) `git grep -n "return _not_implemented(" backend/app/modules/resumes_v2/api.py` 期望 0 hits（helper 函数未被调用） | 0 endpoint 返 501 + 0 NotImplementedError + helper dead code 标记保留或删除（dev 自由发挥） | SC-8A + spec 范围修正 + 实际代码盘点 |
| AC-02 | happy | **analyze endpoint 真实 LLM 调用**（P0）— `POST /api/v1/v2/resumes/{id}/analyze` 真实接通 DeepSeek V4 Pro（per phase4_llm_config memory）：3× retry + 1s/2s/4s 指数退避 + DeepSeek 返回 `\`\`\`json ... \`\`\`` 时 strip fence + UPSERT `resume_analysis_v2` + emit `analysis.completed` SSE + 200 `{status, analysis, failure_reason, updated_at}` | (1) pytest `pytest backend/app/modules/resumes_v2/tests/test_analysis.py -k "analyze" -v` 期望 ≥ 3 子 case 全 pass（happy + retry exhaustion + invalid JSON fence）；(2) HTTP probe (test rig) `curl -X POST -H "Authorization: Bearer $JWT" /api/v1/v2/resumes/$RID/analyze` 期望 200 + `status in {"success", "failed"}` + `analysis.overallScore` 是 0..100 整数；(3) `mcp__postgres__query "SELECT status, analysis, failure_reason FROM resume_analysis_v2 WHERE resume_id='$RID'"` 期望 1 row（per [feedback_postgres_mcp_validation]） | analyze 真实接通 DeepSeek + 3 retry + UPSERT 落库 + SSE emit | SC-8B + spec analyze 真实实施 + phase4_llm_config memory |
| AC-03 | happy | **analyze retry 3 次失败路径**（P0）— 当 DeepSeek 持续返 429/5xx（mock LLM client 抛 `LLMInvokeError` 3 次）时，service 捕获最后 exception 存 `status='failed'` + `failure_reason` + 返 200（不抛 500）+ UI 可显示 error | (1) `pytest backend/app/modules/resumes_v2/tests/test_analysis.py -k "retry or failure or failed" -v` 期望 ≥ 2 子 case 全 pass；(2) 静态断言 `git grep -n "for attempt in range(3)" backend/app/modules/resumes_v2/service.py` 期望 1 hit + `await asyncio.sleep(2 ** attempt)` 期望 1 hit（1s/2s 退避，第 3 次失败后 store failed row 不 sleep）；(3) 静态断言 `git grep -n "upsert_analysis" backend/app/modules/resumes_v2/service.py` 期望 ≥ 2 hits（成功 + 失败 2 path 都调） | analyze 3 retry 失败 → 200 + status=failed + failure_reason | SC-8C + spec 失败路径 + 032 ship 时 T152 实施记录 |
| AC-04 | happy | **get_analysis 真实读 path**（P0）— `GET /api/v1/v2/resumes/{id}/analysis` 从 `resume_analysis_v2` 表 UPSERT 后 1 row 持久化，GET 返回最新 row（含 `analysis.overallScore`）；never-analyzed 返 404 NOT_FOUND（不是 200 + null） | (1) `pytest backend/app/modules/resumes_v2/tests/test_analysis.py -k "get_analysis or never_analyzed" -v` 期望 ≥ 2 子 case 全 pass；(2) HTTP probe `curl -H "Authorization: Bearer $JWT" /api/v1/v2/resumes/$RID/analysis`（先 POST analyze 成功）期望 200 + body 含 `analysis.overallScore >= 0`；never-analyzed resume 期望 404 + `{"error": "NOT_FOUND", ...}` | GET analysis 真实读 row + 404 未分析 | SC-8D + US8 spec 真实实施 + test_analysis.py 锁契约 |
| AC-05 | happy | **duplicate endpoint 真实 copy**（P0）— `POST /api/v1/v2/resumes/{id}/duplicate` deep-copy `data` JSONB + 新 UUIDv7 + `<orig>-copy-N` slug（N = 1 + max existing N）+ name suffix `（副本）` for `zh-CN` Accept-Language else ` (Copy)` + `is_public=false` + `is_locked=false` + `password_hash=null` + version=0 + statistics/analysis row **不**复制 | (1) `pytest backend/app/modules/resumes_v2/tests/test_duplicate.py -v` 期望 ≥ 4 子 case 全 pass（happy + zh-CN suffix + slug N increment + statistics/analysis 不复制）；(2) HTTP probe `curl -X POST -H "Accept-Language: zh-CN" -H "Authorization: Bearer $JWT" /api/v1/v2/resumes/$RID/duplicate` 期望 200 + body 含 `name.endswith("（副本）")` + 新 resume id != 旧 + 新 slug 匹配 `^<orig>-copy-\d+$`；(3) `mcp__postgres__query "SELECT id, slug, name, is_public, is_locked, version FROM resumes_v2 WHERE user_id='$UID' ORDER BY created_at"` 期望原 + 副本 2 row + 副本 is_public=false + version=0；(4) `mcp__postgres__query "SELECT resume_id FROM resume_statistics_v2 WHERE resume_id IN ('$RID', '$NEW_RID')"` 期望仅原 RID 1 row（statistics 不复制） | duplicate 真实 deep copy + zh-CN suffix + statistics/analysis 不复制 | SC-8E + spec + 032 T158 ship 实施 |
| AC-06 | happy | **export/render 真实 render**（P0）— `POST /api/v1/v2/export/render` 走 027 export gateway `render_resume`：format=json 返 row.data + `Content-Disposition: attachment`；format=pdf/png/jpeg 走 Playwright pipeline；content_size > 1_000_000 返 413 CONTENT_TOO_LARGE；空 html + pdf 返 400 EMPTY_CONTENT | (1) `pytest backend/app/modules/resumes_v2/tests/test_export.py -v` 期望 ≥ 5 子 case 全 pass（json + pdf + png + content_too_large + empty_content + ownership 403）；(2) HTTP probe `curl -X POST -H "Authorization: Bearer $JWT" -d '{"html":"<h1>test</h1>","format":"json","resume_id":"$RID"}' /api/v1/v2/export/render` 期望 200 + `Content-Type: application/json` + body 含 `metadata.template`；(3) `curl -X POST -H "Authorization: Bearer $JWT" -d '{"html":"","format":"pdf"}' /api/v1/v2/export/render` 期望 400 + `{"error": "EMPTY_CONTENT"}` | export 真实 render + content validation | SC-8F + spec + 032 T106 ship 实施 |
| AC-07 | happy | **sharing endpoint 真实 bcrypt**（P0）— `PUT /api/v1/v2/resumes/{id}/sharing` 当 password 是 string 时 6..64 chars 校验通过 + bcrypt cost 12 hash 存 `password_hash`；password 是 None 时清空 hash（要求 `is_public=true`，否则 400 INVALID_SHARING） | (1) `pytest backend/app/modules/resumes_v2/tests/test_public.py -k "sharing or password" -v` 期望 ≥ 4 子 case 全 pass（happy + 短密码 < 6 拒绝 + 长密码 > 64 拒绝 + is_public=false + password 拒绝）；(2) HTTP probe `curl -X PUT -H "Authorization: Bearer $JWT" -d '{"is_public":true,"password":"abc123"}' /api/v1/v2/resumes/$RID/sharing` 期望 200 + `password_set: true` + `public_url` 含 `/r/`；(3) `mcp__postgres__query "SELECT password_hash FROM resumes_v2 WHERE id='$RID'"` 期望 password_hash 以 `$2b$12$` 开头（bcrypt cost 12） | sharing 真实 bcrypt + password 校验 | SC-8G + spec + 032 T141 ship 实施 |
| AC-08 | state | **statistics endpoint 真实读 + views/downloads 增量**（P0）— `GET /api/v1/v2/resumes/{id}/statistics` 返 `{views, downloads, last_viewed_at, last_downloaded_at}`；is_public=false 返 0 + null timestamps；`public_view` + `public_pdf` 调 `increment_views` / `increment_downloads`（owner 访问不增） | (1) `pytest backend/app/modules/resumes_v2/tests/test_statistics.py -v` 期望 ≥ 3 子 case 全 pass（empty + 增量 views + 增量 downloads + owner 不增）；(2) HTTP probe 先 `curl /api/v1/v2/public/$USER/$SLUG`（非 owner）→ `curl -H "Authorization: Bearer $OWNER_JWT" /api/v1/v2/resumes/$RID/statistics` 期望 views=1, downloads=0 + `last_viewed_at` ISO timestamp；(3) `mcp__postgres__query "SELECT views, downloads, last_viewed_at FROM resume_statistics_v2 WHERE resume_id='$RID'"` 期望 views=1, downloads=0 | statistics 真实 + views/downloads 增量 | SC-8H + spec + 032 T145 ship 实施 |
| AC-09 | state | **public PDF 真实 content + public verify-password 真实 bcrypt 校验**（P0）— `GET /api/v1/v2/public/{u}/{s}/pdf` 返 `{resume_id, slug, data, render_url}` + 增 downloads；`POST /api/v1/v2/public/{u}/{s}/verify-password` 错密码返 401 INVALID_PASSWORD，正确密码设 HttpOnly cookie `v2_public_pw_{hash[:12]}`（10min Max-Age=600） | (1) `pytest backend/app/modules/resumes_v2/tests/test_public.py -k "public or verify or pdf" -v` 期望 ≥ 5 子 case 全 pass（public view 401 password_required + verify wrong password 401 + verify correct password 200 + pdf 401 password_required + owner view 不增 views）；(2) HTTP probe `curl /api/v1/v2/public/$USER/$SLUG/pdf` 期望 200 + body 含 `data.metadata.template` + `render_url="/api/v1/export/render"`；(3) `curl -X POST -d '{"password":"wrong"}' /api/v1/v2/public/$USER/$SLUG/verify-password` 期望 401 + `{"error": "PASSWORD_INVALID"}` + `Set-Cookie` 头**不**存在 | public 路径 + verify password + pdf | SC-8I + SC-8J + spec + 032 T142-T144 ship 实施 |
| AC-10 | edge | **RLS 鉴权 + 跨用户读 404**（P0 — 不可泄漏存在性）— 任何 authenticated endpoint（list / get / update / delete / duplicate / sharing / statistics / analyze / get_analysis）跨用户访问返 404 NOT_FOUND（**不**返 403 NOT_OWNER，避免泄漏简历存在性）；owner = `await svc.repo.get_owner_id()` 检查仅用于显式 lock endpoint 的 403 区分；public 路径不需 RLS（用 `get_db_session_no_rls`） | (1) `pytest backend/app/modules/resumes_v2/tests/test_api.py -k "not_owner or cross_user or 404" -v` 期望 ≥ 4 子 case 全 pass（GET 跨用户 404 + PUT 跨用户 404 + DELETE 跨用户 404 + analyze 跨用户 404）；(2) 静态断言 `git grep -n "db_session_user_dep" backend/app/modules/resumes_v2/api.py` 期望 ≥ 8 hits（authenticated endpoint 都用 RLS-bound session）+ `git grep -n "get_db_session_no_rls" backend/app/modules/resumes_v2/api.py` 期望 ≥ 3 hits（public 路径不绑 RLS）；(3) HTTP probe `curl -H "Authorization: Bearer $OTHER_JWT" /api/v1/v2/resumes/$RID` 期望 404 + `{"error": "NOT_FOUND"}`（**不**是 403） | RLS 鉴权 + 跨用户 404 + public 路径无 RLS | SC-8K + spec + US1 鉴权模式 + 032 RLS 实施 |
| AC-11 | edge | **错误信封统一**（P0）— 4xx 错误全部 `{"error": code, "message": ...}` flat shape（**不**走全局 `HTTPException` 包装成 `{"error": {"code", "message"}}` 嵌套）；`ServiceError` 是唯一错误源，`to_response()` 转 JSONResponse；5xx 返 `{"error": "RENDERING_FAILED", ...}` 等具体 code | (1) 静态断言 `git grep -n "raise HTTPException" backend/app/modules/resumes_v2/api.py` 期望 0 hits（**不**用全局 HTTPException）+ `git grep -n "from fastapi import" backend/app/modules/resumes_v2/api.py` 期望 HTTPException 出现（import 了但不用作 raise）作为 dead import；(2) HTTP probe 各 endpoint 失败 case 期望 body shape 一致：POST 错 slug → `{"error": "INVALID_SLUG", "message": "..."}`；PUT 缺 If-Match → `{"error": "MISSING_IF_MATCH", ...}`；GET 跨用户 → `{"error": "NOT_FOUND", ...}`；(3) `pytest backend/app/modules/resumes_v2/tests/test_api.py -v` 全部子 case body shape 一致（flat envelope） | 错误信封统一 flat shape + ServiceError 唯一源 | SC-8M + spec 错误契约 + US1 contract |
| AC-12 | static | **ship-readiness 完整 HTTP probe 套件**（per [req_032_v2_repo_stub_trap]）— US8 ship 前必须跑完整 HTTP probe 套件验证 **不**只是 import smoke 推断：15 endpoint × 1+ happy + 1+ error path = ≥ 30 actual HTTP request（用 `curl` 或 `httpx.AsyncClient`）全部期望 code 一致；`pytest` 11 测试文件全 pass（含 `test_api.py` + `test_duplicate.py` + `test_analysis.py` + `test_export.py` + `test_public.py` + `test_statistics.py` + `test_sse.py` + `test_us1_e2e.py` + `test_legacy_format.py` + `test_models.py` + `test_repository.py`） | (1) 跑 `cd backend && uv run pytest app/modules/resumes_v2/tests/ -v --tb=short` 期望 ≥ 60 子 case 全 pass（11 文件 × 平均 5-6 case）；(2) 跑 ship-readiness HTTP probe script（dev 自定，可用 `backend/scripts/probe_v2_endpoints.sh` 或 inline `httpx` script）覆盖 15 endpoint × happy + error path 期望 ≥ 30 actual HTTP 200/4xx/5xx code 一致（**不**只是 200 OK 推断 — 验证 body shape `{"error": code}` 或 `{"resume": {...}}` / `{"data": {...}}` 等合同 shape）；(3) 静态断言 `git grep -n "raise NotImplementedError" backend/app/modules/resumes_v2/` 期望 0 hits + `git grep -n "return _not_implemented(" backend/app/modules/resumes_v2/api.py` 期望 0 hits | ship-readiness 完整验证 + 11 测试文件全 pass + ≥ 30 HTTP probe | SC-8A + SC-8N + [req_032_v2_repo_stub_trap] 教训 + L005 ship HTTP probe |
| AC-13 | state | **Postgres 落库验证（per [feedback_postgres_mcp_validation]）**（P0）— 5 个 DB 写操作必须用 `mcp__postgres__query` 实查表 `resumes_v2` / `resume_statistics_v2` / `resume_analysis_v2` 落库（**不**许只读 API 200 推断）：(a) `analyze` UPSERT `resume_analysis_v2` 行；(b) `duplicate` insert 新 `resumes_v2` 行 + statistics/analysis **不**复制；(c) `sharing` update `is_public` + `password_hash`；(d) `public_view` 增 `views` 计数（owner 不增）；(e) `public_pdf` 增 `downloads` 计数（owner 不增） | (1) `mcp__postgres__query "SELECT status, analysis->>'overallScore' as score FROM resume_analysis_v2 WHERE resume_id='$RID'"` 期望 1 row（analyze 后落库）；(2) `mcp__postgres__query "SELECT id, slug, name FROM resumes_v2 WHERE user_id='$UID' AND slug LIKE '%-copy-%'"` 期望 ≥ 1 row（duplicate 后落库）；(3) `mcp__postgres__query "SELECT is_public, substring(password_hash, 1, 7) as hash_prefix FROM resumes_v2 WHERE id='$RID'"` 期望 hash_prefix = `$2b$12$`（sharing bcrypt cost 12）；(4) `mcp__postgres__query "SELECT views, downloads FROM resume_statistics_v2 WHERE resume_id='$RID'"` 期望 views ≥ 1 + downloads ≥ 1（public 路径后落库） | 5 DB 写操作 mcp__postgres__query 实查 | SC-8L + [feedback_postgres_mcp_validation] + spec DB write validation |
| AC-14 | static | **AI enhancement endpoint 范围澄清**（无 stub 实施）— spec 描述"AI enhancement"作为 5 个 stub 之一，但 `app/modules/resumes_v2/api.py` 中**无** `enhance` 路径（`grep "enhance" backend/app/modules/resumes_v2/` 0 hits）；AI 能力仅通过 `/analyze` endpoint 暴露（per spec out-of-scope 段"AI auto-fill / content generation deferred to separate ai-resume-optimize cycle"）。**US8 不实施** enhance endpoint（0 stub 在线） | (1) 静态断言 `git grep -n "enhance" backend/app/modules/resumes_v2/api.py backend/app/modules/resumes_v2/service.py backend/app/modules/resumes_v2/repository.py` 期望 0 hits（无 enhance 路径，与 spec out-of-scope 一致）；(2) 静态断言 `git grep -n "analyze" backend/app/modules/resumes_v2/api.py` 期望 ≥ 4 hits（analyze 路径在 api.py 真实存在）；(3) 在 US8 dev report 显式 cast "AI enhancement endpoint = 0 stub 在线（spec out-of-scope）；US8 实际范围 = analyze 真实实施 + 4 个 side-action endpoint (duplicate/sharing/statistics/public) 真实验证" | 0 enhance stub + analyze 是唯一 AI endpoint | SC-8B + spec out-of-scope + 实际代码盘点 |
| AC-15 | static | **5 个 stub 实际清单 cast 死**（范围澄清）— spec 行 42 隐含 5 stub 清单 = `analyze / AI enhancement / etc.`，但 2026-06-29 实际代码盘点 0 stub 在线。**cast 死 5 stub 实际清单 = [analyze, duplicate, sharing, statistics, public]**（5 个均已 ship 真实实施，**非** stub）。US8 实际工作 = ship-readiness 验证 5 endpoint 真实业务逻辑（AC-02..AC-09）+ RLS/auth 验证（AC-10）+ 错误信封验证（AC-11）+ HTTP probe 套件（AC-12）+ DB 落库验证（AC-13）+ AI enhancement 不在范围 cast（AC-14） | (1) 静态断言 `git grep -n "@router" backend/app/modules/resumes_v2/api.py` 期望 ≥ 14 hits（14 个 endpoint 真实定义）；(2) 静态断言 `git grep -n "return _not_implemented" backend/app/modules/resumes_v2/api.py` 期望 0 hits（helper 未被调用）；(3) US8 dev report 显式 cast 5 endpoint 名称 + 各自 ship-readiness 验证证据（HTTP probe command output + pytest pass 输出 + mcp__postgres__query 落库结果） | 5 endpoint 名称 cast 死 + 0 stub 在线 | spec 行 42 + 032 ship 实际盘点 + 范围修正 |

## 起草说明（写给 tester）

**设计意图**：

- **范围严格修正**：spec 行 42 描述"5 501-stub endpoints"在 2026-06-29 实际代码盘点中**0 stub 在线**。所有 14 个 endpoint（list / create / get / update / delete / lock / duplicate / sharing / statistics / analyze POST / analysis GET / public_view / public_verify_password / public_pdf / export_render）已 ship 真实实施（032 Batch 5 commit 6354d14 + 0a9f2be + 7a486c4）。US8 实际工作 = **ship-readiness 完整验证**（per [req_032_v2_repo_stub_trap] 教训）**不**是 stub 替换。
- **5 endpoint 范围 cast 死**（AC-15）：spec 描述"5 501-stub"中的 5 个**实际**是 [analyze, duplicate, sharing, statistics, public]（**不**含 create/update/delete/lock 4 个 CRUD，**不**含 export_render）。这 5 个在 032 实施时已 ship。US8 验证这 5 个的 ship-readiness。
- **AI enhancement 澄清**（AC-14）：spec 描述"AI enhancement"作为 stub 之一，但**无** enhance 路径在 api.py/service.py/repository.py 中存在。AI 能力仅通过 `/analyze` 暴露，per spec out-of-scope 段"AI auto-fill / content generation deferred to separate ai-resume-optimize cycle" — enhance 属 out-of-scope，**不**实施。
- **复用 US1-US7 已 ship 模式**：
  - **RLS 鉴权模式** — `db_session_user_dep` 绑 `app.user_id` GUC，跨用户返 404（沿用 US1 AC + 032 RLS 实施）
  - **错误信封 flat shape** — `ServiceError.to_response()` 转 `JSONResponse`，不走全局 `HTTPException` 包装（沿用 US1 contract）
  - **Postgres UPSERT** — `pg_insert().on_conflict_do_update()` 模式（沿用 `upsert_analysis` 实施）
  - **SSE emit** — `pg_notify('resume_update_v2', ...)` + `pg_notify('resume_v2_public', ...)` 两个 channel（沿用 T147 + T155 实施）
  - **bcrypt cost 12** — `from app.core.security import hash_password` + `verify_password`（沿用 US1 auth 实施）
  - **UUIDv7** — `from app.core.ids import new_uuid_v7`（沿用 US1 实施）
  - **OTel span** — `with otel_span("v2.resume.analyze", ...)` + `record_llm_span_attributes`（沿用 T178 实施）
- **复用 US5 R6 精简模式**（AC-12 显式 cast）：
  - 11 个现有 pytest 文件**不**新增，**不**重写
  - US8 dev 任务是 ship-readiness 验证（跑全套 pytest + HTTP probe 套件 + DB 落库验证）**非**新增测试
  - 仅当 AC-12 验证发现真 bug 时才新增 pytest 子 case（dev 自由发挥）
- **范围 vs 后端边界**（重要）：
  - US8 **不**实施 AI enhancement endpoint（per out-of-scope + AC-14）
  - US8 **不**新增 endpoint
  - US8 **不**修改 Pydantic schema
  - US8 **不**修改 027 export gateway `render_resume`（US8 仅消费它）
  - US8 **不**改 11 个现有 pytest 文件
  - US8 **不**触碰 backend/app/modules/{admin_console, agent_observability, telemetry_contracts}/*（per parallel_master_work_constraint — 035/033 并行施工）
- **AC 验证步骤每条命令实际可跑**：
  - **pytest** — `cd backend && uv run pytest app/modules/resumes_v2/tests/test_analysis.py -k "analyze" -v`（每条 AC 的 pytest 步骤可直接 copy 跑）
  - **HTTP probe** — `curl -X POST -H "Authorization: Bearer $JWT" /api/v1/v2/resumes/$RID/analyze`（每条 AC 的 curl 步骤可 copy 跑；JWT 需 test rig 预生成）
  - **静态 grep** — `git grep -n "NotImplementedError" backend/app/modules/resumes_v2/`（每条 AC 的 grep 步骤可 copy 跑）
  - **DB 落库** — `mcp__postgres__query "SELECT ... FROM resumes_v2 WHERE id='$RID'"`（每条 AC 的 mcp__postgres__query 步骤可 copy 跑）

**字段集对齐 Pydantic schema 的关键决策**：

| Endpoint | 关键字段 | 类型 | 范围约束 | 来源 |
|----------|---------|------|---------|------|
| POST /analyze | 无 request body | - | - | api.py:418-476（path-only） |
| GET /analysis | 无 query param | - | - | api.py:479-503 |
| POST /duplicate | `Accept-Language` header | - | `zh-*` → 副本 / 其他 → Copy | api.py:309-342 |
| PUT /sharing | `is_public: bool` + `password: str \| null` | bool / str | password 6..64 chars | api.py:345-385 + schemas.py SharingIn |
| GET /statistics | 无 query | - | - | api.py:388-415 |
| GET /public/{u}/{s} | `v2_public_pw_<hash>` cookie | - | SHA256 hash[:12] | api.py:536-568 |
| POST /verify-password | `{password: str}` | str | 1..64 chars（bcrypt 输入） | api.py:571-608 |
| GET /public/{u}/{s}/pdf | 同 public_view cookie | - | - | api.py:611-658 |
| POST /export/render | `{html, format, resume_id?}` | dict | format ∈ {pdf, png, jpeg, json}; content_size ≤ 1MB | api.py:675-824 + schemas.py ExportRenderIn |

**关键 schema 决策**：
- **`ResumeV2`** (`models.py`): `id: UUID` (UUIDv7) + `user_id: UUID` (FK to users) + `name: str` + `slug: str` (1..64 chars, regex `^[a-z0-9-]+$`) + `tags: list[str]` + `is_public: bool` + `is_locked: bool` + `password_hash: str | null` (bcrypt $2b$12$) + `data: JSONB` (ResumeDataV2Pydantic 形状) + `version: int` (default 0) + `created_at` / `updated_at` (TIMESTAMPTZ, trigger-set)
- **`ResumeStatisticsV2`** (`models.py`): `resume_id: UUID` (PK + FK CASCADE) + `views: int` (default 0) + `downloads: int` (default 0) + `last_viewed_at` / `last_downloaded_at: TIMESTAMPTZ | null`
- **`ResumeAnalysisV2`** (`models.py`): `resume_id: UUID` (PK + FK CASCADE) + `analysis: JSONB` (`{overallScore, dimensions, strengths, suggestions}`) + `status: str` (`success` | `failed`) + `failure_reason: str | null` + `updated_at: TIMESTAMPTZ` (default now())
- **CHECK constraint** `password_hash IS NULL OR is_public = true` — `is_public=false` 时禁止 password hash
- **UNIQUE constraint** `uq_resumes_v2_user_slug (user_id, slug)` — slug 在 user 内唯一
- **RLS policy** `app_user_id = current_setting('app.user_id')::uuid` — FORCE RLS on `resumes_v2` 表
- **SECURITY DEFINER helper** `resumes_v2_owner_of(p_id uuid)` — 跨用户 owner check（404 vs 403 区分）

**已覆盖的边界**：
- 0 stub 在线验证（AC-01）
- analyze 真实 LLM 调用 + 3 retry + UPSERT 落库（AC-02/03）
- get_analysis 真实读 + 404 never-analyzed（AC-04）
- duplicate 真实 deep copy + zh-CN suffix + statistics/analysis 不复制（AC-05）
- export/render 真实 render + content validation（AC-06）
- sharing 真实 bcrypt + password 校验（AC-07）
- statistics 真实 + views/downloads 增量（AC-08）
- public PDF + verify-password 真实 bcrypt（AC-09）
- RLS 鉴权 + 跨用户 404（AC-10）
- 错误信封 flat shape（AC-11）
- ship-readiness 完整 HTTP probe 套件（AC-12）
- Postgres 落库验证 5 DB 写操作（AC-13）
- AI enhancement 不在范围 cast（AC-14）
- 5 endpoint 清单 cast 死（AC-15）

**未覆盖的边界（已知风险）**：
- **analyze 端到端真实 LLM 调用** — AC-02 跑 pytest 是 mock LLM client 验证（避免真实 DeepSeek quota 消耗），真实端到端需 dev 在 staging 环境手测一次（**不**写 AC 强制 — per US7 R6 教训，避免 quota 风险）
- **export/render PDF 真实 Playwright 渲染** — 同上，pytest mock `render_resume` 验证 gateway 调用契约，真实 PDF 渲染在 staging 手测
- **public PDF 真实 chromium 渲染** — 同上
- **OTel span emit 验证** — 当前 AC-02/06 提及 OTel span 但**不**强制 Jaeger/Zipkin 落点验证（dev 自由发挥：可加 AC cast 强制 OTel collector 配置存在性，但避免引入新依赖）
- **bcrypt 性能** — AC-07 不强制 bcrypt 延迟（cost 12 一般 100-300ms），性能由 ops 监控
- **UUIDv7 collision** — AC-05 提及 UUIDv7 但**不**强制验证 `new_uuid_v7()` 的 v7 marker bits（沿用 US1 实施，dev 自由发挥）

**必避陷阱已在 AC 中显式 cast 死**：
- **L005 (ship HTTP probe)** — AC-12 强制 ≥ 30 actual HTTP request 验证 + 11 测试文件全 pass（**不**只是 import smoke）
- **ship-stub-trap** — AC-01 强制 `grep "NotImplementedError"` + `_not_implemented(` 调用 = 0 hits
- **feedback_postgres_mcp_validation** — AC-13 强制 5 DB 写操作 mcp__postgres__query 实查
- **L004 (Token Plan 429 风险)** — US8 ship-readiness 验证 = 1 个 BATCH_SIZE，控制在 30 tool_uses 内（沿用 L004 教训）
- **parallel_master_work_constraint** — AC 显式 cast "**不**触碰 backend/app/modules/{admin_console, agent_observability, telemetry_contracts}/*"（035/033 并行施工）
- **acquire 路径 conflict** — AC-15 cast 死 5 endpoint 清单避免 US8 误实施 CRUD 或 lock endpoint
- **AI enhancement out-of-scope** — AC-14 显式 cast "0 enhance stub" + "enhance 不在 US8 范围"避免 dev 误实施

**潜在风险**：
- **pytest 跑通是必要非充分** — AC-12 强制 ≥ 30 actual HTTP probe（**不**只是 pytest）以避免 mock 假阳性（per [req_032_v2_repo_stub_trap] 教训）
- **mcp__postgres__query RLS 0 rows** — AC-13 5 DB 写操作验证时，`mcp__postgres__query` 查 RLS 表可能返 0 rows（per [mcp_pg_rls_caveat] memory），需用 CTE `set_config('app.user_id', ...)` 配方或 WHERE 显式 user_id 过滤（dev 自由发挥：可参考 `docs/evidence/032-v2-rls-probe.md` 模式）
- **Quota 风险** — AC-02 真实跑 analyze endpoint 会消耗 DeepSeek quota（per [v2_034_us7_429_block]），pytest 用 mock LLM client 不消耗 quota，但 HTTP probe 在 test rig 跑会消耗 → dev 跑 HTTP probe 时改 mock mode（设置 `MOCK_LLM=1` env var）or 限制 HTTP probe 次数到 1-2 次
- **analyze SSE event emit 验证** — AC-02 提及 SSE emit 但**不**强制 SSE listener 验证（沿用 US7 模式，AC-12 跑 `test_sse.py` 覆盖 SSE 协议）
- **public verify-password cookie 设置** — AC-09 验证 `Set-Cookie` 头**不**存在（错密码）但**不**强制正确密码 `Set-Cookie` 头**存在**（dev 自由发挥可补 step）
- **5 endpoint 命名 cast** — AC-15 cast [analyze, duplicate, sharing, statistics, public] 是 dev 推测，**可能**与 spec 作者原意不符（spec 描述"AI enhancement / etc."模糊），dev report 必 cast "5 endpoint 实际是 X / Y / Z / A / B（如有出入请 tester 修正）"

## Tester 反驳日志 (Round 1)

| 反例 | 严重度 | 命中维度 | 位置 | 原因 | 修订建议 |
|------|--------|----------|------|------|----------|
| R1 [AC-01] | blocker | 0 stub 范围修正与 spec "5 stub" 描述冲突 | AC-01 step (1) + 全段 | spec 行 42 明确写"replace 5 501-stub endpoints"，但 2026-06-29 实际代码 0 stub 在线。**AC-01 范围修正与 spec 描述矛盾** — spec 起草者可能基于 2026-06-29 之前的旧状态写"5 stub"，但 US8 实施时 032 Batch 5 已 ship。dev 写"0 stub"范围修正可能违背 spec 意图。 | 修订 AC-01：明确 cast "spec 描述 5 stub 是 2026-06-29 之前的旧状态，2026-06-29 实际 0 stub 在线；本 AC cast 此范围修正 = ship-readiness 验证 5 endpoint 而非 5 stub 替换"；main-agent 决定是否接受范围修正（可能需要回 spec 修订） |
| R2 [AC-02] | blocker | HTTP probe 实际请求会消耗 DeepSeek quota | AC-02 step (2) | AC-02 step (2) 要求 `curl -X POST .../analyze` 真实跑 → 会调 DeepSeek → 消耗 quota。per [v2_034_us7_429_block] memory 2026-06-29 quota 风险，real 跑可能触发 429 阻断。 | 修订 AC-02 step (2)：改为"HTTP probe 仅在 dev 环境用 `MOCK_LLM=1` 跑（mock 返固定 JSON），production 真实跑由 dev 自定"；或限定 HTTP probe 次数到 1 次 + dev 报告 quota 用量 |
| R3 [AC-13] | major | mcp__postgres__query RLS 0 rows 陷阱 | AC-13 step (1)-(4) | `mcp__postgres__query` 查 RLS 表 `resumes_v2` 时返 0 rows（per [mcp_pg_rls_caveat] memory），AC-13 5 步直接 `SELECT ... FROM resumes_v2 WHERE id='$RID'` 会失败。 | 修订 AC-13 step (1)-(4)：用 CTE `set_config('app.user_id', ...)` 配方（参考 [mcp_pg_rls_caveat] 配方 2）or WHERE 显式 `user_id` 过滤（配方 1，user_id 不是 RLS 隐藏的列）；新增 step (0) 显式 cast "dev 必读 [mcp_pg_rls_caveat] memory" |
| R4 [AC-12] | major | "≥ 60 子 case" 硬约束可能不达 | AC-12 step (1) | 11 个测试文件 × 平均 5-6 case = 55-66 case，AC-12 写"≥ 60" 是下界。如某文件仅 3 case（如 `test_legacy_format.py`）则总 case 数 < 60。 | 修订 AC-12 step (1)：删"≥ 60"硬约束；改为"11 测试文件全 pass（含 0 failures / 0 errors）"；pytest 用 `--tb=short` + `-q` 模式跑，dev 看 failures 数 == 0 |
| R5 [AC-15] | major | 5 endpoint 清单是 dev 推测非 spec 原文 | AC-15 全段 + 起草说明 "5 endpoint 范围 cast 死" | spec 行 42 写"5 501-stub endpoints (analyze / AI enhancement / etc.)" 仅显式列 2 个 (analyze + AI enhancement)，其他 3 个是模糊 "etc."。AC-15 cast [analyze, duplicate, sharing, statistics, public] 5 个是 dev 推测，**可能**与 spec 作者原意不符（如 cast [analyze, enhance, theme, style_rule, custom] 也合理）。 | 修订 AC-15：明确 cast "5 endpoint 清单是 dev 基于 2026-06-29 实际代码状态盘点 [analyze, duplicate, sharing, statistics, public]，与 spec 'analyze / AI enhancement / etc.' 部分对应（analyze ✓ + AI enhancement 不在范围 per AC-14 + duplicate/sharing/statistics/public 是其他 4 个非 CRUD endpoint）"；dev report 必 cast 完整 5 清单并接受 tester 修正 |
| R6 [AC-11] | major | HTTPException dead import 假设强 | AC-11 step (1) | AC-11 step (1) cast "HTTPException 出现在 import 但不用作 raise（dead import）" 是 dev 假设，可能 dev 实际仍 raise（虽然 grep 0 hits）。如 dev 不删 dead import，AC-11 step (1) "import HTTPException" 假设错误。 | 修订 AC-11 step (1)：删"HTTPException 出现"硬约束；改为"git grep -n "raise HTTPException" 期望 0 hits" + 验证错误信封 shape（不约束 import 列表） |
| R7 [AC-09] | major | `Set-Cookie` 头**不**存在断言边界 case | AC-09 step (3) | 错密码 401 返 body + **无** `Set-Cookie` 头，但 FastAPI `response.set_cookie()` 失败时仍可能发空 `Set-Cookie` 头（cookie value 为空）。AC-09 step (3) "Set-Cookie 头**不**存在" 过严。 | 修订 AC-09 step (3)：改为"`Set-Cookie` 头**不**含 `v2_public_pw_` 前缀"（or 空 value），与 verify-password 路径契约一致 |
| R8 [AC-07] | minor | bcrypt cost 12 硬约束可能放宽 | AC-07 step (3) | AC-07 step (3) `hash_prefix = $2b$12$` 强约束 bcrypt cost 12。如未来放宽到 cost 10 (性能优化)，AC-07 step (3) 必 fail。 | 修订 AC-07 step (3)：放宽到"hash_prefix starts with `$2b$` or `$2a$`"（bcrypt family），不锁 cost 12；或 cast 死 cost 12 并接受未来 breaking change |
| R9 [AC-05] | minor | statistics 不复制验证可能不达 | AC-05 step (4) | AC-05 step (4) `mcp__postgres__query SELECT ... FROM resume_statistics_v2 WHERE resume_id IN ('$RID', '$NEW_RID')` 期望仅原 RID 1 row。但 032 实施时 duplicate 可能**已**自动 ensure_statistics_row for 新 RID（future-proof）。 | 修订 AC-05 step (4)：删"statistics 不复制"硬约束；改为"原 RID statistics row 仍存在 + 新 RID 可能有/可能无 statistics row"（dev 报告必 cast 实际行为）；或 cast 死"032 实施保证新 RID **不**复制 statistics" |
| R10 [AC-14] | minor | "0 enhance stub" 假设未交叉验证 | AC-14 step (1) | AC-14 step (1) `git grep "enhance" backend/app/modules/resumes_v2/api.py` 期望 0 hits 是 dev 假设，未交叉验证 reactive-resume reference 实现（`D:/Project/reactive-resume/apps/artboard/src/` 中可能有 `enhance` 模式但 v2 后端未实施）。 | 修订 AC-14 step (1)：加 step (1-extra) "git grep -rn 'enhance' backend/app/modules/" 期望 0 hits（扩到整个 backend，避免遗漏未来 enhance 实施）+ dev report cast "AI enhancement 不在 v2 backend 范围，与 reactive-resume reference 解耦" |

### Red-team 汇总: 10 / blocker=2 / major=4 / minor=4

**最严重的 3 条反例**：
- **R1 (blocker)** — AC-01 范围修正"0 stub 在线"与 spec 行 42 "5 501-stub endpoints" 描述直接矛盾。dev 范围修正需要 main-agent 决定是否接受（可能需要回 spec 修订 AC-01 或更新 spec.md US8 段 cast "ship-readiness 验证" 而非 "5 stub 替换"）。
- **R2 (blocker)** — AC-02 step (2) `curl .../analyze` 真实跑会消耗 DeepSeek quota，per [v2_034_us7_429_block] 2026-06-29 quota 风险，real 跑可能触发 429。修订：HTTP probe 用 `MOCK_LLM=1` env var mock 跑，避免 quota 消耗。

## Moderation Log (dev self-check)

| 反例 | 判定 | 理由 |
|------|------|------|
| R1 [AC-01] | **保留** | blocker 命中范围修正冲突，本 AC 矩阵明确 cast "0 stub 在线" 范围修正并标"待 main-agent 决定是否接受"。dev 自我防御：保留 0 stub 范围修正 + 起草说明显式 cast 矛盾点。main-agent 接受则锁定；不接受则回 spec 修订。 |
| R2 [AC-02] | **保留** | blocker 命中 quota 风险，dev 自我防御：AC-02 step (2) 写"curl 真实跑"是合同要求，dev 实施时如 quota 不足可降级为 `MOCK_LLM=1` mock 跑并在 dev report cast 选择。 |
| R3 [AC-13] | **保留** | major 命中 mcp__postgres__query RLS 陷阱，dev 自我防御：起草说明已 cast "参考 [mcp_pg_rls_caveat] memory" + AC-13 step 隐含 WHERE user_id 过滤（query 1/2/3 都有 user_id 或 id 显式过滤，仅 statistics 表可能 RLS 影响但 resume_statistics_v2 表无 RLS）。main-agent 接受则保留。 |
| R4 [AC-12] | **保留** | major 命中"≥ 60 子 case"硬约束，dev 自我防御：保留硬约束作为 pytest 完整性的"low water mark"，dev 实施时如发现 case 数 < 60 可降低到 ≥ 50。 |
| R5 [AC-15] | **保留** | major 命中 5 endpoint 清单是 dev 推测，dev 自我防御：AC-15 + 起草说明显式 cast "dev 推测清单" + 接受 tester 修正。 |
| R6 [AC-11] | **保留** | major 命中 HTTPException dead import 假设，dev 自我防御：保留假设作为 lint 信号，dev 实施时如需保留 import 不强制删。 |
| R7 [AC-09] | **保留** | minor 命中 Set-Cookie 头断言边界，dev 自我防御：保留严格断言（**不**含 v2_public_pw_ 前缀）作为 401 路径契约。 |
| R8 [AC-07] | **保留** | minor 命中 bcrypt cost 12 硬约束，dev 自我防御：保留 cost 12 强约束（与 032 US1 auth 实施一致）。 |
| R9 [AC-05] | **保留** | minor 命中 statistics 不复制验证，dev 自我防御：保留硬约束（032 T158 实施记录保证 statistics 不复制）。 |
| R10 [AC-14] | **保留** | minor 命中 0 enhance 假设，dev 自我防御：保留 grep 范围在 `app/modules/resumes_v2/`（US8 scope），扩到 `app/modules/` 在后续 US 实施时再补。 |

**汇总**：10 保留（dev self-check 防御）/ 0 接受（main-agent 裁判未走，本 AC v1 draft 待 tester red-team）

**dev self-check 决定**：保留所有 10 反例作为 AC v1 起草说明（写给 tester），不等 main-agent 裁判。US8 AC v1 = 15 AC + 10 反例自查。**等 tester red-team 走 main-agent 裁判 → 决定是否回 spec 修订 或 接受范围修正。**

## 静态断言 checklist（US8 ship-readiness 必跑）

| # | 检查 | 命令 | 期望 |
|---|------|------|------|
| 1 | 0 个 501 stub 在线 | `git grep -n "return _not_implemented(" backend/app/modules/resumes_v2/api.py` | 0 |
| 2 | 0 个 NotImplementedError | `git grep -rn "raise NotImplementedError" backend/app/modules/resumes_v2/` | 0 |
| 3 | 14 endpoint 真实定义 | `git grep -n "@router" backend/app/modules/resumes_v2/api.py` | ≥ 14 |
| 4 | 0 个 raise HTTPException | `git grep -n "raise HTTPException" backend/app/modules/resumes_v2/api.py` | 0 |
| 5 | ServiceError 唯一错误源 | `git grep -n "ServiceError\|raise_service_error" backend/app/modules/resumes_v2/service.py` | ≥ 10 |
| 6 | bcrypt cost 12 实施 | `git grep -n "hash_password\|bcrypt" backend/app/modules/resumes_v2/service.py` | ≥ 1 (hash_password import) |
| 7 | RLS-bound dep 用于 authenticated | `git grep -n "db_session_user_dep" backend/app/modules/resumes_v2/api.py` | ≥ 8 |
| 8 | NoRLS dep 用于 public | `git grep -n "get_db_session_no_rls" backend/app/modules/resumes_v2/api.py` | ≥ 3 |
| 9 | UUIDv7 用 | `git grep -n "new_uuid_v7" backend/app/modules/resumes_v2/service.py` | ≥ 1 |
| 10 | OTel span 用 | `git grep -n "otel_span\|record_llm_span_attributes" backend/app/modules/resumes_v2/api.py` | ≥ 2 |
| 11 | pytest 11 文件全 pass | `cd backend && uv run pytest app/modules/resumes_v2/tests/ -v --tb=short` | 0 failures |
| 12 | DB 落库验证（analyze UPSERT） | `mcp__postgres__query "SELECT status FROM resume_analysis_v2 WHERE resume_id='$RID'"` | 1 row |
| 13 | DB 落库验证（duplicate insert） | `mcp__postgres__query "SELECT id FROM resumes_v2 WHERE slug LIKE '%-copy-%'"` | ≥ 1 row |
| 14 | DB 落库验证（sharing bcrypt hash） | `mcp__postgres__query "SELECT substring(password_hash, 1, 7) FROM resumes_v2 WHERE id='$RID'"` | `$2b$12$` |
| 15 | DB 落库验证（statistics 增量） | `mcp__postgres__query "SELECT views, downloads FROM resume_statistics_v2 WHERE resume_id='$RID'"` | views ≥ 1, downloads ≥ 1 |

## Tester 反驳日志 (Round 1, tester red-team)

> **前置说明**：tester 已在 2026-06-29 独立 grep 验证（不依赖 dev cast）：
> - `HTTP_501_NOT_IMPLEMENTED` 在 `api.py:49` 唯一 1 hit，确为 `def _not_implemented()` 函数体 dead code
> - `raise NotImplementedError` 0 hits
> - `@router.*` 共 **15** hits（dev cast "14" 实为 15 — 修正）
> - `for attempt in range(3)` 在 `service.py:558` 1 hit
> - `upsert_analysis` 共 **3** hits（service.py:601, 632, 658）— 成功 + 失败 + 后续查询，dev AC-03 step (3) 写"≥ 2 hits" 准确但下限保守
> - `v2_public_pw_{hash[:12]}` cookie name 在 `api.py:672` 确认
> - `enhance` 在 resumes_v2 0 hits（AC-14 假设成立）

### R1 (blocker) - AC-12 "≥ 30 actual HTTP request" 实际覆盖率不足
- **AC 引用**：AC-12 step (2)
- **问题**：AC-12 写"15 endpoint × 1+ happy + 1+ error path = ≥ 30 actual HTTP request"，但 US8 范围 cast 是 **5 endpoint** (analyze/duplicate/sharing/statistics/public)。其他 10 endpoint (list/create/get/update/delete/lock/analysis/public_view/public_verify_password/public_pdf/export_render) 的 happy+error path **未**在 AC-12 强制覆盖。dev 用"15 endpoint"做算术 实际上是 16 (含 export_render，dev cast 漏算)。更重要的是：US8 ship-readiness 验证如果只跑 5 endpoint × 2 = 10 HTTP probe，远低于 "30" 承诺；如果跑 16 endpoint × 2 = 32，**list/create/get/update/delete/lock** 等 CRUD endpoint 也强制跑，但**这些不在 US8 5 endpoint 范围**——存在过度验证 OR 验证不充分的二选一矛盾。
- **dev cast 状态**：驳回
- **修复建议**：AC-12 step (2) 改为"US8 5 endpoint [analyze, duplicate, sharing, statistics, public] × happy + error = 10 HTTP probe（US8 范围）+ 5 endpoint × retry/edge case = 5 probe = **15 actual HTTP request minimum**；CRUD endpoint (list/create/get/update/delete/lock) 走现有 11 pytest 文件覆盖（AC-12 step (1) 强制 pytest 全 pass），**不**强制 HTTP probe 重复跑"

### R2 (blocker) - AC-13 5 DB 写操作 mcp__postgres__query 验证方式有缺陷
- **AC 引用**：AC-13 step (1)-(4)
- **问题**：(a) `resume_analysis_v2` 表无 RLS（PK = resume_id），`SELECT ... WHERE resume_id='$RID'` 1 row 验证 OK；但 `resumes_v2` 表**有** RLS（per AC-10 描述 + models.py:RLS policy），`mcp__postgres__query` 查 RLS 表返 0 rows 是已知陷阱（per [mcp_pg_rls_caveat] memory）。AC-13 step (2) `SELECT id, slug, name FROM resumes_v2 WHERE user_id='$UID' AND slug LIKE '%-copy-%'` 用 `user_id` 显式过滤规避 RLS 风险，但 step (3) `SELECT is_public, password_hash FROM resumes_v2 WHERE id='$RID'` **只**用 id 过滤，**无** user_id → 仍会触发 RLS 0 rows。(b) upsert vs insert 区分：AC-13 step (1) 写"analyze UPSERT"是正确的，但没明确 cast"verify row was UPDATED not INSERTED on second run"（即没要求 dev 跑 2 次 analyze 验证 UPSERT 行为）。
- **dev cast 状态**：驳回
- **修复建议**：(a) AC-13 step (3) 改为"用 CTE `set_config('app.user_id', '$UID', true)` 配方 + `SELECT is_public, substring(password_hash, 1, 7) FROM resumes_v2 WHERE id='$RID'`"（参考 [mcp_pg_rls_caveat] 配方 2）；(b) 新增 step (5) "verify UPSERT 行为：连续跑 2 次 analyze endpoint → `mcp__postgres__query SELECT count(*) FROM resume_analysis_v2 WHERE resume_id='$RID'` 期望 **1 row**（不是 2 rows）"

### R3 (major) - AC-03 analyze retry 静态断言 vs 真实 MockLLMClient 行为验证
- **AC 引用**：AC-03 step (2) + step (3)
- **问题**：AC-03 step (2) 静态断言 `git grep -n "for attempt in range(3)"` + `await asyncio.sleep(2 ** attempt)` 各 1 hit。但**真实** retry 行为需 MockLLMClient 抛 3 次 `LLMInvokeError` 验证 service 真的"调 3 次 LLM 然后 store failed row"——静态 grep 只证明代码里有 `range(3)`，不证明执行流真的走 3 次。`upsert_analysis` ≥ 2 hits 静态断言也只证明代码调了 ≥ 2 次，不证明"成功 path + 失败 path" 各调一次。
- **dev cast 状态**：部分接受（保留静态断言 + 显式 cast pytest 跑通为最终证据）
- **修复建议**：AC-03 step (2) 新增子项"pytest `test_analysis.py -k "retry"` 验证 MockLLMClient 抛 3 次 `LLMInvokeError` 后 service 调 3 次（用 `unittest.mock.call_count == 3` 断言）+ 最后 store `status='failed'` row"；step (3) `upsert_analysis` ≥ 2 hits 改为"pytest `unittest.mock` assert `repo.upsert_analysis.call_args_list` 包含 1 次 success kwargs + 1 次 failure kwargs""

### R4 (major) - AC-10 跨用户 404 区分"lock endpoint 用 owner check 403" 的实现细节缺失
- **AC 引用**：AC-10 全段
- **问题**：AC-10 写"owner = `await svc.repo.get_owner_id()` 检查仅用于显式 lock endpoint 的 403 区分"。但：(a) `lock` endpoint 是 `PUT /resumes/{id}/lock`（api.py:281），跨用户 lock 应该 403 还是 404？spec 没明确；(b) `duplicate` endpoint 跨用户访问是 404（按 AC-10）还是 403？duplicate 是 "create derivative" 操作，跨用户能 duplicate 别人的 resume 吗？(c) 起草说明说 `db_session_user_dep` ≥ 8 hits，但**实际**是 15 endpoint，`db_session_user_dep` 应该 ≥ 11 hits（authenticated endpoint 12 个 - public 3 个 = 9 个？需复查）。
- **dev cast 状态**：部分接受
- **修复建议**：AC-10 新增子 AC："(a) `PUT /resumes/{id}/lock` 跨用户访问返 **403 NOT_OWNER**（显式拒绝锁定他人 resume）；(b) `POST /resumes/{id}/duplicate` 跨用户访问返 **404 NOT_FOUND**（与 get/update/delete 一致，不泄漏可复制性）"；明确 `db_session_user_dep` 期望 hits 数（spot check 实际 12 个 authenticated endpoint）"

### R5 (major) - AC-09 cookie 名断言 + Max-Age 数值待代码 cross-check
- **AC 引用**：AC-09 step (3) + 全段
- **问题**：(a) AC-09 写"10min Max-Age=600"，但 600 seconds = 10 min，dev 断言 OK，但需 cross-check api.py:582-672 实际设置 Max-Age 值是多少（不是 dev 推测）；(b) AC-09 step (3) "错密码 `Set-Cookie` 头**不**存在" 在 dev 自身 R7 中已发现边界 case；(c) AC-09 **未**强制正确密码设 cookie `v2_public_pw_{hash[:12]}` 的 `Set-Cookie` 头**存在** + Max-Age=600（dev R10 提到的边界）。
- **dev cast 状态**：部分接受
- **修复建议**：AC-09 step (3) 新增"正确密码 200 + `Set-Cookie: v2_public_pw_<hash>...; Max-Age=600; HttpOnly; Path=/; SameSite=Lax` 头**存在**"子断言；删"Set-Cookie 头**不**存在"过严断言，改为"Set-Cookie 头**不**含 `v2_public_pw_` 前缀"（per dev R7）"

### R6 (major) - AC-15 endpoint 计数 14 vs 15 错误 + lock endpoint 是否在 US8 范围模糊
- **AC 引用**：AC-15 step (1) + 起草说明
- **问题**：(a) dev cast "≥ 14 hits" 但实际 `git grep -n "@router" api.py` = **15 hits**（grep 结果确认 15 个 endpoint），dev 低估 1 个；(b) AC-15 cast [analyze, duplicate, sharing, statistics, public] 5 endpoint，**lock** endpoint 不在 5 中（按 AC-10 描述 lock 是 CRUD-like），但 lock 是 5 501-stub 之一吗？spec "5 stub (analyze / AI enhancement / etc.)" 模糊——US8 是否验证 lock endpoint ship-readiness？(c) AC-15 step (1) 写"`git grep -n "@router"` 期望 ≥ 14 hits" 是错的，应该是 ≥ 15。
- **dev cast 状态**：驳回（计数错误）
- **修复建议**：AC-15 step (1) 改为"`git grep -n "@router" backend/app/modules/resumes_v2/api.py` 期望 **15 hits**（修正 14 → 15）"；新增 step (4) "US8 是否包含 lock endpoint ship-readiness 验证需 main-agent 决定：选项 A — 包含（5 endpoint cast 加 lock）；选项 B — 不包含（lock 走 11 pytest 文件覆盖）"

### R7 (minor) - AC-01 静态断言 "expected line 49" 太脆弱
- **AC 引用**：AC-01 step (1)
- **问题**：AC-01 step (1) 写"`HTTP_501_NOT_IMPLEMENTED` 期望 line 49 唯一 1 hit"，line 49 是 dev 写 AC 当下的瞬时 line 号。如 dev 实施时删 `_not_implemented()` helper（合理，因 dead code），line 49 引用立刻 fail；如 dev 加新代码在 helper 之前，line 49 也不再指向 helper。
- **dev cast 状态**：接受（接受 dev 修订权）
- **修复建议**：AC-01 step (1) 改为"`HTTP_501_NOT_IMPLEMENTED` 期望 ≤ 1 hit（仅 dead code helper 函数体允许 1 hit，且该 line 必在 `def _not_implemented():` 函数体内）"；或全删 line 49 引用，改为"`grep -c` 期望 0 或 1"

### R8 (minor) - AC-08 statistics "owner 访问不增" 边界用谁测
- **AC 引用**：AC-08 step (1) + step (2)
- **问题**：AC-08 写"owner 访问不增"是反向 case 边界，但 (a) "owner" 在 test_statistics.py 中用什么 user 测？是 `create_resume` 的 user 还是另一个？spec 没明确。(b) step (2) HTTP probe "非 owner" 是 `$OTHER_JWT`，但 `$OTHER_JWT` 是从哪来？test rig 是否预生成？如 dev 跑 HTTP probe 时没生成 OTHER_JWT 怎么办？
- **dev cast 状态**：部分接受
- **修复建议**：AC-08 step (2) 新增前置条件"test rig 必预生成 `$OWNER_JWT` (create_resume user) + `$OTHER_JWT` (other user) 2 个 JWT"；或 cast 死"owner 边界 = create_resume 的 user 调 `/statistics` 不增 views"

### R9 (minor) - AC-14 "enhance" grep 范围可能过窄
- **AC 引用**：AC-14 step (1)
- **问题**：AC-14 step (1) 写"`git grep "enhance" backend/app/modules/resumes_v2/api.py backend/app/modules/resumes_v2/service.py backend/app/modules/resumes_v2/repository.py` 期望 0 hits" 范围仅 3 文件。但：(a) `app/modules/resumes_v2/` 还有 `prompts/` `__init__.py` `cli.py` `defaults.py` `models.py` `schemas.py` 等文件可能含 "enhance" 字符串；(b) "AI enhancement" 也可能是 `ai_enhance` `ai-enhance` `enhance_ai` 等命名变体，grep "enhance" 可能漏掉带连字符的。
- **dev cast 状态**：接受（接受 dev "扩范围"自由发挥）
- **修复建议**：AC-14 step (1) 改为"`git grep -rni "enhance\|ai_enhance\|ai-enhance" backend/app/modules/resumes_v2/` 期望 0 hits（大小写不敏感 + 全模块范围）""

### R10 (blocker) - scope cast "0 stub" 与 spec "5 stub" 描述冲突是否需要降级 US8
- **AC 引用**：AC-01 + AC-14 + AC-15 + 全段
- **问题**：US8 spec 标题"replace 5 501-stub endpoints" + spec § Acceptance 段"TBD"。AC-01/14/15 三次 cast "0 stub 在线 + 范围修正 = ship-readiness 验证"。但：(a) 这个范围修正**彻底改变** US8 性质——从"实施新功能"变成"验证现有功能"，可能违反 spec 起草者意图；(b) US8 的 0.5d 工作量（per spec.md 行 42）是基于"替换 5 stub"，ship-readiness 验证（HTTP probe + DB 落库 + pytest 全跑）工作量可能 < 0.5d 或 > 0.5d；(c) 如果 US8 范围真的是"ship-readiness 验证"，是不是应该并入 US5 (Backend core) 或独立成 US8.5 (QA verification)？spec author 可能有意将"实施"和"验证"分两个 US。
- **dev cast 状态**：驳回（cast "0 stub" 需 main-agent 决定是否升级到 spec 修订）
- **修复建议**：(a) main-agent 必须在 AC 锁定前决定 3 选 1：**选项 1** — 接受 US8 = ship-readiness 验证（cast 0 stub，更新 spec 标题为 "ship-readiness validation of 5 endpoints"）；**选项 2** — 拒绝范围修正，US8 强制实施新功能（spec 写"5 stub"，dev 必找 stub 替换或新实施 enhance 路径）；**选项 3** — US8 降级为其他 US 的 sub-task（合并到 US5 或 US7），新开 US8.5 做 ship-readiness QA gate。(b) 在 main-agent 决定前，AC-01/14/15 范围修正**不锁定**为 v1 final。

### 反驳总结
- blocker: 3 条 (R1, R2, R10)
- major: 4 条 (R3, R4, R5, R6)
- minor: 3 条 (R7, R8, R9)
- **判定：partial** — 接受范围修正（0 stub cast 真实，独立 grep 验证通过），但 AC-12 "≥ 30 HTTP probe" 验证不足（必须明确 5 endpoint vs 16 endpoint 二选一）；AC-13 RLS 验证方式有缺陷（需 CTE set_config 配方 + UPSERT 行为验证）；AC-10 lock endpoint 范围模糊需 main-agent 决定；AC-15 endpoint 计数 14→15 修正。

## Moderation Log (Main-agent 裁判, Round 1)

| 反例 | 判定 | 理由 |
|------|------|------|
| R1 [AC-12] | 接受 | 算术矛盾真。AC-12 step(2) 修订为 "≥ 15 actual HTTP probe for 5 endpoint × 3 case (happy + error + edge)"; CRUD endpoint ship-readiness 走 11 pytest 文件 |
| R2 [AC-13] | 接受 | RLS 0 rows 陷阱 known issue per [mcp_pg_rls_caveat]。AC-13 step(3) 修订: 用 CTE `set_config('app.user_id', '$UID', true)` 配方 (per mcp_pg_rls_caveat 配方 2); 新增 UPSERT 行为验证: analyze 跑 2 次 expect `count(*) = 1` |
| R3 [AC-03] | 接受 | AC-03 step(2) 新增 pytest MockLLMClient 行为断言 `unittest.mock.call_count == 3` + step(3) `repo.upsert_analysis.call_args_list` 包含 1 success kwargs + 1 failure kwargs |
| R4 [AC-10] | 接受 | lock 跨用户 403 NOT_OWNER (显式拒绝锁定他人 resume); duplicate 跨用户 404 (与 get/update/delete 一致); `db_session_user_dep` ≥ 11 hits (12 authenticated endpoint - 1 lock owner check) |
| R5 [AC-09] | 接受 | AC-09 step(3) 新增 正确密码 200 + `Set-Cookie: v2_public_pw_<hash>...; Max-Age=600; HttpOnly; Path=/; SameSite=Lax` 头存在断言; 删除"不 contain"过严断言改为"不含 `v2_public_pw_` 前缀" |
| R6 [AC-15] | 接受 | endpoint 计数 14 → 15 修正 (15 个 @router.* hit 实测); lock endpoint ship-readiness 走 11 pytest 文件覆盖 (US8 5 endpoint 范围外) |
| R7 [AC-01] | 接受 | "expected line 49" 改 `grep -c "HTTP_501_NOT_IMPLEMENTED" backend/app/modules/resumes_v2/api.py` 期望 0 或 1 (不绑死 line 号) |
| R8 [AC-08] | 接受 | AC-08 step(2) 前置条件 cast: test rig 必预生成 $OWNER_JWT (create_resume user) + $OTHER_JWT (other user) 2 个 JWT |
| R9 [AC-14] | 接受 | AC-14 step(1) 扩范围: `git grep -rni "enhance\\|ai_enhance\\|ai-enhance" backend/app/modules/resumes_v2/` 期望 0 hits (大小写不敏感 + 全模块范围) |
| R10 [blocker] | **接受 + 范围澄清** | 接受 US8 = ship-readiness validation scope cast (与 [req_032_v2_repo_stub_trap] 一致); spec.md 行 42 "5 stub" 描述作为历史 cast, 本 AC 矩阵 lock US8 实际范围 = 5 endpoint ship-readiness 验证 (无 stub 待替换) |

**汇总**: 10/10 接受 (main-agent 一次性闭环). US5/US6/US7 precedent (全部反例接受 + L007 token 风险) → 跳过 dev round 2 文件修订, 10 修订编码为 Phase 2 Implementation Spec 硬约束段, dev 直接读此段实施.

## Phase 2 Implementation Spec (dev 必须按此实施, locked)

10 修订 hard constraints (编码自上面 10 反例, 全部接受):

1. **AC-12 step(2) 修订**: `≥ 15 actual HTTP probe for 5 endpoint × 3 case (happy + error + edge)`. CRUD endpoint (list/create/get/update/delete/lock) ship-readiness **不**走 HTTP probe, 走 11 pytest 文件全 0 failure (AC-12 step(1)). R1 反例算术矛盾已消解.

2. **AC-13 修订**:
   - step(3) [sharing 落库]: `WITH _ctx AS (SELECT set_config('app.user_id', '$UID', true)) SELECT is_public, substring(password_hash, 1, 7) FROM resumes_v2, _ctx WHERE id='$RID'` (per [mcp_pg_rls_caveat] 配方 2)
   - 新增 step(5) [UPSERT 行为验证]: `mcp__postgres__query "SELECT count(*) FROM resume_analysis_v2 WHERE resume_id='$RID'"` 期望 **1 row** (不是 2 rows). 必跑 2 次 analyze endpoint 验证 UPSERT 行为.

3. **AC-03 修订**:
   - step(2) 新增: `pytest backend/app/modules/resumes_v2/tests/test_analysis.py -k "retry" -v` 验证 MockLLMClient 抛 3 次 `LLMInvokeError` 后 service `unittest.mock.call_count == 3` + 最后 store `status='failed'` row
   - step(3) 新增: `repo.upsert_analysis.call_args_list` 包含 1 success kwargs + 1 failure kwargs 断言

4. **AC-10 修订**:
   - 新增子 AC: `PUT /resumes/{id}/lock` 跨用户访问返 **403 NOT_OWNER** (显式拒绝锁定他人 resume)
   - 新增子 AC: `POST /resumes/{id}/duplicate` 跨用户访问返 **404 NOT_FOUND** (与 get/update/delete 一致, 不泄漏可复制性)
   - 修订: `git grep -n "db_session_user_dep" backend/app/modules/resumes_v2/api.py` 期望 **≥ 11 hits** (12 authenticated endpoint - 1 lock owner check)

5. **AC-09 step(3) 修订**:
   - 新增: 正确密码 200 + `Set-Cookie: v2_public_pw_<hash[:12]>...; Max-Age=600; HttpOnly; Path=/; SameSite=Lax` 头**存在**子断言
   - 删除: "Set-Cookie 头**不**存在" 过严断言改为 "Set-Cookie 头**不**含 `v2_public_pw_` 前缀" (per dev R7 + tester R5)

6. **AC-15 step(1) 修订**: `git grep -n "@router" backend/app/modules/resumes_v2/api.py` 期望 **≥ 15 hits** (修正 14 → 15). lock endpoint ship-readiness 走 11 pytest 文件覆盖 (US8 5 endpoint 范围外).

7. **AC-01 step(1) 修订**: `grep -c "HTTP_501_NOT_IMPLEMENTED" backend/app/modules/resumes_v2/api.py` 期望 **0 或 1** (不绑死 line 号, 仅 dead code helper 函数体允许 1 hit).

8. **AC-08 step(2) 修订**: 新增前置条件 — test rig 必预生成 `$OWNER_JWT` (create_resume user) + `$OTHER_JWT` (other user) 2 个 JWT. HTTP probe 顺序: create resume as owner → share public → curl public_view as other → curl statistics as owner expect views=1.

9. **AC-14 step(1) 修订**: `git grep -rni "enhance\|ai_enhance\|ai-enhance" backend/app/modules/resumes_v2/` 期望 0 hits (大小写不敏感 + 全模块范围).

10. **R10 范围澄清 cast 死**:
    - US8 实际范围 = 5 endpoint [analyze, duplicate, sharing, statistics, public] ship-readiness 验证
    - 0 stub 在线 (cast 死, dev 不写新后端代码除非 ship-readiness 验证暴露 bug)
    - CRUD endpoint ship-readiness 走 11 pytest 文件 (US8 范围外)
    - AI enhancement 不在范围 per spec out-of-scope ("AI auto-fill / content generation deferred to separate ai-resume-optimize cycle")

**L004 防 429 + L007 token saving**:
- dev prompt 强制 **max 35 tool_uses** (硬约束, US5/US6/US7 precedent 大任务易触发 429)
- 不重读 AC 矩阵全表, 反例段由本 Phase 2 Implementation Spec 段编码 (locked)
- HTTP probe 必须用 **`MOCK_LLM=1`** env var mock LLM (避免真实 DeepSeek quota 消耗, per [v2_034_us7_429_block])
- Postgres 落库验证必须用 **CTE set_config 配方** (per [mcp_pg_rls_caveat])
- 后端 pytest 用 `--tb=short -q` 模式跑 (per dev R4)
- dev 报告必走 [feedback_dev_report_truthfulness] 4 grep 硬约束 (实际命令输出 + 不发虚数)

**Phase 2 dev 必跑** (15 steps):
1. 写 backend/scripts/probe_v2_endpoints.sh 或 inline httpx script (US8 5 endpoint)
2. 跑 pytest: `cd backend && uv run pytest app/modules/resumes_v2/tests/ -v --tb=short -q` (11 文件, 期望 0 failure)
3. 跑 HTTP probe: 5 endpoint × 3 case (happy + error + edge) = 15 actual request
4. 跑 mcp__postgres__query 5 DB 写操作 (含 CTE set_config, 含 UPSERT 2 次)
5. 跑 15 静态断言 checklist (Phase 2 § "静态断言 checklist")
6. 跑 typecheck + L8 shadow 检查
7. 报告: AC 命中表 + 实际命令输出 + Honesty declaration
8. 任何 FAIL → triage + 可能修后端 (e.g. lock 跨用户实际 403 vs 404 反例发现)

**tester red-team 后续**:
- Phase 2 dev 完成后, 派 tester 跑 AC 逐条 + 4 grep + pytest + DB 落库 (per feedback_dev_report_truthfulness)
- 派 reviewer 静态约束审查 + 类型 + RLS
- dual PASS → main-agent 代行 commit

