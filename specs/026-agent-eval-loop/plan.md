# Implementation Plan: Agent Eval-Driven Self-Improvement Loop

**Branch**: `026-agent-eval-loop` | **Date**: 2026-06-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-agent-eval-loop/spec.md`

## Summary

为 5 个 LangGraph agent 建立 eval 驱动的质量护栏。本次 **partial 实现**：聚焦
US1 核心护栏（Chinese fidelity checker — 直接对准历史教训
`interview_report_chinese_caveat`，DeepSeek V4 Pro 在 zh-CN prompt 下偶发返回
英文 summary_md / feedback）+ US2 骨架（golden dataset loader + interview
score/report 两节点各 5 个共 10 个 sample case）+ US1 集成（pytest eval plugin
可在 CI 跑 `uv run pytest tests/eval/ -q`）。

US3 完整 trace 采集 / US4 DSPy 自动优化 / US5 self-evolution feedback loop /
US2 其余 4 个 graph 的 golden cases 全部标记 ⏳ 后续 — 依赖 029 OTel 接管
trace，DSPy 引入需单独评估，self-evolution 需要 US3 trace 数据。

**关键约束**：不引入 langsmith / deepeval / dspy 等大包，自研轻量 fidelity
checker（Unicode 范围 + 规则）。LangSmith 0.8.15 已作为 langgraph 传递依赖存
在，但需要 API key 才能 upload trace，故 US3 轻量版跳过 LangSmith 集成，
eval suite 不依赖它。

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI, LangGraph 0.2.28, openai 1.109 (DeepSeek
V4 Pro OpenAI 协议), pydantic 2.13, structlog, prometheus_client, pytest
8 + pytest-asyncio 0.23。**不新增依赖**（langdetect / deepeval / langsmith /
dspy 全部不引入）。

**Storage**: JSON / YAML 文件作为 golden cases（FR-008：版本控制随 spec 同
步）。`EvalRun` 报告为 in-memory dataclass + JSON 序列化输出（FR-013 持久
化在 US3+ 阶段引入 DB 表）。

**Testing**: pytest（eval 模块自身单测在 `backend/tests/eval/`，golden cases
replay 在 `backend/tests/eval/test_golden_cases.py`）。

**Target Platform**: Linux server (CI) + dev 本地（Windows + bash）。

**Project Type**: Library（`backend/app/eval/`）+ pytest plugin +
CLI（`uv run python -m app.eval.cli`）。

**Performance Goals**: 全量 eval suite（10 cases）跑完 ≤ 30s（mock 模式）；
真实 DeepSeek 模式 opt-in（不强制 CI 跑）。

**Constraints**: 不改 graph 业务节点逻辑；不改 LLM client 契约；不改 API 契
约；既有 395+ 后端测试零回归；既有 64/64 E2E 零回归（本 feature 不动 E2E）。

**Scale/Scope**: 本次实现 1 个 graph（interview）的 2 个高价值节点
（score / report）的 golden cases；其余 4 graph × N 节点 ⏳ 后续。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ Pass | `backend/app/eval/` 自包含库：`checker.py` + `golden_loader.py` + `runner.py` + `cli.py`。无 DB 依赖、无 FastAPI 依赖、可独立 import。5 个 graph 后续接入时仅 import 这个库。 |
| II. CLI Interface | ✅ Pass | `uv run python -m app.eval.cli run --mode mock` 可跑全量；`--node interview.score` 可过滤；`--report-out path.json` 输出 JSON 报告。CI 通过 `uv run pytest tests/eval/ -q` 跑 pytest 路径。 |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | TDD：先写 `test_checker.py`（fidelity 正负样本）+ `test_golden_loader.py`（loader 正负样本）+ `test_runner.py`（runner 端到端）+ `test_golden_cases.py`（10 cases 全部 replay 通过）。 |
| IV. Integration & Synchronization Testing | ✅ Pass | golden cases 真实跑过 `score_node` / `report_node` 函数（mock LLM client 注入），不是纯字符串比较。验证 node 的 prompt assembly + JSON parsing + state shape 完整链路。 |
| V. Observability | ✅ Pass | 每个 case 输出 `CaseResult{passed, metrics{chinese_fidelity, answer_correctness, scoring_consistency}, failure_reasons}`；aggregate `EvalReport` 含 per-node + total stats；JSON 报告含 timestamp + git_sha + model id（FR-013）。 |

**Gate Result**: PASS — 无违规项，无需 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/026-agent-eval-loop/
├── plan.md              # This file
├── tasks.md             # Phase 2 output
├── spec.md              # Existing
└── golden/              # US2 golden cases (FR-008: version-controlled)
    ├── README.md         # Case format spec + how to add new cases
    ├── interview_score/  # 5 cases for interview.score node
    │   ├── case_01_high_chinese.json
    │   ├── case_02_mid_chinese.json
    │   ├── case_03_low_chinese.json
    │   ├── case_04_english_regression.json   # ⚠️ known-bad: zh-CN prompt → English feedback
    │   └── case_05_short_answer.json
    └── interview_report/ # 5 cases for interview.report node
        ├── case_01_strong_chinese.json
        ├── case_02_weak_chinese.json
        ├── case_03_mixed_chinese.json
        ├── case_04_english_regression.json   # ⚠️ known-bad: zh-CN prompt → English summary_md
        └── case_05_minimal_scores.json
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── eval/                        # 新增: 自包含 eval 库 (Constitution I)
│       ├── __init__.py
│       ├── checker.py               # ChineseFidelityChecker (Unicode 范围 + 规则)
│       ├── golden_loader.py         # GoldenCase dataclass + load_golden_cases()
│       ├── runner.py                # EvalRunner + CaseResult + EvalReport
│       └── cli.py                   # `python -m app.eval.cli` 入口
└── tests/
    └── eval/                        # 新增: eval 测试目录 (per AGENTS.md)
        ├── __init__.py
        ├── conftest.py              # pytest fixtures: stub LLM client, patch node deps
        ├── test_checker.py          # ChineseFidelityChecker 单测 (TDD)
        ├── test_golden_loader.py    # GoldenCase loader 单测 (TDD)
        ├── test_runner.py           # EvalRunner 端到端单测 (TDD)
        └── test_golden_cases.py     # 10 cases replay through real nodes
```

**Structure Decision**: `backend/app/eval/` 是 Library-First 自包含库（无
DB / FastAPI 依赖）；golden cases 放在 `specs/026-agent-eval-loop/golden/`
（FR-008 要求随 spec 版本控制）；eval 测试在 `backend/tests/eval/`（per
AGENTS.md canonical test roots）。

## Implementation Strategy

### Phase A — ChineseFidelityChecker (US1 核心)

**目标**: 实现 Chinese fidelity checker，直接对准
`interview_report_chinese_caveat` 教训（DeepSeek 偶发返回英文 summary_md /
feedback）。

1. TDD：先写 `test_checker.py` 断言：
   - 纯中文文本 → `is_correct=True`, `chinese_ratio ≥ 0.7`
   - 纯英文文本 → `is_correct=False`, `english_ratio ≥ 0.7`
   - 中文为主含英文技术词（React / useState / useMemo）→ `is_correct=True`
     （允许英文术语混入）
   - 空字符串 → `is_correct=False`, `score=0.0`
   - 仅 JSON 标点 / 数字 → `is_correct=False`
   - 回归样本：DeepSeek 实际返回的英文 feedback → `is_correct=False`
   - 回归样本：DeepSeek 实际返回的英文 summary_md → `is_correct=False`
2. 实现 `checker.py`：
   - `ChineseFidelityChecker.check(text, expected_language="zh-CN") -> ChineseFidelityResult`
   - CJK Unicode 范围检测：U+4E00-U+9FFF, U+3400-U+4DBF, U+20000-U+2A6DF 等
   - 计算中文/英文字符比例
   - 阈值：`chinese_ratio ≥ 0.3` 视为合规（允许 70% 英文技术词混入）
   - 提取违规英文段落（连续 ≥ 5 个英文单词）
3. 不依赖 langdetect / deepeval（纯标准库 `unicodedata` + `re`）。

### Phase B — GoldenCase Loader + 10 Sample Cases (US2 骨架)

**目标**: 实现 golden case loader，并为 interview 的 score / report 两节点
各写 5 个 sample case。

1. TDD：先写 `test_golden_loader.py` 断言：
   - `load_golden_cases(spec_dir)` 返回 10 个 `GoldenCase` 实例
   - 缺失 `golden/` 目录 → 返回空列表（不抛异常）
   - 单个 case JSON 缺字段 → 该 case 被标记 `stale` 但不阻塞其他 case
   - `case_id` 重复 → 后加载的 case 跳过并 warning log
2. 实现 `golden_loader.py`：
   - `@dataclass GoldenCase`：`case_id, node, label, source, input_state,
     llm_response, expected_language, expected_contains, expected_score_range,
     expected_overall_score_range, expected_fidelity_pass=True, status="active"`
   - `load_golden_cases(spec_dir: Path) -> list[GoldenCase]`
   - 遍历 `golden/**/*.json`，逐文件解析
3. 写 10 个 sample case JSON：
   - interview_score × 5：高 / 中 / 低分（中文 feedback）+ 1 个英文回归 case
   - interview_report × 5：强 / 弱 / 混合（中文 summary_md）+ 1 个英文回归 case + 1 个 minimal scores edge case
4. 回归 case 标记 `expected_fidelity_pass: false` — 验证 checker 能捕获该
   回归（这是 US1 独立测试：revert 已知好的 prompt，eval gate 应 block）。

### Phase C — EvalRunner + Node Invocation (US1 集成)

**目标**: EvalRunner 调用真实 node 函数（mock LLM 注入），生成 per-case +
aggregate 报告。

1. TDD：先写 `test_runner.py` 断言：
   - `EvalRunner.run_case(case)` 对纯中文 case 返回 `passed=True`
   - 对英文回归 case 返回 `passed=False, failure_reasons=["chinese_fidelity"]`
   - `run_all()` 返回 `EvalReport`，含 `total_cases=10, passed_cases=9,
     failed_cases=1`（1 个回归 case 期望失败）
   - `model="mock-llm"` 标识 mock 模式
   - `git_sha` 从环境变量或 `.git/HEAD` 读取
2. 实现 `runner.py`：
   - `EvalRunner.__init__(cases, mode="mock")`
   - `run_case(case)`:
     (a) 调用 `ChineseFidelityChecker.check(case.llm_response)` → fidelity 指标
     (b) Patch `get_llm_client` 返回 stub（yield `case.llm_response`）
     (c) Patch `_sink_to_error_book`（避免 DB 调用）
     (d) 调用真实 node 函数（`score_node` / `report_node`）→ actual_output
     (e) 校验 `expected_contains` keywords 在 actual_output 中
     (f) 校验 `expected_score_range` / `expected_overall_score_range`
     (g) 组装 `CaseResult`
   - `run_all()` → `EvalReport`
3. `EvalReport.to_json()` 序列化为 FR-013 要求的格式
   （timestamp + git_sha + model + per-case verdicts）。

### Phase D — pytest Plugin + CLI (US1 集成)

**目标**: eval suite 可在 CI 跑，提供 CLI 入口。

1. 写 `backend/tests/eval/conftest.py`：
   - `eval_cases` fixture：加载全部 golden cases
   - `eval_runner` fixture：构造 `EvalRunner(mode="mock")`
   - autouse fixture：在 eval 测试开始前重置 LLM client singleton
2. 写 `test_golden_cases.py`：parametrize 10 个 case，每个 case 一个 test
   - 中文 case 期望 `passed=True`
   - 英文回归 case 期望 `passed=False` 且 `failure_reasons` 含
     `chinese_fidelity`（验证 checker 真能抓到回归）
3. 实现 `cli.py`：`python -m app.eval.cli run --mode mock [--node X] [--report-out path.json]`
4. 验证 SC-003（Chinese fidelity ≥95% recall）：在回归 case 上断言
   `is_correct=False`，证明 checker 能 100% 捕获已知回归样本（10 个 case
   中 2 个回归，2/2 命中 = 100% recall，满足 SC-003 阈值）。

### Phase E — 回归验证

1. 跑 `cd backend && uv run pytest tests/eval/ -q` — 10 cases + 单测全绿
2. 跑 `cd backend && uv run pytest -q` — 全量回归零失败（≥ 395 passed）
3. 跑 `npm run typecheck` — 前端类型检查 clean（本 feature 不动前端，
   理应无变化）
4. 更新 `specs/README.md` 026 行 Status 为 `active / in_progress (US1 + US2 partial)`。

## Complexity Tracking

> 无 Constitution Check 违规，本节为空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Partial Scope Justification

本 feature 完整 spec 含 5 个 US，全部实现是 multi-week 级别工作。为避免单次
dev 调用 429 中断（教训 L004），本次范围收窄到 **US1 核心护栏 + US2 骨架 +
US1 集成**：

- **必须实现**：ChineseFidelityChecker + GoldenCase loader + 10 sample cases
  + EvalRunner + pytest plugin + CLI
- **标记后续 ⏳**：
  - US2 其余 4 graph golden cases（interview 框架验证后批量补）
  - US3 完整 trace 采集（029 OTel 接管，本 feature 仅用 MockLLMClient trace 够用）
  - US4 DSPy 自动优化（依赖重，单独评估）
  - US5 self-evolution feedback loop（依赖 US3 trace 数据）
