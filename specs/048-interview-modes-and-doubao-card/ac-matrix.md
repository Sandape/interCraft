---
req_id: REQ-048
status: locked
locked_at: 260707 0952
locked_by: negotiation
negotiation_rounds: 3
---

# Acceptance Matrix for REQ-048 (Interview Mode Split + Doubao Card Export)

> AC 起草者：dev agent (mode=ac-proposal)
> 起草日期：2026-07-07
> 来源：spec.md 6 个 US + 22 条 SC + 50+ FR + 8 Edge Cases，按 US 聚合而非按 SC 逐条复制

---

## SC Gaps

无（spec.SC 完整 22 条覆盖 4 个能力域：模式选择可用性 / 错题筛选质量 / 完整面试体验 / 豆包卡片质量 / 错题本联动；Edge Cases 8 个覆盖降级 / 缓存 / 超时）。建议：

- US6（错题本联动）虽标 P2 但用户已明确要求"快速补漏闭环"，建议 AC 矩阵至少包含 2 条核心 AC（UPSERT 语义 + regression 反向迁移），而非整段 deferred
- Phase 9 polish 不在 AC 范围（quickstart E2E 隐含覆盖）
- 卡片渲染性能 SC-030 (p95 ≤5s) 与文件大小 SC-031 (≤300KB) 合并为一条 AC
- cache 命中率 SC-013 由 quickstart QS-4 perf script 实测，独立成一条 AC

---

## AC 矩阵

### User Story 1 — Choose Interview Mode at Start (P1)

| AC-ID | 描述 | 验证方式（命令/测试名/可观测指标） | 来源 (spec.SC/FR) | 边界覆盖 |
|-------|------|-----------------------------------|---------------------|----------|
| AC-01 | demo 账号在「新建面试」完成岗位参数后，必须看到「在线 AI 面试」/「豆包面试」两个并列入口卡片；选「在线 AI 面试」展开二级「快速补漏」+「完整面试」；选「豆包面试」直接进入 Planner 出卡片（无二级选项） | `cd backend && uv run pytest -q tests/integration/test_us1_mode_selection.py -k "two_top_level_or_doubao_no_suboptions" -v` 期望 PASS；`npm run e2e -- tests/e2e/mode-selection.spec.ts -g "renders two top-level cards"` 期望 PASS | FR-001, FR-002, FR-004, US-1.AS1 | empty/error (no job selected → 422) |
| AC-02 | demo 账号错题集 < 5 道时，「快速补漏」入口必须置灰 + hover 提示「先做完一次面试，错题集有题才能补漏」；URL 直接绕过调用 POST /api/v1/interviews 返回 422 + `INSUFFICIENT_ERROR_POOL` | `cd backend && uv run pytest -q tests/contract/test_interview_mode_contract.py::test_insufficient_error_pool_returns_422 -v` 期望响应含 `ctx.available<5`；`npm run e2e -- tests/e2e/mode-selection.spec.ts -g "quick_drill disabled when <5 errors"` 期望 toast 出现 + Playwright `.locator('[data-testid=quick-drill]').isDisabled() AND locator('[role=tooltip]').toHaveText('先做完一次面试，错题集有题才能补漏')` | FR-002, US-1.AS2, Edge-1 | empty (error_count=0) + null (no errors table) |
| AC-02b | 「快速补漏」入口置灰时 hover tooltip 文案必须精确等于「先做完一次面试，错题集有题才能补漏」（zh-CN 全角标点、不可英文/拼错）| `npm run e2e -- tests/e2e/mode-selection.spec.ts -g "quick_drill hover tooltip shows exact zh-CN text"` 期望 `await page.locator('[data-testid=quick-drill]').hover() + expect(page.locator('[role=tooltip]')).toHaveText('先做完一次面试，错题集有题才能补漏')` | FR-002, US-1.AS2 | 文本可观测性 |
| AC-03 | 「面试方式」返回上一步修改岗位参数时，模式选择 state 必须清空（Zustand store reset）；重新进入模式选择时之前选过的 mode 不可残留 | `cd backend && uv run pytest -q tests/integration/test_us1_mode_selection.py::test_mode_state_reset_on_position_back -v`；前端单测 `npm run test -- --run src/stores/useInterviewModeStore.test.ts` 期望调用 `reset()` 后 store.mode === null | FR-005, US-1.AS3 | state pollution（残留） |

### User Story 2 — Quick Drill Mode: Hybrid Error-Question Selection (P1)

| AC-ID | 描述 | 验证方式 | 来源 | 边界覆盖 |
|-------|------|----------|------|----------|
| AC-03b | demo 账号在模式选择页按 F5（page.reload）→ 状态清空 + 跳转回 `/interviews/new`（Edge-8 显式断言）| `npm run e2e -- tests/e2e/mode-selection.spec.ts -g "F5 refresh clears mode state and redirects to interview create"` 期望 `page.reload() → expect(page).toHaveURL(/\/interviews\/new$/)` | FR-005, Edge-8 | 浏览器刷新（前端 store 无 persist）|
| AC-04 | demo 账号（≥50 错题跨 5 个 dimension）选「在线 AI 面试 + 快速补漏」+ 指定 JD「分布式事务/微服务/RAG」时，系统在 p95 ≤3s 内返回 5 道题；至少 3 题 dimension 与 JD 关键词命中 | `cd backend && uv run python -m scripts.perf_test_drill --users 20 --iterations 5` 输出 `p95 ≤ 3.0s`（quickstart QS-4 脚本）；`cd backend && uv run pytest -q tests/integration/test_us2_drill_e2e.py::test_dimension_distribution_aligns_jd -v` 期望 ≥3/5 命中；hash(JD + error_pool_hash) 一致时复用，任意字段变化触发 miss（见 AC-09b）| SC-010, SC-011, FR-012, US-2.AS1, US-2.AS2 | 性能 p95 + 准确率 |
| AC-04b | JD 关键词「分布式事务」必须命中 dimension ∈ {distributed_systems, architecture} ≥1 题（关键词→dimension map 显式存 `specs/048-interview-modes-and-doubao-card/keyword-dimension-map.md`，**T094 必须先于 T044-T062 (US2 测试) 完成**；如 T094 schedule 在 Phase 6 > Phase 4，本 AC 测试套件必须用 inline fixture 兜底 — 内置 10 个关键词→dimension 映射如 `分布式事务→distributed_systems` / `微服务→architecture` / `RAG→tech_depth` 等 + 后续契约锁定；`--eval-set` 路径统一为「T094 输出后才知道」型软引用）| `cd backend && uv run pytest -q tests/integration/test_us2_drill_e2e.py -k drill_e2e -v` 用 `@pytest.mark.skipif(not eval_set_exists(), reason="T094 outputs")` 守卫，CI 启动时 `pytest -k drill_e2e` 自动 skip 但 leave 5-case inline 兜底集（AC-04c） | SC-011, FR-012, US-2.AS2, R-10, R-17 | dimension 命中可观测 + 文档未建 fallback |
| AC-05 | 100 道/500 道错题场景下，Hybrid 检索 top-5 与 ground truth（`docs/evidence/048-interview-modes-and-doubao-card/drill-eval-set.md` 20 组人工标注，T094 产物）重合度 ≥70%；T094 未建时 `--eval-set` 路径自动 skip，兜底见 AC-04c | `cd backend && uv run python -m scripts.eval_drill_accuracy --eval-set docs/evidence/048-interview-modes-and-doubao-card/drill-eval-set.md --error-counts 100,500` 输出 `accuracy ≥ 0.70` 两个 scenario 全过；`@pytest.mark.skipif(not eval_set_exists(), reason="T094 outputs")` 守卫 | SC-012, FR-012, R-17 | scale（100/500 错题集）+ 文档未建 fallback |
| AC-04c | **inline fixture 兜底**：T094 未生成时，测试套件内置 5 个 (JD 关键词, expected_dimension) case：`[("分布式事务", "distributed_systems"), ("微服务", "architecture"), ("RAG", "tech_depth"), ("分布式锁", "distributed_systems"), ("服务降级", "architecture")]`；AC-04c 通过即 T094 之前的 contract 锁定 | `cd backend && uv run pytest -q tests/integration/test_us2_drill_e2e.py::test_inline_keyword_dimension_fixture -v`（需新增）期望 5/5 case 命中 | SC-011, FR-012, R-17 | inline 兜底集 |
| AC-06 | embedding service 不可用时（HTTPX MockTransport 拦截 embedding service 的 `/embed` 端点返回 503），Hybrid 降级为「BM25 top-50 → bge-reranker-v2-m3 精排 top-5」；UI 顶部 toast 显示「错题匹配精度下降」；analytics_events 写入 `drill_degraded_to_bm25` 1 行 | `cd backend && uv run pytest -q tests/unit/agents/interview/test_drill_degradation.py::test_mock_embed_503_fallback -v`（需新增，使用 `httpx.MockRouter` 拦截 `/embed`）；`PGPASSWORD=$DB_PASS psql -c "SELECT count(*) FROM analytics_events WHERE event_type='drill_degraded_to_bm25';"` 期望 ≥1（quickstart QS-2 Scenario D） | FR-013, Edge-2 | 服务降级（503 mock） |
| AC-07 | bge-reranker-v2-m3 不可用时（HTTPX MockRouter 拦截 embedding service 的 `/rerank` 端点返回 500），重试 1 次失败后降级为「BM25 top-5 ∪ bge-small cosine top-5 → LLM listwise rerank top-5」；analytics 写 `drill_degraded_to_llm_rerank` | `cd backend && uv run pytest -q tests/unit/agents/interview/test_drill_degradation.py::test_mock_rerank_500_fallback -v`（需新增，使用 `httpx.MockRouter` 拦截 `/rerank`）；`psql -c "SELECT event_type FROM analytics_events ORDER BY created_at DESC LIMIT 1;"` 期望 `drill_degraded_to_llm_rerank` | FR-014, Edge-3 | 服务降级（reranker mock 500） + LLM 配额回退 |
| AC-08 | embedding + reranker 同时不可用时，完全降级为「BM25 top-5」直接返回（无任何精排）；toast 显示「错题匹配回退到基础模式」 | `cd backend && uv run pytest -q tests/unit/test_drill_degradation.py::test_both_down_falls_back_to_bm25_only -v` | Edge-4 | 双服务全故障 |
| AC-09 | 同一 (user_id, job_id) 在 5 分钟内二次点「快速补漏」，复用同一组 5 道题（缓存命中）；hash(JD + error_pool_hash) 一致时复用，任意字段变化触发 miss；缓存命中率 ≥80%（1h 窗口 100 用户场景）；超过 5min 自动失效 | `cd backend && uv run python -m scripts.measure_drill_cache_hit --window 1h --users 100` 输出 `cache_hit_rate ≥ 0.80`（quickstart QS-4）；`cd backend && uv run pytest -q tests/unit/test_drill_cache.py::test_ttl_5min_expiry -v` 用 `time.sleep(301)` 验证过期；hash 范围测试见 AC-09b | FR-015, SC-013, US-2.AS3 | cache TTL + 命中率 |
| AC-09b | 同一 (user_id, job_id) 在 5 分钟内，JD 文本变化或 error_pool 变化必须触发 cache miss 返回新 5 题（spec FR-015 `cache key = hash(JD + error_pool_hash)`）；**同一 JD+error_pool 输入两次，Redis key 完全相等的 assertion**（hash 算法一致性 — SHA256，AC-09c 锁定）| `cd backend && uv run pytest -q tests/unit/test_drill_cache.py::test_cache_key_includes_jd_and_pool_hash -v`（需新增）；构造同 job_id 但 position 变化 → 期望 candidates 哈希全变；插入新错题 → 同 position 也期望 candidates 不同；同一输入两次 → `redis-cli GET drill_cache:{user_id}:{key_hex1}` 应等于 `redis-cli GET drill_cache:{user_id}:{key_hex2}` | FR-015, SC-013, R-18 | cache key hash 完整性 + 算法一致性 |
| AC-09c | **cache key 计算公式锁定**：`sha256(jd_text.encode('utf-8') + error_pool_hash.encode('utf-8'))[:32]` 取前 32 字符 hex，附加 user_id 前缀为 `drill_cache:{user_id}:{key_hex}`（hash 算法 = SHA256，避免 murmurhash3 / blake2b 跨服务漂移）；data-model.md L97 同步锁定此公式 | `cd backend && uv run pytest -q tests/unit/test_drill_cache.py::test_cache_key_formula_sha256 -v`（需新增）；直接 SQL `redis-cli KEYS "drill_cache:{user_id}:*"` 期望 key 长度 = `len("drill_cache:") + 36 (uuid) + 1 (:) + 32 (hex) = 70` | FR-015, SC-013, R-18 | hash 算法 + key 长度锁定 |
| AC-10 | JD 为空（用户没选岗位）时，错题筛选退化为「按 frequency 倒序取 5 道」；前端 toast 提示「未指定岗位，已选错题练习」 | `cd backend && uv run pytest -q tests/integration/test_us2_drill_e2e.py::test_no_jd_falls_back_to_frequency -v` 期望 candidates 按 `frequency DESC` 排序 | Edge-5 | null JD |
| AC-11 | backfill：T-NEW-2 脚本运行后，`SELECT COUNT(*) FROM error_questions WHERE embedding IS NOT NULL` 必须 = total count（不允许遗漏历史错题） | `cd backend && uv run python -m scripts.backfill_embeddings && PGPASSWORD=$DB_PASS psql -c "SELECT COUNT(*) FILTER (WHERE embedding IS NULL), COUNT(*) FROM error_questions;"` 期望 `0 / N` | FR-010, FR-011 | 冷启动 backfill |
| AC-11b | 新错题写入后 30 秒内必须异步计算 embedding 落库（依赖 arq worker 正常运行）；**CI smoke 跑前先预热 arq worker**：`arq app.workers.main.WorkerSettings` 启动后跑一次 `INSERT INTO error_questions (dummy) RETURNING id` 触发 warm-up 30 秒（python 解释器初始化 + 加载 bge-small-zh-v1.5 ~10s + arq 注册 ~1s），再开始正式 assertion | `cd backend && uv run pytest -q tests/integration/test_embedding_pipeline.py::test_arq_enqueue_on_new_error_question -v`（需新增，T048/T-NEW-1 路径覆盖）；流程：`INSERT INTO error_questions ... RETURNING id` → 30 秒内 `SELECT embedding FROM error_questions WHERE id=$1` 应非 NULL；warm-up 流程：`arq app.workers.main.WorkerSettings & sleep 30 && PGPASSWORD=$DB_PASS psql -c "INSERT INTO error_questions (user_id, question_text) VALUES (...) RETURNING id"` | FR-011, FR-013, R-20 | arq worker race + cold start |
| AC-11c | **cold / warm 路径分离**: cold start（首次 INSERT 后 60 秒内必须 compute_embedding，后续 INSERT 30 秒内），区分 cold/warm SLO；冷启动重跑 3 次期望至少 2/3 pass（CI flaky 容忍）| `cd backend && uv run pytest -q tests/integration/test_embedding_pipeline.py::test_cold_warm_split_slo -v`（需新增）；验证：`cd backend && arq app.workers.main.WorkerSettings & sleep 60 && PGPASSWORD=$DB_PASS psql -c "SELECT count(*) FROM error_questions WHERE embedding IS NULL AND created_at > now() - interval '5 min';"` 期望 0 rows（cold start）；后续 INSERT 期望 30 秒内 | FR-011, R-20 | cold/warm SLO 分离 |

### User Story 3 — Full Interview Mode: 10-15 Questions with Agent-Controlled Depth (P1)

| AC-ID | 描述 | 验证方式 | 来源 | 边界覆盖 |
|-------|------|----------|------|----------|
| AC-12a | `effective_max = max(MIN_QUESTIONS=7, min(user_choice, planner_recommended))` 常数边界：user=10,planner=10 → 10；user=15,planner=15 → 15；user=10,planner=5 → 7（命中硬下限）；user=15,planner=20 → 15（命中硬上限）| `cd backend && uv run pytest -q tests/unit/test_effective_max.py::test_boundary_constants -v` 4 个常数 boundary assertion 全 PASS；**migration 0028 约束形态**：`ALTER TABLE interview_sessions ADD COLUMN max_questions CHECK (max_questions BETWEEN 7 AND 15) NOT VALID` 必须存在（避免对历史 legacy 行 `max_questions=5` 触发 CheckViolation）；事后 `PGPASSWORD=$DB_PASS psql -c "ALTER TABLE interview_sessions VALIDATE CONSTRAINT interview_sessions_max_questions_check"` 必须通过（直接 SQL 断言 0028 migration 行为） | FR-023, R-6, R-16 | 常数边界值（含 hard min/max）+ migration 风险 |
| AC-12b | `effective_max` 动态边界（FR-023 focus_areas × 3-5 题）：user=10,planner=8 → 8；user=15,planner=9 → 9；user=10,planner=12 → 10（planner>user，命中 user）；user=15,planner=14 → 14 | `cd backend && uv run pytest -q tests/unit/test_effective_max.py::test_planner_recommended_dynamic_7_to_15 -v`（需新增）4 个 dynamic assertion 全 PASS | FR-023, US-2.AS1 | planner 落在 7-15 中间 |
| AC-13 | 「中等（10 题）」模式下 90% 面试实际生成 9-11 题；「深入（15 题）」模式下 90% 面试生成 13-15 题；Wilson score 95% CI 下限 ≥ 0.85（L007 历史教训 — 100 轮 90% 点估计标准误 ≈3%，固定点估计 0.90 统计过严）| `cd backend && uv run python -m scripts.distribution_test_full_interview --rounds 200 --confidence 0.95` 期望两个档位 Wilson 下限 ≥ 0.85 | SC-020, SC-021 | 统计分布 + Wilson CI |
| AC-14 | 自适应收尾：score ≥ 8.0 连续 3 题 + current ≥ effective_max - 3 时提前生成报告；中等 10 题档最早 7 题收尾；深入 15 题档最早 12 题收尾；硬下限 7 即使条件满足也禁止提前（current=6 → MUST NOT terminate）| `cd backend && uv run pytest -q tests/unit/test_adaptive_termination.py -v` 覆盖 3 个 case：current=7 + 3 consecutive ≥8.0 → 终止；current=12 + 3 consecutive ≥8.0 → 终止；current=6 + 3 consecutive ≥8.0 → 不终止 | SC-022, FR-021, FR-022, US-3.AS2 | 边界（硬下限保护）|
| AC-15 | 完整面试 score < 6 时仍走原 sink_error 路径（与现状一致，行为不变）；legacy session (`mode='full'`, `max_questions=5`) 经过 effective_max 计算后实际展示为 7 题 + 历史报告数据不被破坏（migration 0028 默认值兼容性）；**migration smoke**: `cd backend && uv run alembic upgrade head 2>&1 | grep -E "CheckViolation|constraint" | head -5` 期望无输出（CI 级别 migration smoke test，0028 步骤不报 CheckViolation）| `cd backend && uv run pytest -q tests/integration/test_us3_full_interview.py::test_low_score_routes_to_sink_error -v` 期望 sink_error 被调用 + 现有 status 状态机迁移；`cd backend && uv run pytest -q tests/integration/test_us3_full_interview.py::test_legacy_session_effective_max_override -v` 构造 legacy session 期望 `compute_effective_max(session_id) == 7` | US-3.AS3, FR-040, data-model.md 第 26 行, R-16 | 兼容性（旧路径不破 + legacy 迁移 + migration smoke）|
| AC-16 | Playwright E2E：demo 账号选「完整面试（中等 10 题）」走完 → 验证 report.per_question_score 长度 9-11 且维度分布 ≥3 个不同 dimension | `npm run e2e -- tests/e2e/full-interview-15.spec.ts -g "complete 10 questions"` 期望 PASS；后端 `psql -c "SELECT jsonb_array_length(per_question_score) FROM interview_reports WHERE session_id=...;"` 期望 9-11 | SC-020, US-3 AS | 端到端 + 报告 schema |
| AC-16b | 并发 2 个 full interview 同一 user：两 session 的 `current_question` 计数器互不干扰（LangGraph checkpointer 按 thread_id 隔离 OK）+ sink_error 并发 UPSERT 不会丢更新（`last_practiced_at` 行级锁或 WHERE 条件保护）；**sink_error 原子写入**: 用 `UPDATE error_questions SET last_practiced_at = $new_now WHERE source_question_id = $A AND last_practiced_at <= $new_now RETURNING ...` 保证读后写原子（或 `SELECT ... FOR UPDATE NOWAIT`）；**late-writer 不覆盖** assertion：`last_practiced_at` 必须等于 N 个 timestamp 中最大者（验证晚到者不覆盖早到者）| `cd backend && uv run pytest -q tests/integration/test_us3_full_interview.py::test_concurrent_termination_window_isolation -v`（需新增，asyncio.gather 跑 2 个 session）；`cd backend && uv run pytest -q tests/integration/test_us6_drill_resink.py::test_concurrent_last_practiced_at_serializable -v`（需新增，asyncio.gather 跑 3 个 sink_error 同一 source_question_id，期望 final `last_practiced_at` = max(三个 now())，且 PG WAL 显示 3 次 UPDATE 都 commit） | FR-040, R-14, R-19 | 并发 isolation + late-writer 保护 |

### User Story 4 — Doubao Card Generation & Export (P1)

| AC-ID | 描述 | 验证方式 | 来源 | 边界覆盖 |
|-------|------|----------|------|----------|
| AC-17a | Planner 生成 InterviewPlan 后，前端调 GET /api/v1/interviews/{session_id}/card 在 p95 ≤5s 内返回 4:3 (1080×810) JPG ≤300KB；卡片含岗位标题、公司、难度 badge、时长、5-8 条大纲、InterCraft 水印 | `cd backend && uv run pytest -q tests/integration/test_us4_card_render_e2e.py -v` 验证 image_bytes < 300*1024 + 字段齐全；`cd backend && uv run python -m scripts.test_card_file_size --size 4_3` 输出 `≤300KB` | SC-030, SC-031, FR-051, FR-053, FR-062, US-4.AS1 | 4:3 性能 + 文件大小 + 字段完整性 |
| AC-17b | 切换为 9:16 (1080×1920) 时复用同一 InterviewPlan 重渲染（不重跑 Planner）；7-8 条大纲 + 2 段分段标题场景下文件 ≤300KB（像素数 ≈ 4:3 的 2.37 倍，独立验证防漏验）| `cd backend && uv run python -m scripts.test_card_file_size --size 9_16 --max-outlines 8` 期望 `<=300*1024 bytes`；`cd backend && uv run pytest -q tests/unit/test_card_renderer_9x16.py::test_max_outlines_8_with_section_titles -v` 验证宽=1080, 高=1920 + 含分段标题 | SC-031, FR-052, US-4.AS2 | 9:16 大文件防超 |
| AC-18 | 切换为 9:16 (1080×1920) 时复用同一 InterviewPlan 重渲染（不重跑 Planner）；含分段标题分隔；前端按钮可见 | `cd backend && uv run pytest -q tests/unit/test_card_renderer_9x16.py -v` 验证宽=1080, 高=1920 + 含分段标题；`npm run e2e -- tests/e2e/doubao-card.spec.ts -g "switch to 9:16"` | SC-031, FR-052, US-4.AS2 | variant 切换 |
| AC-19 | 卡片生成成功时，analytics_events 表新增 1 行（user_id + plan_id + rendered_at + size_variant），payload 不含任何对话内容（Q4=B 决策）；直接 SQL 断言 `payload ? 'question_text' = false AND payload ? 'score' = false AND payload ? 'answer' = false` | `PGPASSWORD=$DB_PASS psql -c "SELECT payload FROM analytics_events WHERE event_type='doubao_card_rendered' AND (payload ? 'question_text' OR payload ? 'score' OR payload ? 'answer');"` 期望 0 rows；`psql -c "SELECT event_type, payload->>'size_variant', payload->>'duration_ms' FROM analytics_events WHERE event_type='doubao_card_rendered' ORDER BY created_at DESC LIMIT 1;"` 期望 size_variant ∈ {'4_3','9_16'} | FR-055, US-4.AS3, Edge-4 | 隐私（无对话内容 + 黑名单字段断言）|
| AC-19b | `doubao_card_rendered` 事件的 payload 禁止字段白名单审计：`{question_text, score, answer, expected_points, interview_plan}` 全部不能存在 | `cd backend && uv run python -m scripts.assert_analytics_pii_free --event-type doubao_card_rendered --forbidden-keys question_text,score,answer,expected_points,interview_plan` 期望退出码 0（需新增脚本）| FR-055, R-6 | PII 全字段审计 |
| AC-20 | 「复制大纲文本」剪贴板内容可被文本识别工具完整还原：Markdown 格式 `# 面试大纲\n## 公司: ...\n## 岗位: ...\n## 大纲: 1. ... 2. ...` | `cd backend && uv run pytest -q tests/unit/test_card_markdown.py -v` 验证生成 markdown 包含 5-8 个 numbered item；Playwright `await page.evaluate(() => navigator.clipboard.readText())` 期望格式合规 | SC-034, FR-054, US-4.AS4 | OCR 完整还原 |
| AC-21 | 文字字号下限 ≥24px、关键标题 ≥64px（模板编译时静态分析：解析 satori JSX 模板中所有 `fontSize` 属性，纯 AST 检查不依赖 PNG OCR/Tesseract）；卡片背景不透明（非 alpha=0）；**4 种间接字号路径覆盖**: inline `style={{ fontSize: X }}` / `className="..."` CSS 类引外部 stylesheet / `style={{ fontSize: 'var(--title-size)' }}` CSS 变量 / `<h1>`-`<h6>` 标签默认字号（`<h1>` = 32px < 64px 必需 → AC-21 FAIL 除非显式 inline 声明）；具体断言：「标题节点字号（`<h1>` 默认 32px → AC-21 FAIL 因 ≥64 必需）必须用 inline `style={{fontSize: X}}` 显式声明 ≥64」+ 独立 metric `<h1>` 使用次数=0 或全用 inline 标题字号 ≥64 | `cd backend && uv run python -m scripts.ast_check_card_font_size --templates backend/app/services/card_renderer/templates/{card_4x3,card_9x16}.tsx --check-inline-style --check-h1-default --check-css-variable --check-classname --min-inline 64` 期望 `min_font_size ≥ 24, max_title_size ≥ 64, h1_count_with_default == 0` | SC-032, FR-060, FR-061, R-13, R-21 | 豆包 OCR 防截断（CI 友好）+ 4 种间接路径 |
| AC-22 | Planner 子图超时（>30s）或卡片渲染失败时返回明确错误码 `INTERVIEW_PLAN_NOT_READY`（422）/ `CARD_RENDER_FAILED`（500），前端显示「卡片生成失败」+ 「复制大纲文本」按钮仍可用 | `cd backend && uv run pytest -q tests/integration/test_us4_doubao_mode.py -k "timeout or render_failed" -v` 期望 HTTP 状态码 + `trace_id` 非空 | FR-056, Edge-6, Edge-7 | 超时 + 渲染失败降级 |
| AC-23 | 「豆包面试」模式在 Planner 后立即停止（不进入 question_gen / score_llm / report 节点）；OTel span `interview.doubao_early_stop` 出现；`interview_sessions` 写入 1 行（mode='doubao' + thread_id + user_id），但不进入 question_gen/score_llm/report 节点（用于 session_id 回传前端调 /card）| `cd backend && uv run pytest -q tests/integration/test_us4_doubao_mode.py::test_no_question_gen_invoked -v` 验证 graph execution 仅含 4 个节点（intake/planner_context/planner_search/planner_generate）+ OTel span filter 命中；`psql -c "SELECT count(*) FROM interview_sessions WHERE mode='doubao';"` 期望 = 1（session 行存在） | FR-050, R-7, R-9 | LangGraph 路由边界 + session 行保留 |
| AC-24 | 卡片输出缓存：hash(JD + plan fields) → 7d TTL；二次请求同 JD+plan 命中缓存（X-Card-Cache-Hit: true），返回时间 < 50ms | `cd backend && uv run pytest -q tests/unit/test_card_cache.py::test_7day_ttl_cache_hit -v`；`curl -i /api/v1/interviews/{sid}/card?cache_key=...` 期望响应头含 `X-Card-Cache-Hit: true` | FR-063, SC-031 (附) | 缓存命中 + TTL |

### User Story 5 — Drill Mode Question Variant Toggle (P2, 简化合并)

| AC-ID | 描述 | 验证方式 | 来源 | 边界覆盖 |
|-------|------|----------|------|----------|
| AC-25 | 「快速补漏」默认原题重考；UI 提供「换种问法」toggle；切换后变体生成节点对每道错题调 LLM 一次生成新 question_text；原 expected_points + dimension 保留；变体生成失败（LLM 异常）降级为原题重考 + analytics 写 `variant_generation_failed`；**默认 `use_variants=false`（不传或 false）必须走原题重考**（question_text 一字不差，非变体 — FR-031 合同硬约束；contracts/http-api.md C-1 request schema `use_variants: bool = false` default 显式标注）| `cd backend && uv run pytest -q tests/integration/test_us5_variant_mode.py -v` 验证 question_text 变化 + dimension 字段恒等；`cd backend && uv run pytest -q tests/unit/test_variant_degradation.py::test_llm_failure_falls_back_to_original -v` 期望 fallback + analytics 事件；`cd backend && uv run pytest -q tests/integration/test_us5_variant_mode.py::test_default_no_variants_flag_uses_original -v`（需新增）逻辑：`POST /api/v1/interviews {mode: quick_drill, use_variants: false|undefined}` → 期望 `error_question_ids[*].question_text == error_questions[source_question_id].question_text`（一字不差）| FR-031, FR-032, FR-033, US-5.AS1, US-5.AS2, US-5.AS3, R-22 | LLM 故障降级 + default 行为路径 |

### User Story 6 — Error Re-Sink on Low Score in Drill Mode (P2, 简化合并) ⏳ 部分 deferred

| AC-ID | 描述 | 验证方式 | 来源 | 边界覆盖 |
|-------|------|----------|------|----------|
| AC-26 | 「快速补漏」+ raw_score < 6 时复用现有 sink_error 节点，但改写为「按 source_question_id UPSERT + frequency 状态机迁移」；source_session_id 字段**保持原值不回写**；last_practiced_at 刷新；A/B 错题从 status=fresh 迁移至 reviewing + frequency=2 | `cd backend && uv run pytest -q tests/integration/test_us6_drill_resink.py -v` 验证 source_session_id 未变 + status 迁移；`cd backend && uv run pytest -q tests/unit/test_sink_error_upsert.py::test_upsert_keeps_source_session_id -v` | FR-040, FR-041, FR-042, US-6.AS1, US-6.AS3 | UPSERT 不污染 + 状态机迁移 |
| AC-27 | 错题 status=mastered 时用户 raw_score=4 → 状态机反向迁移至 reviewing + analytics 写 `drill_resink_completed` 包含 `regression_detected=true` 字段 | `cd backend && uv run pytest -q tests/unit/test_error_regression.py::test_mastered_to_reviewing_regression -v`；`psql -c "SELECT payload->>'regression_detected' FROM analytics_events WHERE event_type='drill_resink_completed';"` 期望 `true` | FR-041, US-6.AS2, A-007 | regression 反向迁移 |
| AC-28 | ⏳ deferred：完整 US6 包含 UPSERT 失败重试 + RLS policy 验证 + regression 多 case 覆盖。本 AC 矩阵保留核心 2 条（AC-26/27）+ AC-29（T111 已升级为强制 AC），其余 T110 留 Phase 8 实施时补 AC | （本 AC 不写，仅记录 deferred 范围） | US-6.P2 | n/a |
| AC-29 | `sink_error` 节点写入路径绝不能修改 `error_questions.source_session_id`（spec FR-042 硬约束）：`UPDATE error_questions SET source_session_id = $S2 WHERE source_question_id = $A AND source_session_id = $S1` 必须 0 rows affected（直接 SQL 断言，非 service mock；T111 已升级为强制 AC，从 deferred 移出）| `cd backend && uv run pytest -q tests/integration/test_us6_drill_resink.py::test_source_session_id_immutable_in_db -v`（需新增） | FR-042, T111, R-8 | DB 字段 immutability 直接断言 |

---

## AC 总数统计

- US1（模式选择）: AC-01, AC-02, AC-02b, AC-03, AC-03b = **5 条**
- US2（快速补漏）: AC-04, AC-04b, AC-04c, AC-05 ~ AC-09, AC-09b, AC-09c, AC-10, AC-11, AC-11b, AC-11c = **13 条**
- US3（完整面试 10-15）: AC-12a, AC-12b, AC-13, AC-14, AC-15, AC-16, AC-16b = **7 条**
- US4（豆包卡片）: AC-17a, AC-17b, AC-18, AC-19, AC-19b, AC-20, AC-21, AC-22, AC-23, AC-24 = **10 条**
- US5（变体 toggle）: AC-25 = **1 条**
- US6（错题联动）: AC-26, AC-27, AC-29 + AC-28 deferred = **3 条活跃 + 1 deferred**

**总计 40 条活跃 AC + 1 条 deferred（AC-28）**；覆盖 5 个 P1 US（US1/2/3/4）+ 2 个 P2 US（US5/US6）。

### Round 3 修订映射（2026-07-07，末轮）

| 反驳 | 修订类型 | AC 影响 |
|---|---|---|
| R16 | 改写 | AC-12a + AC-15 (migration 0028 NOT VALID 约束 + alembic smoke)；data-model.md L21 同步 NOT VALID + VALIDATE |
| R17 | 改写 + 新增 | AC-04b + AC-05 改（`@pytest.mark.skipif` 守卫）+ AC-04c 新（inline 5-case fixture 兜底集）|
| R18 | 改写 + 新增 | AC-09b 改（同一输入 Redis key 相等 assertion）+ AC-09c 新（SHA256 + user_id 前缀公式）；data-model.md L97 + contracts/http-api.md C-3 同步公式 |
| R19 | 改写 | AC-16b 增（`UPDATE ... WHERE last_practiced_at <= $new_now` + late-writer 不覆盖 assertion + test_concurrent_last_practiced_at_serializable）|
| R20 | 改写 + 新增 | AC-11b 改（warm-up 30s）+ AC-11c 新（cold 60s / warm 30s SLO 分离）|
| R21 | 改写 | AC-21 增（4 种间接字号路径：inline/className/CSS 变量/`<h1>`）+ `--check-inline-style --check-h1-default --check-css-variable --check-classname --min-inline 64` |
| R22 | 改写 | AC-25 增（default `use_variants=false` 必须走原题重考）+ test_default_no_variants_flag_uses_original；contracts/http-api.md C-1 同步 default 标注 |

净变化：37 + 3 新增（04c/09c/11c）+ 9 改写 = **40 条活跃 AC**。

### Round 2 修订映射（2026-07-07）

| 反驳 | 修订类型 | AC 影响 |
|---|---|---|
| R1 | 改写 | AC-06/07 (HTTPX MockTransport) |
| R2 | 改写 + 新增 | AC-09 改 + AC-09b 新 |
| R3 | 拆分 | AC-12 → AC-12a + AC-12b |
| R4 | 改写 | AC-13 (Wilson CI 0.85) |
| R5 | 拆分 | AC-17 → AC-17a + AC-17b |
| R6 | 改写 + 新增 | AC-19 改 + AC-19b 新 |
| R7 | 改写 + 改 contracts | AC-23 + contracts/http-api.md C-1 注释 |
| R8 | 新增 + 移除 deferred | AC-29 新，T111 移出 AC-28 |
| R9 | 改写 + 新增 | AC-02 改 + AC-02b 新 |
| R10 | 新增 | AC-04b 新（keyword-dimension-map.md T094）|
| R11 | 新增 | AC-11b 新（arq race）|
| R12 | 改写 | AC-15 + legacy 迁移 |
| R13 | 改写 | AC-21（静态 AST 替代 PNG OCR）|
| R14 | 新增 | AC-16b 新（并发 isolation）|
| R15 | 新增 | AC-03b 新（F5 refresh）|

净变化：27 + 10 新增（02b/03b/04b/09b/11b/16b/19b/29 = 8） + 拆分净 +2（12a+12b, 17a+17b）= **37 条活跃 AC**。

---

## 起草说明（写给 tester）

### 设计意图

1. **聚合原则**：按 US 而非按 SC 复制。22 条 SC 中重复性质（如 p95 / 命中率 / 降级路径）合并为单条 AC 的不同断言，避免 token 翻倍（L007 教训）
2. **边界覆盖**：每条 AC 至少覆盖 1 类边界（empty / null / timeout / 降级 / 缓存命中 / scale / 边界值 / 隐私 / 兼容性）
3. **降级路径独立成条**：embedding 不可用（AC-06）/ reranker 不可用（AC-07）/ 双不可用（AC-08）三条独立，避免单条 AC 多分支膨胀
4. **证据路径统一**：quickstart QS-4 perf 脚本 + docs/evidence/048/sample-cards/ + scripts.backfill_embeddings 作为可复用的验证工具
5. **FR-023 边界值独立**：AC-12 用 4 个 boundary assertion 覆盖 effective_max 公式（clarify round 2 引入，避免 FR-021 软上限模糊）
6. **SC-034（剪贴板可还原）** 写进 AC-20 而非另立，因为「复制大纲 Markdown」是 US4.AS4 的一部分
7. **US6 不全 deferred**：保留 2 条核心（UPSERT 不污染 + regression 反向迁移），因为「快速补漏」闭环价值依赖此闭环；其余 T110/T111 在 Phase 8 实施时再补 AC
8. **回归反例（mastered→reviewing）单列**：AC-27 独立保证 FR-041 + A-007 风险点被测试盯住，避免 1 行 PR 漏测
9. **SC-031（卡片 ≤300KB）** 与 SC-030（p95 ≤5s）合并到 AC-17，因为同一条端到端验证脚本 `test_card_file_size` 输出两者
10. **隐私合规（FR-055 不存对话内容）** 写进 AC-19，payload 黑名单字段检查（question_text/score/answer 不在 payload）

### 已覆盖的边界

| 边界类型 | 覆盖 AC |
|---|---|
| empty/null | AC-02 (error<5), AC-10 (no JD), AC-25 (no LLM) |
| timeout | AC-22 (Planner>30s) |
| 服务降级 | AC-06, AC-07, AC-08 (embedding/reranker/both), AC-25 (LLM fallback) |
| 缓存命中 | AC-09 (drill 5min), AC-24 (card 7d) |
| 性能 p95 | AC-04 (drill ≤3s), AC-17 (card ≤5s) |
| 边界值 | AC-12 (effective_max 4 cases), AC-13 (9-11/13-15), AC-14 (硬下限 7 保护) |
| scale | AC-05 (100/500 错题), AC-11 (backfill 100%) |
| 兼容性 | AC-15 (旧 sink_error 路径不破) |
| 隐私 | AC-19 (analytics 无对话内容) |
| 状态机迁移 | AC-26 (UPSERT), AC-27 (regression reverse) |
| OCR 防截断 | AC-21 (字号 ≥24px) |

### 未覆盖的边界（已知风险）

- ❌ 浏览器刷新场景（Edge-8）：状态丢失；属于前端 UX 范围，建议 Playwright E2E 覆盖但本次未单列 AC（与 AC-03 state reset 重叠）
- ❌ 字体子集化完整字符覆盖（FR-060）：需要从 sample cards OCR 反推字符集；建议 reviewer 在 Phase 6 单独跑 `python -m scripts.test_card_font_subset.py`
- ❌ RLS policy 强制（FR-119）：属于 Phase 9 polish 范围，本次 AC 矩阵按用户指示排除
- ❌ 多端一致性（WS 事件 + HTTP API）：US4 WS 事件 `interview.card_ready` 已隐含在 AC-17 验证，未单列
- ❌ 性能 regression：embedding 离线计算 ≤500ms / rerank top-50 ≤2.5s（plan.md Performance Goals）；建议 Phase 9 perf test 覆盖，本次未单列

### 与 spec 的对齐

- ✅ FR 覆盖：FR-001~005（US1）, FR-010~015（US2）, FR-020~023（US3）, FR-030~033（US5）, FR-040~042（US6）, FR-050~056 + FR-060~063（US4）全部映射到至少 1 条 AC
- ✅ SC 覆盖：SC-001（AC-01）, SC-002（AC-02）, SC-010/011/012/013（AC-04/05/09）, SC-020/021/022（AC-13/14）, SC-030/031/032/033/034（AC-17/19/20/21/22）, SC-040/041（AC-26/27）全部命中
- ✅ Edge Case 覆盖：Edge-1（AC-02）, Edge-2（AC-06）, Edge-3（AC-07）, Edge-4（AC-08）, Edge-5（AC-10）, Edge-6（AC-22）, Edge-7（AC-22）
- ✅ tasks.md 任务 ID 对齐：T033→AC-02 contract test, T044-T050→AC-04~09 unit/integration, T063-T066→AC-12~16, T074-T080→AC-17/22/24, T095-T098→AC-25, T104-T107→AC-26/27

---

## 自检清单（dev.md Step 3）

- [x] 每条 AC 都有"验证方式"列（不可空）
- [x] 每条 AC 都有"来源"列（不可空）
- [x] AC 总数 = 27 ≥ 18 条
- [x] 每条 AC 至少覆盖 1 个边界（empty/null/timeout/降级/缓存/性能/边界值/scale/兼容/隐私/状态机/OCR）
- [x] 无模糊词（已 grep "快/稳定/高效/合理/差不多"，0 命中）
- [x] AC 未超出 spec.SC 范围（SC Gaps 段为"无"）
- [x] 不修改 spec.md / tasks.md / plan.md（仅产出 ac-matrix.md）
- [x] 不写任何代码（仅 AC 起草）
- [x] 不启动后端 / 不跑测试

---

## Tester 反驳日志

### R1 [AC-06 vs AC-07] embedding/reranker 端口无法独立隔离 — 验证方式不可复现
- **反例场景**: AC-06 写「停掉 8765 端口」、AC-07 写「reranker port 8765/rerank 返回 500」。但 plan.md R-2 + contracts/http-api.md C-5 + `.env.example` 把 embedding 与 reranker 合并到**同一 service**（`embedding_service_url=127.0.0.1:8765`、`reranker_service_url=127.0.0.1:8765`）。`kill -9 (8765)` 会让两个端点同时挂，无法仅隔离 reranker → AC-07 降级路径在生产拓扑下根本进不去。
- **验证命令**: `cd backend && uv run python -c "import os; print(os.getenv('EMBEDDING_SERVICE_URL'), os.getenv('RERANKER_SERVICE_URL'))"` 期望两条输出相同。Playwright 试图只 mock `/rerank` 端点也会因同一进程内 `/embed` 也 down 而被卡死。
- **建议**: 把 AC-06 改写为「mock `/embed` 返回 503」(用 HTTPX MockTransport 或 `httpx.MockRouter` 拦截)，AC-07 改写为「mock `/rerank` 返回 500」，删除两条 AC 中所有「停掉 8765 端口」字样；或在 plan.md 增加 R-12 决策把两个 service 拆成独立端口（8765+8767），并对应改 `core/config.py` + `.env.example`。

### R2 [AC-09] cache key 与 spec FR-015 不一致 — hash 范围过窄
- **反例场景**: AC-09 写「同一 (user_id, job_id) 在 5 分钟内复用同一组 5 道题」。spec FR-015 写「cache key = hash(JD + error_pool_hash)」。如果用户在同一 job_id 改了岗位/公司名（JD 改了）或新错题入库（error_pool 变了），AC-09 会继续返回旧题 — 与 spec 行为不一致，SC-013 cache 命中率会被错算（错误地高估）。
- **验证命令**: `cd backend && uv run pytest -q tests/unit/test_drill_cache.py::test_cache_key_includes_jd_and_pool_hash -v`（需新增）；现有 `tests/unit/test_drill_cache.py` 仅有 TTL 测试。
- **建议**: 新增 AC-09b 验证「JD 文本改变时 cache miss」（`curl POST /api/v1/interviews/quick-drill/preview {job_id=X, position='P1'} → 5 题A；同 job_id 但 position='P2' → 不同 5 题`）；把 AC-09 改写为「hash(JD+error_pool_hash) 一致时复用，任意字段变化触发 miss」。

### R3 [AC-12] planner_recommended 的动态计算未验证 — 公式边界看似完整但只测了常数
- **反例场景**: AC-12 的 4 个 boundary case 全部用常数（planner=10/15/5/20），但 FR-023 写「planner_recommended 由 focus_areas 数量 × 每维度 3-5 题动态算出」。若 Planner 实际算出 planner=8（focus_areas=2 × 4 题），user_choice=10 → `min(10,8)=8` → `max(7,8)=8`，但测试用例未覆盖这种「planner_recommended 落在 7-15 中间」的 case。T063 单元测试只验常数边界，与 FR-023 动态语义脱节。
- **验证命令**: `cd backend && uv run pytest -q tests/unit/test_effective_max.py::test_planner_recommended_dynamic_7_to_15 -v`（需新增，断言 8 个 case：user/planner 组合 (10,8)/(15,9)/(10,12)/(15,14) 等）。
- **建议**: AC-12 补充 4 个 dynamic case（user=10,planner=8→8；user=15,planner=9→9；user=10,planner=12→10；user=15,planner=14→14），共 8 个 assertion；或将 AC-12 拆为 AC-12a（常数边界）+ AC-12b（动态计算）。

### R4 [AC-13] 「90% 落入 ±1」统计断言缺置信度 — L007 教训复现
- **反例场景**: AC-13 写「`distribution_test_full_interview --rounds 100` 输出两个档位的 ±1 命中率 ≥90%」。100 轮样本量下 90% 命中率的标准误 `sqrt(0.9*0.1/100) ≈ 3%`，置信区间约 84%-96%；下限卡 90% 等于不接受 95% CI 下沿 < 87% 的实现，统计上过于严苛（更可能因随机噪声 false-fail）。Spec SC-020/021 也只说「90%」无 CI。
- **验证命令**: `cd backend && uv run python -m scripts.distribution_test_full_interview --rounds 200 --confidence 0.95` 期望 95% Wilson 下限 ≥ 85%（而非固定点估计 90%）。
- **建议**: AC-13 改为「Wilson score 95% CI 下限 ≥ 0.85」(L007 历史教训 — spec 锁定时已记录)；同步改 SC-020/021 文字或 AC 验证命令。

### R5 [AC-17] 9:16 竖版 300KB 上限未独立验证 — 4:3 与 9:16 文件大小差异显著
- **反例场景**: AC-17 写「`test_card_file_size` 输出 ≤300KB 两个 variant」。但 9:16 (1080×1920) 像素数 ≈ 4:3 (1080×810) 的 2.37 倍，JPG q=85 同字号下文件大小也近线性增长 — 当大纲条数 ≥7 条 + 9:16 必须分多段（FR-052 提到分段标题）时，实际文件常超 300KB。spec SC-031 合并两条 variant 是设计意图，但实施时容易让 dev 只对 4:3 通过、9:16 漏验。
- **验证命令**: `cd backend && uv run python -m scripts.test_card_file_size --size 9_16 --max-outlines 8` 期望 `<=300*1024 bytes`；当前 AC-17 命令未指定 `--size` 参数。
- **建议**: AC-17 拆为 AC-17a（4:3 ≤300KB）+ AC-17b（9:16 ≤300KB + 7-8 条大纲 + 2 段标题），明确两条独立 assertion；或将 `test_card_file_size` 验证脚本硬编码 9:16 + 8 大纲 fixture。

### R6 [AC-19] payload 黑名单验证方式不充分 — 仅 SELECT 两个字段
- **反例场景**: AC-19 验证命令是 `psql ... SELECT event_type, payload->>'size_variant', payload->>'duration_ms'`，但完全没有检查「payload 是否含 question_text/score/answer 字段」。若 dev 误把所有 InterviewPlan 字段 dump 进 payload（FR-055 隐私违规），AC-19 测试仍 PASS — 因为 SELECT 永远不会返回 NULL，只是没去查。
- **验证命令**: `cd backend && uv run python -m scripts.assert_analytics_pii_free --event-type doubao_card_rendered --forbidden-keys question_text,score,answer,expected_points,interview_plan`（需新增）；现有 SQL 不验证。
- **建议**: 改 AC-19 验证命令为「`SELECT payload FROM analytics_events WHERE event_type='doubao_card_rendered'` 期望 `payload ? 'question_text' = false AND payload ? 'score' = false AND payload ? 'answer' = false`」；或新增 AC-19b 专门 PII 审计。

### R7 [AC-23] interview_sessions 行创建行为与契约矛盾 — session_id 来源不明
- **反例场景**: AC-23 写「`interview_sessions` 表**不创建新行**（仅埋点）」。但 contracts/http-api.md C-1 `POST /api/v1/interviews` 响应包含 `session_id: uuid` + `mode: 'doubao'`，前端需要这个 session_id 调 `/card` 端点；若不写表，前端报错「session not found」。spec.md FR-050 也只说「不进入 question_gen/score_llm/report」，并未禁止 sessions 表插入。
- **验证命令**: `cd backend && uv run pytest -q tests/integration/test_us4_doubao_mode.py::test_doubao_session_persisted_with_mode_guard -v`（应保留 1 行 session + mode='doubao' + thread_id 非空）。
- **建议**: 改 AC-23 描述为「`interview_sessions` 写入 1 行（mode='doubao' + thread_id + user_id）但**不进入 question_gen/score_llm/report 节点**」；同步改 contracts/http-api.md C-1 注释说明 doubao 模式仍创建 session。

### R8 [AC-28] deferred 范围过宽 — T110/T111 是 US6 核心 AC 而非 polish
- **反例场景**: AC-28 把「T110（drill_resink_completed analytics 埋点）+ T111（source_session_id 不回写验证）」列为 deferred。但 spec FR-042 明确要求「保留原 source_session_id 不回写」是 US6 验收硬指标，AC-26 只测了「source_session_id 未变」的间接断言，没有验证 sink_error 节点的写入路径确实没动 source_session_id 字段（T111 才是直接断言）。
- **验证命令**: `cd backend && uv run pytest -q tests/integration/test_us6_drill_resink.py::test_source_session_id_immutable_in_db -v`（需新增）；AC-26 现有断言只在 service 层 mock。
- **建议**: 把 T111（sink_error 不回写 source_session_id）从 AC-28 移出，单独新增 AC-29「`UPDATE error_questions SET source_session_id = $S2 WHERE source_question_id = $A` 必须 0 rows affected」（直接 SQL 断言，非 service mock）。

### R9 [AC-02] hover tooltip 文本不可观测 — Playwright 断言缺
- **反例场景**: AC-02 验证命令是「Playwright `.locator('[data-testid=quick-drill]').isDisabled()`」，但只验了 disabled 状态，**没有验证 hover tooltip 的具体文案**「先做完一次面试，错题集有题才能补漏」。若 dev 把 tooltip 写成英文或拼错，AC-02 仍 PASS（disabled 是真的），但 spec US-1.AS2 验收失败。
- **验证命令**: `npm run e2e -- tests/e2e/mode-selection.spec.ts -g "quick_drill hover tooltip shows exact zh-CN text"` 期望 `await page.locator('[data-testid=quick-drill]').hover() + expect(page.locator('[role=tooltip]')).toHaveText('先做完一次面试，错题集有题才能补漏')`。
- **建议**: 改 AC-02 Playwright 断言为「`isDisabled() AND locator('[role=tooltip]').toHaveText('先做完一次面试，错题集有题才能补漏')`」；或新增 AC-02b tooltip 文本断言。

### R10 [AC-04] 「≥3/5 dimension 命中」的可观测性缺失 — 无 dimension → JD 关键词映射
- **反例场景**: AC-04 写「至少 3 题 dimension 与 JD 关键词命中」，但没指定「dimension 与 JD 关键词」的对应关系定义在哪（spec SC-011 也没指）。drill-eval-set.md 是人工标注 20 组 ground truth（计划产物，AC-05 引用），但 AC-04 用的是 general JD「分布式事务/微服务/RAG」，与 eval-set 不挂钩。dev 可能用任何 dimension 字符串（如「tech_depth」）就报「命中」，因为没有 explicit 关键词→dimension map。
- **验证命令**: `cd backend && uv run python -m scripts.eval_drill_accuracy --eval-set docs/evidence/048/drill-eval-set.md --scenario general-jd-tech` 期望输出「≥3/5 dimension ∈ {tech_depth, architecture, engineering_practice}」。
- **建议**: 新增 AC-04b「JD 关键词『分布式事务』必须命中 dimension ∈ {distributed_systems, architecture} ≥1 题」(map 显式存 `specs/048/keyword-dimension-map.md`)；或 AC-04 引用 drill-eval-set.md 第 1-5 组用例作为 baseline。

### R11 [AC-11] backfill 100% 验证命令缺 race 保护 — arq worker 未启动场景
- **反例场景**: AC-11 写「`scripts.backfill_embeddings && psql -c SELECT COUNT(*) FILTER (WHERE embedding IS NULL)` 期望 `0/N`」。但 spec FR-011 写「错题写入时异步触发 embedding 计算」，arq worker 必须独立进程跑（plan.md T-NEW-1）。如果 dev 跑 backfill 脚本时忘记起 arq worker，backfill 本身也是脚本调 embedding service HTTP，不依赖 arq；AC-11 通过 ≠ arq pipeline 正常。
- **验证命令**: `cd backend && uv run pytest -q tests/integration/test_embedding_pipeline.py::test_arq_enqueue_on_new_error_question -v`（T048/T-NEW-1 路径覆盖，需新增）；现有 AC-11 不验新错题自动入队。
- **建议**: 新增 AC-11b「`INSERT INTO error_questions ... RETURNING id` 之后 30 秒内 `SELECT embedding FROM error_questions WHERE id=$1` 应非 NULL（依赖 arq worker 正常运行；smoke 测试需先 `arq app.workers.main.WorkerSettings`）」。

### R12 [AC-15] 兼容性未覆盖迁移默认值 — legacy session.mode='full'+max_questions=5 怎么处理
- **反例场景**: AC-15 写「完整面试 score < 6 走原 sink_error 路径（与现状一致）」。但 data-model.md 第 26 行写「Backfill: 现有 session 全部 mode='full' + max_questions=5 (DEFAULT)」+ migration 0028 把 `max_questions` 字段 nullable，且 `effective_max = max(7, min(user, planner))`。legacy session 的 `max_questions=5` 在迁移后实际会被 `effective_max = max(7, min(5, planner)) = 7` 改写，但 AC-15 没测「打开 1 周前旧 session 链接，前端展示题数从 5 变 7 是否平滑」。
- **验证命令**: `cd backend && uv run pytest -q tests/integration/test_us3_full_interview.py::test_legacy_session_effective_max_override -v`（需新增）；构造 1 条 legacy session `mode='full', max_questions=5`，调 `compute_effective_max(session_id)` 期望返回 7。
- **建议**: AC-15 补充「legacy session (max_questions=5) 经过 effective_max 计算后实际展示为 7 题 + 历史报告数据不被破坏」断言。

### R13 [AC-21] 字号 ≥24px 自动校验依赖外部 PNG 推断 — 不可在 CI 复现
- **反例场景**: AC-21 验证命令是 `python -m scripts.test_card_font_size --card docs/evidence/048/sample-cards/card-4x3-sample.jpg`。但 `docs/evidence/048/sample-cards/` 在 T093 才生成（plan.md Phase 6），且 OCR 字号推断准确率依赖 OpenCV + Tesseract；CI 环境无 Tesseract 时此 AC 跑不起来，AC 验证失败 = dev 误判。spec SC-032 是「自动化脚本校验」，但脚本可靠性没保障。
- **验证命令**: `which tesseract && tesseract --version 2>&1 | head -1` 在 backend Docker/CI 环境无此 binary；`pip install pytesseract` 不带 binary。
- **建议**: 改 AC-21 为「模板编译时静态分析：解析 satori JSX 模板中所有 `fontSize` 属性，断言最小值 ≥24 + 标题 ≥64」(纯静态 AST 检查，不依赖 PNG OCR)；或把 Tesseract 安装写入 CI Dockerfile。

### R14 [AC-12/13 缺少并发] effective_max 计算并发场景未测 — T064 race
- **反例场景**: AC-12 + AC-14 在单元测试层覆盖 `effective_max` 公式 + 自适应收尾边界，但没测「同时 2 个并发面试 session 共享同一 user 时，adaptive_termination_window 的 3 题滚动 counter 是否被串扰」。LangGraph state 是 per-session，但 sink_error 写 last_practiced_at 时若用 `UPDATE ... WHERE last_practiced_at < $now` 无并发锁，并发写可能丢更新。
- **验证命令**: `cd backend && uv run pytest -q tests/integration/test_us3_full_interview.py::test_concurrent_termination_window_isolation -v`（需新增，用 asyncio.gather 跑 2 个 session）。
- **建议**: 新增 AC-16b「并发 2 个 full interview 同一 user：两 session 的 `current_question` 计数器互不干扰（LangGraph checkpointer 按 thread_id 隔离 OK）+ sink_error 并发 UPSERT 不会丢更新」。

### R15 [AC-03] 浏览器刷新场景（Edge-8）未覆盖 — 与起草说明已知风险一致
- **反例场景**: AC-03 测「Zustand store reset」是程序内 reset，但 spec Edge-8 写「浏览器刷新页面 → 所有模式选择状态丢失」。前者测的是用户在 wizard 内点 back，后者是 F5 强制刷新 → AC-03 没覆盖真实 Edge-8。Zustand 不带 persist 中间件时 F5 状态确实丢（这是当前预期行为），但 AC-03 应该显式断言这一点 + 给出降级 UI（重新从「新建面试」入口开始）。
- **验证命令**: `npm run e2e -- tests/e2e/mode-selection.spec.ts -g "F5 refresh clears mode state and redirects to interview create"` 期望 `page.reload() → expect(page).toHaveURL(/\/interviews\/new$/)`。
- **建议**: 新增 AC-03b「demo 账号在模式选择页按 F5 → 状态清空 + 跳转回 /interviews/new」；或 AC-03 补 Playwright `page.reload()` 断言。

---

## Moderation Log (Round 1, 2026-07-07)

主 Agent 裁判结果：15 条反例全部接受（其中 R10 含一次主动探索）。`status: draft → in_review`，`negotiation_rounds: 0 → 1`。

- **R1 [接受]**: AC-06/07 端口隔离不可复现。plan.md R-2 + contracts/http-api.md C-5 + .env.example 把 embedding 与 reranker 合并到 8765 同进程；`kill -9 (8765)` 会让两个端点同时挂，无法仅隔离 reranker。dev 修订：AC-06/07 改写为 HTTPX MockTransport 拦截 `/embed` + `/rerank` 端点，删除"停掉 8765 端口"字样。
- **R2 [接受]**: AC-09 cache key hash 范围与 FR-015 不一致。spec FR-015 明确 `cache key = hash(JD + error_pool_hash)`，AC-09 必须包含 JD 变化与 error_pool 变化两条 miss 断言。dev 修订：新增 AC-09b「JD 文本或 error_pool 变化触发 cache miss」。
- **R3 [接受]**: AC-12 planner_recommended 动态计算未验证。FR-023 写「planner_recommended 由 focus_areas 数量 × 每维度 3-5 题动态算出」，但 AC-12 仅测常数。dev 修订：补充 4 个 dynamic case（user/planner 组合 (10,8)/(15,9)/(10,12)/(15,14)），共 8 个 assertion；或将 AC-12 拆为 AC-12a + AC-12b。
- **R4 [接受]**: AC-13 ±1 命中率缺置信度。100 轮 90% 命中率标准误 ≈3%，95% CI 下沿可低至 84%。dev 修订：AC-13 改为「Wilson score 95% CI 下限 ≥ 0.85」(L007 历史教训 — spec 锁定时已记录)。
- **R5 [接受]**: AC-17 9:16 竖版 300KB 上限未独立验证。9:16 像素数 ≈ 4:3 的 2.37 倍，文件大小近线性增长；spec SC-031 合并两条 variant 但实施易漏。dev 修订：AC-17 拆为 AC-17a（4:3 ≤300KB）+ AC-17b（9:16 ≤300KB + 7-8 条大纲 + 2 段标题）。
- **R6 [接受]**: AC-19 payload 黑名单验证方式不充分。仅 SELECT 两个字段不检查 question_text/score/answer 是否在 payload 中；FR-055 隐私违规可绕过。dev 修订：AC-19 验证命令改为直接 SQL 断言 `payload ? 'question_text' = false AND payload ? 'score' = false AND payload ? 'answer' = false`；或新增 AC-19b 专门 PII 审计。
- **R7 [接受]**: AC-23 interview_sessions 行创建行为与契约矛盾。contracts/http-api.md C-1 响应包含 `session_id: uuid` + `mode: 'doubao'`，前端需要 session_id 调 /card 端点；不写表前端报错。dev 修订：改 AC-23 描述为「写入 1 行（mode='doubao' + thread_id + user_id）但不进入 question_gen/score_llm/report 节点」；同步改 contracts/http-api.md C-1 注释说明 doubao 模式仍创建 session。
- **R8 [接受]**: AC-28 deferred 范围过宽（T111 是硬约束）。spec FR-042 明确要求 source_session_id 不回写，AC-26 只测间接断言未测 sink_error 直接 SQL。dev 修订：T111 移出 deferred，新增强制 AC-29「`UPDATE error_questions SET source_session_id = $S2 WHERE source_question_id = $A` 必须 0 rows affected」。
- **R9 [接受]**: AC-02 hover tooltip 文本不可观测。仅验 disabled 状态未验 tooltip 文案；spec US-1.AS2 明确要求"先做完一次面试，错题集有题才能补漏"。dev 修订：AC-02 Playwright 断言改为 `isDisabled() AND locator('[role=tooltip]').toHaveText('先做完一次面试，错题集有题才能补漏')`；或新增 AC-02b tooltip 文本断言。
- **R10 [主动探索 → 接受]**: AC-04 dimension→JD 关键词映射无。主 Agent 主动 Read `specs/048/.../` 与 `docs/evidence/048/.../`，确认 drill-eval-set.md 尚未创建（应在 T094 生成），故 AC-04 无法直接引用；反例方向正确。dev 修订：新增 AC-04b「JD 关键词『分布式事务』必须命中 dimension ∈ {distributed_systems, architecture} ≥1 题」(map 显式存 `specs/048-interview-modes-and-doubao-card/keyword-dimension-map.md`，T094 一并创建)；或 AC-04 引用 drill-eval-set.md 第 1-5 组用例作为 baseline。
- **R11 [接受]**: AC-11 backfill 100% 验证缺 race 保护。arq worker 必须独立进程跑（plan.md T-NEW-1），AC-11 仅测 backfill 脚本不测 arq pipeline。dev 修订：新增 AC-11b「`INSERT INTO error_questions ... RETURNING id` 之后 30 秒内 `SELECT embedding FROM error_questions WHERE id=$1` 应非 NULL（依赖 arq worker 正常运行；smoke 测试需先 `arq app.workers.main.WorkerSettings`)」。
- **R12 [接受]**: AC-15 兼容性未覆盖迁移默认值。migration 0028 默认值需验证，legacy session (max_questions=5) 经 effective_max 应返回 7。dev 修订：AC-15 补充「legacy session (max_questions=5) 经过 effective_max 计算后实际展示为 7 题 + 历史报告数据不被破坏」断言。
- **R13 [接受]**: AC-21 字号 ≥24px 自动校验依赖外部 Tesseract。CI 环境无 tesseract binary，`pip install pytesseract` 不带 binary。dev 修订：改 AC-21 为「模板编译时静态分析：解析 satori JSX 模板中所有 `fontSize` 属性，断言最小值 ≥24 + 标题 ≥64」(纯静态 AST 检查，不依赖 PNG OCR)；或把 Tesseract 安装写入 CI Dockerfile（仅当优先选择 PNG 推断时）。
- **R14 [接受]**: AC-12/13 缺并发 isolation 测试。LangGraph checkpointer 按 thread_id 隔离 OK，但 sink_error 并发 UPSERT 可能丢更新。dev 修订：新增 AC-16b「并发 2 个 full interview 同一 user：两 session 的 `current_question` 计数器互不干扰 + sink_error 并发 UPSERT 不会丢更新」(asyncio.gather + `last_practiced_at` 行级锁或 WHERE 条件保护)。
- **R15 [接受]**: AC-03 浏览器刷新场景（Edge-8）未覆盖。spec Edge-8 明确写 F5 行为，AC-03 仅测 Zustand store reset。dev 修订：新增 AC-03b「demo 账号在模式选择页按 F5 → 状态清空 + 跳转回 /interviews/new」；或 AC-03 补 Playwright `page.reload()` 断言。

**汇总**：15 条接受 → 派 dev 修订。修订完成后进入 Round 2 (tester 再审)。若 Round 2 后仍有 ≥1 条接受的反例，则继续 Round 3；3 轮未锁定则 main-agent 强制取 tester 更严版本。

---

## Tester 反驳日志 (Round 2, 2026-07-07)

> **Round 2 范围**：15 条 Round 1 修订全部落实（37 条 AC + AC-28 deferred）。本轮聚焦 6 类问题：
> 覆盖度 / 边界 / 可观测性 / 歧义 / 并发 / PII 安全。
> 推荐 6 条精炼反例（控 token L007 教训）+ 1 条「dev 自查遗漏」。

### R16 [AC-12a + AC-15] R3+R12 修订引入新漏洞 — migration 0028 CHECK 约束与 legacy 数据直接冲突
- **反例场景**: data-model.md 第 21 行写 `ALTER TABLE interview_sessions ADD COLUMN max_questions smallint CHECK (max_questions BETWEEN 7 AND 15)`，但第 26 行声明 `Backfill: 现有 session 全部 mode='full' + max_questions=5 (DEFAULT)`。PostgreSQL CHECK 约束 ALTER TABLE ADD CONSTRAINT 默认可对历史行验证（`NOT VALID` 才是反例，但 dev 实施很容易默认 VALID）。生产 0028 跑完 alembic upgrade head 后立即触发 `psycopg2.errors.CheckViolation`：现存 interview_sessions 表里所有 legacy 行的 `max_questions=5`（DEFAULT）落在 [7,15] 区间外 → migration 失败回滚 → AC-15「legacy session 迁移后 effective_max=7」永远无法验证。AC-12a (10/15/5/20) 中 case `user=10, planner=5 → 7` 也属此类（planner_recommended=5 < hard_min=7），但其验证方式 `test_boundary_constants` 在单元测试跑不出 production 失败点。
- **验证命令**: `cd backend && uv run alembic upgrade head 2>&1 | grep -E "CheckViolation|constraint" | head -5` 期望生产环境在 alembic upgrade 0028 步骤报错；直接 SQL：`SELECT COUNT(*) FROM interview_sessions WHERE max_questions NOT BETWEEN 7 AND 15` 期望 migration 完成后 = 0，但实际 > 0（取决于是否使用 `NOT VALID`）。
- **建议**: AC-12a 增 1 条「`ALTER TABLE interview_sessions ADD COLUMN max_questions CHECK ... NOT VALID` 必须存在；事后 `psql -c "ALTER TABLE interview_sessions VALIDATE CONSTRAINT ..."` 必须通过」（直接 SQL 断言 0028 migration 行为）；AC-15 增「alembic upgrade head 在 0028 步骤不能报 CheckViolation」（CI 级别的 migration smoke test）。

### R17 [AC-04b + AC-05] R10 修订引用未存在文档 — 关键词 map 是 T094 计划产物并未创建
- **反例场景**: AC-04b 验证命令引 `python -m scripts.eval_drill_accuracy --eval-set docs/evidence/048-interview-modes-and-doubao-card/drill-eval-set.md --scenario general-jd-tech`，并要求「关键词→dimension map 显式存 `specs/048-interview-modes-and-doubao-card/keyword-dimension-map.md`，T094 一并创建」。但当前 `ls specs/048-interview-modes-and-doubao-card/` 目录确认**实际未创建**此 map（仅 ac-matrix.md + spec.md + tasks.md + plan.md + checklist + contracts + data-model.md + quickstart.md + research.md）；T094 在 tasks.md 列于 Phase 6 US4（如 "Generate hand-labeled drill eval set"），属 US4 范围却绑定 US2 验收。AC-05 同样引用 drill-eval-set.md（dev grep `docs/evidence/048/drill-eval-set.md` 会落空）。
- **验证命令**: `ls D:/Project/eGGG/specs/048-interview-modes-and-doubao-card/keyword-dimension-map.md 2>&1` 期望 `No such file`（确认不存在）；`ls D:/Project/eGGG/docs/evidence/048-interview-modes-and-doubao-card/ 2>&1` 期望空目录（确认未建）。
- **建议**: AC-04b 增「T094 必须先于 T044-T062 (US2 测试) 完成；如 T094 schedule 在 Phase 6 > Phase 4，AC-04b 须以临时 inline keymap 兜底（fixture 内置 10 个关键词→dimension 映射）+ 后续契约锁定」（防止 AC 引用空气）；把 AC-04b + AC-05 的 `--eval-set` 路径统一为「T094 输出后才知道」型软引用：CI 启动阶段 `pytest -k drill_e2e` 自动 skip 但 leave 5-case inline 兜底集。

### R18 [AC-09b] R2 修订引入歧义 — hash(JD + error_pool_hash) 的 hash 算法未指定
- **反例场景**: AC-09b 验「JD 文本变化或 error_pool 变化必须触发 cache miss」，但 spec FR-015 写「`cache key = hash(JD + error_pool_hash)`」未指定 hash 函数。dev 可能用 SHA256（64 字符 hex 字符串作 Redis key，对人难读，对 Redis 内存浪费），也可能用 murmurhash3 或 blake2b。如果 AC-09b 验证方式只断言「cache hit/miss」行为而不锁定 hash 算法一致性，T094 之后跨服务（embedding_service / backend）跨语言（Python vs Node.js 调试脚本）复现同一 cache_key 时无法保证。spec FR-015 + data-model.md L97「`drill_cache:{user_id}:{job_id_hash}`」含义不清：是 hash(user_id+job_id) 还是 hash(user_id+hash(JD)) 还是 hash(JD + error_pool_hash)？
- **验证命令**: `cd backend && uv run python -c "import hashlib; print(hashlib.sha256(b'分布式事务' + b'err_pool_xyz').hexdigest())"` vs `redis-cli GET "drill_cache:{user_id}:{job_id_hash}"` 期望 key 字符串格式统一（如 `user_id:sha256(jd_text+err_pool_hash)[:16]` 16 字符前缀）；当前 data-model.md L97 仅说 `job_id_hash` 而非 `cache_key` 计算公式。
- **建议**: 新增 AC-09c（不改 AC-09b；保持 R2 修订主体）「cache key 计算公式必须锁定为 `sha256(jd_text.encode('utf-8') + error_pool_hash.encode('utf-8'))[:32]`，并附加 user_id 前缀 `drill_cache:{user_id}:{key_hex}`」（data-model.md L97 必须同步增这条公式）；AC-09b 验证方式补「同一 JD+error_pool 输入两次，Redis key 完全相等的 assertion」（hash 算法一致性）。

### R19 [AC-16b] R14 修订并发断言不完整 — adaptive_termination counter 串扰未覆盖
- **反例场景**: AC-16b 仅验「asyncio.gather 跑 2 个 session + current_question 互不干扰 + sink_error 并发 UPSERT 不会丢更新」，但 spec FR-021/022 写「自适应收尾：连续 3 题 score ≥ 8.0 时 + current ≥ effective_max - 3」。score 滚动 counter 是 LangGraph state 内字段（per-thread_id 隔离），确实安全 — AC-16b 这点 PASS。**但 spec FR-040 + R14 反例原文**指出 sink_error UPSERT 写 `last_practiced_at`，AC-29 是 SQL UPDATE 0-rows affected 仅覆盖 source_session_id 字段。AC-16b 没覆盖「sink_error 并发刷新 last_practiced_at 时会否丢失晚到者的 now()」，也未明示「行级锁 (SELECT ... FOR UPDATE) 或 WHERE 条件 (last_practiced_at < new_timestamp) 保护」。如果 dev 用裸 `UPDATE error_questions SET last_practiced_at = now() WHERE source_question_id = $A` 无并发锁，两个 session 同时写同一 source_question_id 较早者覆盖晚者 → `last_practiced_at` 不准确。
- **验证命令**: `cd backend && uv run pytest -q tests/integration/test_us6_drill_resink.py::test_concurrent_last_practiced_at_serializable -v`（需新增）；逻辑：用 asyncio.gather 跑 3 个 sink_error 同一 source_question_id，期望 final `last_practiced_at` 等于 max(三个 now())，且 PG WAL 显示 3 次 UPDATE 都 commit。
- **建议**: AC-16b 增 1 行「sink_error 用 `UPDATE ... WHERE source_question_id = $A AND last_practiced_at <= $new_now RETURNING ...` 保证读后写原子」（或 `SELECT ... FOR UPDATE NOWAIT`）；新增独立 assertion `last_practiced_at` 必须等于 3 个 timestamp 中最大者。

### R20 [AC-11b] R11 修订 30 秒窗口在 CI 不可靠 — arq worker 启动开销 + queue 排队
- **反例场景**: AC-11b 写「`INSERT INTO error_questions ... RETURNING id` 之后 30 秒内 `SELECT embedding FROM error_questions WHERE id=$1` 应非 NULL」。CI 环境 arq worker 启动开销包括：python 解释器初始化 + 加载 bge-small-zh-v1.5 (93MB 模型 + 加载时间 ~10s) + arq 注册到 Redis (~1s) + 从主队列拉任务 (~0.1s)。当测试用 `INSERT ... RETURNING id` 触发 embedding_task 后，30 秒窗口在 cold start 第一次跑可能不够，CI flaky 风险高。FR-011 写「错题写入时异步触发 embedding 计算（避免写入阻塞 + 重试 3 次）」，30s 是 FR-011 隐含的 SLO，但既不是 spec.SC 也不是 AC-11 文本显式声明。
- **验证命令**: `cd backend && arq app.workers.main.WorkerSettings & sleep 30 && PGPASSWORD=$DB_PASS psql -c "SELECT count(*) FROM error_questions WHERE embedding IS NULL AND created_at > now() - interval '5 min';"` 期望 0 rows；冷启动重跑 3 次期望至少 2/3 pass。
- **建议**: AC-11b 验证命令改为「CI smoke 跑前先预热 arq worker：`arq app.workers.main.WorkerSettings` 启动后跑一次 `INSERT INTO error_questions (dummy) RETURNING id` 触发 warm-up 30 秒，再开始正式 assertion」；或把 30 秒窗口改为 60 秒（cold start 安全）；或新增 AC-11c「cold start：`first INSERT 后 60s 内必须 compute_embedding`，后续 INSERT 30s 内」（区分 cold/warm 路径）。

### R21 [AC-21] R13 修订 AST 静态分析覆盖不全 — CSS className 间接设 fontSize 漏检
- **反例场景**: AC-21 改为「解析 satori JSX 模板中所有 `fontSize` 属性」，但 satori JSX 模板允许通过多种方式设字号：(a) inline `style={{ fontSize: 24 }}`；(b) `className="text-h1"`（CSS 类引外部 stylesheet）；(c) `style={{ fontSize: 'var(--title-size)' }}`（CSS 变量）；(d) `<h1>` satori 标签默认字号（`<h1>` = 32px, `<h2>` = 24px）。R13 修订提到 `fontSize` 属性 AST 检查只覆盖 (a)，(b)(c)(d) 全部漏过。如果 dev 在 templates/card_4x3.tsx 用 `<h1>` 标签作为「关键标题」，AC-21 静态分析看不到 fontSize 属性，但实际渲染出 32px < spec FR-060 要求 64px → SC-032 验收失败。
- **验证命令**: `grep -n "fontSize" backend/app/services/card_renderer/templates/card_4x3.tsx backend/app/services/card_renderer/templates/card_9x16.tsx` 期望命中 ≥1 行；但 `cat backend/app/services/card_renderer/templates/card_4x3.tsx | grep -E "<h[1-6]"` 同样应发现标题用 `<h1>`；当前 AST 检查仅正对 fontSize 属性。
- **建议**: AC-21 增 1 条「`<h1>` / `<h2>` / CSS 变量 / className 引用 4 种间接字号路径也必须经 AST 静态分析覆盖」；具体断言「标题节点字号（`<h1>` 默认 32px → AC-21 FAIL 因 ≥64 必需）必须用 inline `style={{fontSize: X}}` 显式声明 ≥64」；或新增独立 metric `<h1>` 使用次数=0 或全用 inline 标题字号 ≥64。

### R22 [AC-25] FR-031 vs US-5.AS1 语义空隙 — 「原题重考」+「变体切换」是否互斥未测
- **反例场景**: spec FR-031 写「「原题重考」模式：question_gen 节点跳过，直接把错题 question_text 注入 questions，dimension 沿用原错题」；US-5.AS3 写「变体生成失败时降级为原题重考 + analytics 记一次降级事件」。**AC-25 验证 `tests/integration/test_us5_variant_mode.py` 验证 question_text 变化 + dimension 字段恒等**，但没测「「快速补漏」默认进入 = 原题重考」+「用户必须用 toggle 切到「变体重考」」（AC-25 是 toggle=true 的路径）。spec FR-031 「原题重考」是默认，user 不点 toggle 时也走原题，但 AC-25 跳过此场景的测试。如果 dev 把「快速补漏」默认变成「变体重考」（toggle 默认 on，dev 容易做错，因 R7 FR-032 暗示 LLM 调一次 → 默认就开了），spec FR-031 失效。**新漏洞：AC-25 没断言「use_variants 不传 or false → 必须原题重考」这条默认行为路径**。
- **验证命令**: `cd backend && uv run pytest -q tests/integration/test_us5_variant_mode.py::test_default_no_variants_flag_uses_original -v`（需新增）；逻辑：`POST /api/v1/interviews {mode: quick_drill, use_variants: false|undefined}` → 期望 `error_question_ids[*].question_text == error_questions[source_question_id].question_text`（一字不差，非变体）。
- **建议**: AC-25 增 1 条「默认 `use_variants=false`（不传或 false）必须走原题重考（question_text 一字不差）」断言；toggles 默认值需在 contracts/http-api.md C-1 request schema 显式标注 default。

### 反驳小结（Round 2）

dev Round 1 修订**全部落实**（37 条 AC + AC-28 deferred + contracts/http-api.md C-1 注释同步）：AC-02b/03b/04b/09b/11b/16b/19b 7 条新增齐全；AC-12a/12b/17a/17b 拆分合理；AC-02/06/07/09/13/15/19/21/23 9 条改写达标。

**Round 2 新引入 / 残留漏洞 7 条**：
1. **R16** AC-12a+AC-15：migration 0028 CHECK 约束与 legacy `max_questions=5` 直接冲突（**最高优** — 实施时 alembic upgrade 直接挂）
2. **R17** AC-04b+AC-05：T094 产物未创建，AC 引用空气
3. **R18** AC-09b：hash 算法未锁定 + data-model.md 公式不一致
4. **R19** AC-16b：并发 UPSERT `last_practiced_at` 晚到者覆盖风险未覆盖
5. **R20** AC-11b：30 秒窗口在 CI cold start 不稳定
6. **R21** AC-21：AST 静态分析只覆盖 `fontSize` 属性，`<h1>` / CSS 变量漏检
7. **R22** AC-25：FR-031 「默认原题重考」路径未测

**主 Agent 裁判建议**：R16（CHECK 约束直接破坏 migration）必接受；R17（AC 引用空气）必接受；R18-R22 按可行性裁。其中 R16 是阻断级别（embargo dev 实施）；其余属 spec.SC 验收级别。

---

## Moderation Log (Round 2, 2026-07-07)

主 Agent 裁判结果：7 条反例全部接受。`status: in_review` 保持，`negotiation_rounds: 1 → 2`。下一轮为最后一轮（Round 3 强制锁定条款）。

- **R16 [接受]**: AC-12a + AC-15 migration 0028 CHECK 约束与 legacy 数据直接冲突。反例命中"边界条件"类（migration 风险）。CHECK constraint `NOT VALID` 是真实工程实践，但 AC 未约束 NOT VALID 行为 → legacy session `max_questions=5` migration 会被 CheckViolation 阻断。**阻断级别**（embargo dev 实施）。dev 修订：AC-12a 增 1 条「`ALTER TABLE interview_sessions ADD COLUMN max_questions CHECK ... NOT VALID` 必须存在；事后 `ALTER TABLE interview_sessions VALIDATE CONSTRAINT ...` 必须通过」；AC-15 增「alembic upgrade head 在 0028 步骤不能报 CheckViolation」(CI 级别 migration smoke test)。
- **R17 [主动探索 → 接受]**: AC-04b + AC-05 引用未存在文档。主 Agent 主动 Read `specs/048/.../` 与 `docs/evidence/048/.../`，确认 `keyword-dimension-map.md` 与 `drill-eval-set.md` 均不存在（应在 T093/T094 生成）；AC 引用空气是真实风险。dev 修订：AC-04b 增「T094 必须先于 T044-T062 (US2 测试) 完成；如 schedule 不允许，T044-T062 测试套件必须用 inline fixture 兜底（内置 10 个关键词→dimension 映射）+ 后续契约锁定」；CI 启动阶段 `pytest -k drill_e2e` 自动 skip 但 leave 5-case inline 兜底集。
- **R18 [接受]**: AC-09b hash 算法未指定。data-model.md L97 仅说 `job_id_hash` 而非 `cache_key` 计算公式，hash 算法不一致会引发 Redis key 漂移。dev 修订：新增 AC-09c「cache key 计算公式必须锁定为 `sha256(jd_text.encode('utf-8') + error_pool_hash.encode('utf-8'))[:32]`，并附加 user_id 前缀 `drill_cache:{user_id}:{key_hex}`」(data-model.md L97 必须同步增这条公式)；AC-09b 验证方式补「同一 JD+error_pool 输入两次，Redis key 完全相等的 assertion」。
- **R19 [接受]**: AC-16b 并发断言不完整 — adaptive_termination counter 串扰。R14 修订未覆盖 counter 串扰；sink_error UPSERT 原子性是真实风险。dev 修订：AC-16b 增 1 行「sink_error 用 `UPDATE ... WHERE source_question_id = $A AND last_practiced_at <= $new_now RETURNING ...` 保证读后写原子」（或 `SELECT ... FOR UPDATE NOWAIT`）；新增独立 assertion `last_practiced_at` 必须等于 3 个 timestamp 中最大者。
- **R20 [接受]**: AC-11b 30s 窗口 CI 不可靠。cold start + arq worker 启动开销真实存在。dev 修订：AC-11b 验证命令改为「CI smoke 跑前先预热 arq worker：`arq app.workers.main.WorkerSettings` 启动后跑一次 `INSERT INTO error_questions (dummy) RETURNING id` 触发 warm-up 30 秒，再开始正式 assertion」；或把 30 秒窗口改为 60 秒（cold start 安全）；或新增 AC-11c「cold start：`first INSERT 后 60s 内必须 compute_embedding`，后续 INSERT 30s 内」（区分 cold/warm 路径）。
- **R21 [接受]**: AC-21 AST 静态分析覆盖不全（h1/CSS/类名）。字体路径不止 inline 属性，间接路径真实存在。dev 修订：AC-21 增 1 条「`<h1>` / `<h2>` / CSS 变量 / className 引用 4 种间接字号路径也必须经 AST 静态分析覆盖」；具体断言「标题节点字号（`<h1>` 默认 32px → AC-21 FAIL 因 ≥64 必需）必须用 inline `style={{fontSize: X}}` 显式声明 ≥64」；或新增独立 metric `<h1>` 使用次数=0 或全用 inline 标题字号 ≥64。
- **R22 [接受]**: AC-25 default `use_variants=false` 未测。FR-031 默认原题重考是合同硬约束，未断言等价于风险。dev 修订：AC-25 增 1 条「默认 `use_variants=false`（不传或 false）必须走原题重考（question_text 一字不差，非变体）」断言；toggles 默认值需在 contracts/http-api.md C-1 request schema 显式标注 default。

**汇总**：7 条接受 → 派 dev 修订 Round 3（最后一轮）。修订完成后 tester 再审一次；若 Round 3 仍有 ≥1 条接受的反例 → main-agent 取 tester 更严版本强制锁定。

---

## Tester 反驳日志 (Round 3, 2026-07-07, 终审)

> **Round 3 范围**：7 条 Round 2 反例全部落实 + 3 条新增 AC（AC-04c/09c/11c）+ 9 条改写（AC-02/06/07/09b/11b/12a/13/15/16b/19/21/23/25）。
> 本轮按 6 类问题系统性核查 40 条 AC，验证 dev 修订是否引入新漏洞。
> **结论：dev Round 3 修订无新漏洞，AC 完整可锁定。**

### 6 类核查结果

| # | 类别 | 核查结论 | 证据 |
|---|------|---------|------|
| 1 | **覆盖度** | ✅ 22 条 SC 全部映射到至少 1 条 AC（已确认 ac-matrix L194 "与 spec 的对齐"段）；3 条新增 AC（04c/09c/11c）填补 inline fixture / hash 公式 / cold-warm SLO 三类空缺 | ac-matrix.md L103-112 "AC 总数统计" + L194 "与 spec 的对齐" |
| 2 | **边界条件** | ✅ NOT VALID + VALIDATE 两阶段（R16）避免 migration 0028 CheckViolation；cold 60s/warm 30s 分窗口（R20）规避 arq cold-start；4 种间接字号路径（R21）堵漏 CSS/className/h1；5-case inline 兜底集（R17）堵 T094 schedule race | data-model.md L21-22; AC-04c; AC-11c; AC-21 |
| 3 | **可观测性** | ✅ AC-09c `redis-cli KEYS` key 长度公式 70 字符精确计算；AC-19/19b 黑名单字段枚举（question_text/score/answer/expected_points/interview_plan）；AC-21 5 个 `--check-*` flag + `--min-inline 64` 阈值明确 | AC-09c L53; AC-19b L79; AC-21 L81 |
| 4 | **歧义** | ✅ AC-04c 5-case fixture 完全枚举（无模糊表述）；AC-11c cold 60s/warm 30s 数值明确；AC-12a 4 个常数 boundary case 完整 | AC-04c L47; AC-11c L57; AC-12a L63 |
| 5 | **并发/竞态** | ✅ AC-16b 三层覆盖：`last_practiced_at <= $new_now` 原子写 + late-writer 不覆盖 assertion + test_concurrent_last_practiced_at_serializable；AC-09c SHA256 公式锁 hash 算法避免跨服务漂移 | AC-16b L69; AC-09c L53 |
| 6 | **PII / 安全** | ✅ AC-19 直接 SQL 断言 `payload ? 'question_text' = false AND ...`；AC-19b 黑名单 5 字段审计脚本；analytics_events RLS 在 data-model.md L70 显式启用 | AC-19 L78; AC-19b L79; data-model.md L70 |

### 7 条 Round 2 修订落实情况核查

| 反驳 | 落实证据 | 状态 |
|---|---|---|
| R16 | data-model.md L21 NOT VALID 注释 + L22 VALIDATE 异步注释；AC-12a 增 NOT VALID 验证 + AC-15 增 alembic upgrade smoke | ✅ 完整落实 |
| R17 | AC-04b `@pytest.mark.skipif(not eval_set_exists())` 守卫 + AC-04c 5-case inline fixture 兜底集（[(分布式事务, distributed_systems), (微服务, architecture), (RAG, tech_depth), (分布式锁, distributed_systems), (服务降级, architecture)]）| ✅ 完整落实 |
| R18 | AC-09b 同一输入 Redis key 相等 assertion + AC-09c SHA256 + user_id 前缀公式；data-model.md L98 同步公式（`sha256(jd_text.encode('utf-8') + error_pool_hash.encode('utf-8'))[:32]`）；contracts/http-api.md C-3 L133 同步 `key_hex = sha256(jd_text + error_pool_hash)[:32]` | ✅ 完整落实 |
| R19 | AC-16b 增 `last_practiced_at <= $new_now RETURNING ...` 原子写 + late-writer assertion（必须等于 max(三个 now())）+ test_concurrent_last_practiced_at_serializable | ✅ 完整落实 |
| R20 | AC-11b 增 warm-up 30s 流程（arq 启动 + sleep 30 + INSERT RETURNING id）+ AC-11c 新增 cold 60s / warm 30s SLO 分离 | ✅ 完整落实 |
| R21 | AC-21 增 4 种间接字号路径覆盖（inline `style={{fontSize: X}}` / className CSS 类 / `style={{fontSize: 'var(--title-size)'}}` CSS 变量 / `<h1>`-`<h6>` 标签默认）+ 5 个 `--check-*` flag（`--check-inline-style --check-h1-default --check-css-variable --check-classname --min-inline 64`）| ✅ 完整落实 |
| R22 | AC-25 增 default `use_variants=false|undefined` 必须走原题重考 assertion（`error_question_ids[*].question_text == error_questions[source_question_id].question_text` 一字不差）+ contracts/http-api.md C-1 L23 同步 `default false` 标注 | ✅ 完整落实 |

### 反驳小结（Round 3 终审）

dev Round 2 修订 **7/7 全部落实 + 无新漏洞**：
- 3 条新增 AC（AC-04c/09c/11c）填补 inline fixture / hash 公式锁定 / cold-warm SLO 分离
- 9 条改写（AC-02/06/07/09b/11b/12a/13/15/16b/19/21/23/25）覆盖原 7 条反驳的 3 件套要求（反例 + 验证命令 + 具体建议）
- data-model.md + contracts/http-api.md 同步增 NOT VALID / SHA256 公式 / default false 标注

**Round 3 无新反例，AC 完整可锁定 → 主 Agent 锁定 → 进 Phase 2 dev 实施。**