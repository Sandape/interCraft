# Tasks: Agent Eval-Driven Self-Improvement Loop

**Input**: Design documents from `/specs/026-agent-eval-loop/`

**Prerequisites**: plan.md, spec.md

**Tests**: Tests are included (Constitution III TDD). Each implementation phase
has test tasks first.

**Organization**: Tasks grouped by user story. **本次仅实现 US1 + US2 partial
+ US1 集成**；US3 / US4 / US5 任务列出但标记 ⏳ 后续。

**Partial Scope**: 见 plan.md "Partial Scope Justification" 节。本次实现范
围 = US1 核心护栏 + US2 骨架（10 cases）+ US1 集成（pytest plugin）。

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline + create directory structure.

- [X] T001 [P] Verify backend tests green: `cd backend && uv run pytest -q` (≥ 395 passed baseline)
- [X] T002 [P] Create `backend/app/eval/` package with empty `__init__.py`
- [X] T003 [P] Create `backend/tests/eval/` test directory with empty `__init__.py`
- [X] T004 [P] Create `specs/026-agent-eval-loop/golden/` directory + `interview_score/` + `interview_report/` subdirs

---

## Phase 2: Foundational (Chinese Fidelity Checker — BLOCKS US1 Integration)

**Purpose**: Build the ChineseFidelityChecker — the core defensive gate that
catches DeepSeek V4 Pro's zh-CN prompt → English output regression (per
`interview_report_chinese_caveat` lesson).

**⚠️ CRITICAL**: No US1 integration work can begin until this phase is complete.

### Tests for Foundational (TDD)

- [X] T010 [P] [US1] Unit test `backend/tests/eval/test_checker.py`:
  - `test_pure_chinese_text_passes` — 纯中文 → `is_correct=True`, `chinese_ratio ≥ 0.7`
  - `test_pure_english_text_fails` — 纯英文 → `is_correct=False`, `english_ratio ≥ 0.7`
  - `test_chinese_with_english_tech_terms_passes` — 中文为主 + 英文技术词 (React / useState) → `is_correct=True`
  - `test_empty_string_fails` — 空字符串 → `is_correct=False`, `score=0.0`
  - `test_only_punctuation_fails` — 仅 JSON 标点 / 数字 → `is_correct=False`
  - `test_english_feedback_regression_caught` — DeepSeek 实际返回的英文 feedback 样本 → `is_correct=False`
  - `test_english_summary_md_regression_caught` — DeepSeek 实际返回的英文 summary_md 样本 → `is_correct=False`
  - `test_english_only_segment_extracted` — 含连续 ≥ 5 英文单词段落 → `violation_segments` 非空

### Implementation for Foundational

- [X] T011 [US1] Implement `backend/app/eval/checker.py`:
  - `ChineseFidelityResult` dataclass: `expected_language, is_correct, chinese_ratio, english_ratio, violation_segments, score`
  - `ChineseFidelityChecker` class with `check(text, expected_language="zh-CN") -> ChineseFidelityResult`
  - CJK Unicode range detection (U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+2A700-2B73F, U+2B740-2B81F)
  - Threshold: `chinese_ratio ≥ 0.3` 视为合规（允许 70% 英文技术词混入）
  - 提取违规英文段落（连续 ≥ 5 个英文单词的 segment）
  - 纯标准库 `unicodedata` + `re`，不依赖 langdetect / deepeval

**Checkpoint**: Foundation ready — checker can detect Chinese/English fidelity.

---

## Phase 3: User Story 2 - Golden Dataset Loader + Sample Cases (Priority: P2)

**Goal**: 实现 golden case loader + interview score/report 两节点各 5 个共 10
个 sample case（FR-006/007/008 partial：1 graph × 2 节点 × 5 cases = 10 cases，
不满 20 但框架验证足够）。

**Independent Test**: `uv run pytest tests/eval/test_golden_loader.py -q` 全绿。

### Tests for User Story 2 (TDD)

- [X] T020 [P] [US2] Unit test `backend/tests/eval/test_golden_loader.py`:
  - `test_load_returns_10_cases` — `load_golden_cases(spec_dir)` 返回 10 个 `GoldenCase`
  - `test_missing_golden_dir_returns_empty` — 缺失 `golden/` 目录 → 返回空列表
  - `test_case_with_missing_field_marked_stale` — 单个 case JSON 缺 `node` 字段 → 标记 `status="stale"` 但不阻塞其他 case
  - `test_duplicate_case_id_skipped_with_warning` — `case_id` 重复 → 后加载的跳过 + structlog warning
  - `test_case_fields_parsed_correctly` — `expected_score_range: [9, 10]` 解析为 tuple
  - `test_source_field_validates_manual_or_promoted` — 非法 `source` 值 → 标记 `stale`

### Implementation for User Story 2

- [X] T021 [US2] Implement `backend/app/eval/golden_loader.py`:
  - `@dataclass GoldenCase`: `case_id, node, label, source, input_state, llm_response, expected_language="zh-CN", expected_contains=[], expected_score_range=None, expected_overall_score_range=None, expected_fidelity_pass=True, status="active"`
  - `load_golden_cases(spec_dir: Path) -> list[GoldenCase]`
  - 遍历 `golden/**/*.json`，逐文件解析；任一文件解析失败 → 标记 stale 但不阻塞
  - `case_id` 去重：dict 跟踪已加载 ID，重复跳过 + warning log

- [X] T022 [P] [US2] Write 5 golden cases for `interview.score` node in `specs/026-agent-eval-loop/golden/interview_score/`:
  - `case_01_high_chinese.json` — 高分 (score=9) + 中文 feedback
  - `case_02_mid_chinese.json` — 中分 (score=6) + 中文 feedback
  - `case_03_low_chinese.json` — 低分 (score=3) + 中文 feedback
  - `case_04_english_regression.json` — ⚠️ 回归 case: zh-CN prompt → 英文 feedback, `expected_fidelity_pass: false`
  - `case_05_short_answer.json` — 边缘 case: 短回答 (5 字) + 中文 feedback

- [X] T023 [P] [US2] Write 5 golden cases for `interview.report` node in `specs/026-agent-eval-loop/golden/interview_report/`:
  - `case_01_strong_chinese.json` — 强表现 + 中文 summary_md (5 轮均 8+)
  - `case_02_weak_chinese.json` — 弱表现 + 中文 summary_md (5 轮均 4-)
  - `case_03_mixed_chinese.json` — 混合表现 + 中文 summary_md (3 高 2 低)
  - `case_04_english_regression.json` — ⚠️ 回归 case: zh-CN prompt → 英文 summary_md, `expected_fidelity_pass: false`
  - `case_05_minimal_scores.json` — 边缘 case: 仅 1-2 轮 scores + 中文 summary_md

- [X] T024 [P] [US2] Write `specs/026-agent-eval-loop/golden/README.md`: case 格式规范 + 如何添加新 case + 如何标记 stale

**Checkpoint**: 10 golden cases loaded + parsed; loader tested.

---

## Phase 4: User Story 1 - EvalRunner + Node Invocation (Priority: P1) 🎯 MVP

**Goal**: EvalRunner 调用真实 node 函数（mock LLM 注入），生成 per-case +
aggregate 报告。CI 可跑 `uv run pytest tests/eval/ -q` 验证。

**Independent Test**: `uv run pytest tests/eval/test_runner.py -q` 全绿 + `uv
run pytest tests/eval/test_golden_cases.py -q` 10 cases 全部按预期通过/失败。

### Tests for User Story 1 (TDD)

- [X] T030 [P] [US1] Unit test `backend/tests/eval/test_runner.py`:
  - `test_run_case_pure_chinese_passes` — 纯中文 case → `passed=True`
  - `test_run_case_english_regression_fails` — 英文回归 case → `passed=False, failure_reasons` 含 `chinese_fidelity`
  - `test_run_case_expected_score_range_violation` — 期望 score 9-10，实际 5 → `passed=False`, `failure_reasons` 含 `score_range`
  - `test_run_case_expected_contains_missing` — 期望含 "React" 关键词，actual 无 → `passed=False`, `failure_reasons` 含 `expected_contains`
  - `test_run_case_expected_fidelity_pass_false` — `expected_fidelity_pass=false` 的 case + checker 抓到 → `passed=True`（验证 checker 真能抓回归）
  - `test_run_all_returns_eval_report` — 10 cases → `EvalReport{total=10, passed=9, failed=1}`
  - `test_eval_report_contains_git_sha_and_model` — `git_sha` 非空 + `model="mock-llm"`
  - `test_eval_report_to_json_serializable` — `to_json()` 返回可 `json.loads` 的 string

- [X] T031 [P] [US1] Integration test `backend/tests/eval/test_golden_cases.py`:
  - parametrize 10 cases，每 case 一个 test
  - 中文 case 期望 `passed=True`
  - 英文回归 case 期望 `passed=False` 且 `failure_reasons` 含 `chinese_fidelity`
  - 验证 SC-003：Chinese fidelity recall = 2/2 = 100%（2 个回归 case 全捕获）

### Implementation for User Story 1

- [X] T032 [US1] Implement `backend/app/eval/runner.py`:
  - `@dataclass CaseResult`: `case_id, node, passed, metrics{chinese_fidelity, answer_correctness}, actual_output, failure_reasons[]`
  - `@dataclass EvalReport`: `timestamp, git_sha, model, total_cases, passed_cases, failed_cases, skipped_cases, per_node{}, case_results[]`
  - `class EvalRunner`:
    - `__init__(cases, mode="mock")` — `mode="mock"` 用 stub LLM client；`mode="real"` 走真实 DeepSeek (opt-in)
    - `async run_case(case) -> CaseResult`:
      1. 调 `ChineseFidelityChecker.check(case.llm_response)` → fidelity 指标
      2. 若 `mode="mock"`: patch `get_llm_client` 返回 stub (yield `case.llm_response`)
      3. Patch `_sink_to_error_book` 为 no-op（避免 DB 调用 — eval 不依赖 DB）
      4. 调用真实 node 函数 (`score_node` / `report_node`)
      5. 校验 `expected_contains` keywords
      6. 校验 `expected_score_range` / `expected_overall_score_range`
      7. 处理 `expected_fidelity_pass=false` 反向断言
    - `async run_all() -> EvalReport`
  - `EvalReport.to_json() -> str` — FR-013 序列化格式

- [X] T033 [US1] Write `backend/tests/eval/conftest.py`:
  - `eval_cases` fixture: 调 `load_golden_cases(specs/026-agent-eval-loop/)`
  - `eval_runner` fixture: 构造 `EvalRunner(mode="mock")`
  - autouse `_reset_llm_singleton`: 每 test 前后 reset `app.agents.llm_client._llm_client_singleton` + `_mock_client_singleton`

**Checkpoint**: EvalRunner can replay 10 cases through real nodes; per-case + aggregate reports generated.

---

## Phase 5: CLI + Regression Gate Hook (Priority: P1)

**Goal**: CLI 可跑 + pytest plugin 集成完成。

- [X] T040 [US1] Implement `backend/app/eval/cli.py`:
  - `python -m app.eval.cli run --mode mock` — 跑全量 cases
  - `--node interview.score` — 过滤单节点
  - `--report-out path.json` — 写 JSON 报告
  - 退出码：0 = 全 pass；1 = 有 case 失败（非回归 case）；2 = 回归 case 未捕获（checker 失效）

- [X] T041 [US1] Verify `uv run pytest tests/eval/ -q` 全绿 — 10 cases + 单测全过

**Checkpoint**: US1 + US2 partial complete — eval suite CI-runnable.

---

## Phase 6: Polish & Regression

- [X] T050 Run `cd backend && uv run pytest -q` — 全量回归零失败（≥ 395 passed + eval 新增）
- [X] T051 Run `npm run typecheck` — 前端 clean（本 feature 不动前端）
- [X] T052 Update `specs/README.md` 026 行 Status 为 `in_progress (US1 + US2 partial)`
- [ ] T053 [P] Write `specs/026-agent-eval-loop/requirements-status.md` 标记 US1 done / US2 partial / US3-5 ⏳ — **⏳ 后续**（US1 全量回归 + SC-003 实测后补）

---

## Phase 7: ⏳ Deferred — US3 Trace Collection (Priority: P2, 后续)

**Goal**: 中央化 trace 采集，每个 LLM call / tool call / node transition 留痕。

**依赖**: 029 OTel 接管 trace — 本 feature 不实现，仅占位。

- [ ] T060 [US3] ⏳ Trace schema 设计：`TraceEvent{trace_id, user_id, graph, node, event_type, payload, ts}`
- [ ] T061 [US3] ⏳ LangGraph node enter/exit hook → 写 trace event
- [ ] T062 [US3] ⏳ LLM client invoke wrapper → 写 LLM call trace event (input messages + output + tokens + latency)
- [ ] T063 [US3] ⏳ Tool call wrapper → 写 tool call trace event
- [ ] T064 [US3] ⏳ Trace query API: `GET /api/v1/traces?user_id=X&graph=Y&since=Z`
- [ ] T065 [US3] ⏳ Trace retention: 30d 后自动 expired 标记（不清空，仅返回 expired 信号）

**Checkpoint**: ⏳ 后续 — 029 OTel 接管后本 phase 可作 fallback 路径。

---

## Phase 8: ⏳ Deferred — US4 Prompt Optimization (Priority: P3, 后续)

**Goal**: DSPy-based 自动 prompt 优化，对指定高价值 node 生成 candidate prompt。

**依赖**: US2 完整 golden dataset (≥ 20 cases per node) + 引入 DSPy 包（需
评估兼容性）。

- [ ] T070 [US4] ⏳ 评估 DSPy 包兼容性（Python 3.11 + pydantic 2.13）
- [ ] T071 [US4] ⏳ 设计 optimizer 算法 (BootstrapFewShot / MIPRO)
- [ ] T072 [US4] ⏳ `POST /api/v1/eval/optimize` endpoint: 输入 node 名 → 返回 PromptProposal
- [ ] T073 [US4] ⏳ `PromptProposal` DB 表 + 状态机 (pending/approved/rejected)
- [ ] T074 [US4] ⏳ Approve / reject API + reviewer signature

**Checkpoint**: ⏳ 后续 — US2 完整后启动评估。

---

## Phase 9: ⏳ Deferred — US5 Self-Evolution Feedback Loop (Priority: P3, 后续)

**Goal**: production trace 通过 review workflow 升级为 golden case。

**依赖**: US3 trace 采集 + US2 golden dataset。

- [ ] T080 [US5] ⏳ FeedbackSignal DB 表 + 隐式信号采集 (re-attempt / abandonment)
- [ ] T081 [US5] ⏳ `POST /api/v1/eval/feedback` endpoint (frontend 后续接入)
- [ ] T082 [US5] ⏳ Trace → GoldenCase candidate 转换 workflow
- [ ] T083 [US5] ⏳ PII redaction 在 promotion 前强制执行
- [ ] T084 [US5] ⏳ Promotion review API + reviewer signature

**Checkpoint**: ⏳ 后续 — US3 完成后启动。

---

## Phase 10: ⏳ Deferred — US2 Golden Dataset 扩展 (Priority: P2, 后续)

**Goal**: 其余 4 graph 的 golden cases 补齐（每 graph 至少 20 cases per FR-006）。

- [ ] T090 [US2] ⏳ error_coach golden cases (evaluate + hint_ladder 节点各 10)
- [ ] T091 [US2] ⏳ resume_optimize golden cases (generate + critique 节点各 10)
- [ ] T092 [US2] ⏳ ability_diagnose golden cases (aggregate + update 节点各 10)
- [ ] T093 [US2] ⏳ general_coach golden cases (respond 节点 20)

**Checkpoint**: ⏳ 后续 — interview 框架验证后批量补。

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — create dirs + verify baseline
- **Foundational (Phase 2)**: BLOCKS US1 integration — checker must exist before runner
- **US2 (Phase 3)**: Depends on Phase 2 (loader uses no checker, but cases are fed to runner in Phase 4) — can run in parallel with Phase 2
- **US1 integration (Phase 4-5)**: Depends on Phase 2 + Phase 3
- **Polish (Phase 6)**: Depends on Phase 4-5 complete
- **⏳ Deferred (Phase 7-10)**: Future work — US3/US4/US5/US2-扩展

### Within Each User Story

- Tests first (TDD) — watch them fail, then implement
- Library code before CLI/integration
- Single-file changes can run in parallel ([P] marker)
- Node invocation depends on stub LLM client fixture (conftest)

### Parallel Opportunities

- Phase 2 (checker) + Phase 3 (loader + cases) can run in parallel
- Within Phase 3, T022 + T023 can run in parallel (different files)
- Within Phase 4, T030 + T031 can run in parallel (different files)

---

## Implementation Strategy

### MVP First (US1 + US2 partial only)

1. Complete Phase 1: Setup (dirs + baseline green)
2. Complete Phase 2: ChineseFidelityChecker (TDD)
3. Complete Phase 3: GoldenCase loader + 10 cases
4. Complete Phase 4: EvalRunner + node invocation
5. Complete Phase 5: CLI + pytest plugin
6. **STOP and VALIDATE**: `uv run pytest tests/eval/ -q` + `uv run pytest -q` 全绿
7. **DEFER**: US3 (trace) → 029 OTel；US4 (DSPy) → 单独评估；US5 (self-evolution) → 依赖 US3

### Incremental Delivery (Future)

1. Add US3 trace collection (after 029 OTel decision)
2. Extend US2 to 4 remaining graphs (after interview framework validated)
3. Add US4 prompt optimization (after US2 full + DSPy evaluation)
4. Add US5 self-evolution (after US3 trace data available)

---

## Notes

- [P] tasks = different files, no dependencies
- Constitution III TDD: tests first, watch them fail, then implement
- Commit after each phase or logical group
- Stop at any checkpoint to validate story independently
- **Partial scope**: 本次仅实现 US1 + US2 partial + US1 集成；US3/US4/US5 + US2 扩展全部 ⏳ 后续
- **关键避坑**:
  - L004 (api-quota-risk): 范围已收窄，不扩展实现 US3/US4/US5
  - L003 (interview-caveat): DeepSeek 偶发吐英文，fidelity checker 必须覆盖 low score 和 high score 双样本（已在 case_04 + case_05 覆盖）
  - L002 (test-pattern): eval suite 测试放 `backend/tests/eval/`，不污染 integration / unit 目录
