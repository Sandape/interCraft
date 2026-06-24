# 审查报告 REQ-026

## 第 1 次审查

### 判定：PASS

**需求**：Agent Eval-Driven Self-Improvement Loop
**范围**：US1 核心护栏 (ChineseFidelityChecker) + US2 骨架 (GoldenCase loader + 10 cases) + US1 集成 (EvalRunner + pytest plugin + CLI)
**验证**：60 eval tests passed / 466 全量 passed / CLI smoke 10/10 pass / typecheck pre-existing error (与 026 无关)

---

## 审查维度结果

### 1. Constitution Principle I (Library-First) — PASS

`backend/app/eval/` 自包含：
- `checker.py`：纯 stdlib (json + re + unicodedata + dataclasses)，无第三方依赖
- `golden_loader.py`：stdlib + structlog
- `runner.py`：stdlib + structlog + app.eval 内部模块；graph node 函数通过 lazy import (`from app.agents.interview.nodes.score import ...` 在方法内部) 调用，保持顶层 import 干净
- `cli.py`：stdlib + structlog + app.eval 内部模块
- `__init__.py` 提供 public API docstring（用途 / 公开类 / 公开函数）
- 无 FastAPI / DB / LangGraph runtime 依赖；EvalRunner 通过 `patch` 替换 `get_llm_client` + `_sink_to_error_book`，避免 DB 调用

轻微建议：可在 `backend/app/eval/` 下补一个 README.md 描述用途/API/配置/示例命令（当前 `__init__.py` docstring 已覆盖基本内容，但 README 可见性更好）。

### 2. Constitution Principle II (CLI Interface) — PASS

`app/eval/cli.py` 符合文本 I/O 协议：
- 参数输入：`run --mode mock --node X --spec-dir Y --report-out Z --model-name N` (argparse)
- 结果写 stdout：per-case verdicts + per-node aggregate + total stats
- 错误写 stderr：`print(..., file=sys.stderr)` 用于 "no cases found" / "no cases match --node"
- 退出码：0 (all pass) / 1 (some fail) / 2 (invocation error) — 符合 spec
- `--report-out path.json` 输出 JSON 报告（FR-013 序列化格式）
- argparse `choices=["mock", "real"]` 校验 `--mode`

轻微建议：spec 提到 "--json 模式" 但未实现 stdout JSON 输出；当前 `--report-out` 写文件已覆盖 JSON 输出需求，stdout 仍为人类可读格式。可后续加 `--json` flag 直接 stdout 输出 JSON（非阻塞）。

### 3. Constitution Principle III (Test-First) — PASS

测试覆盖四个核心组件：
- `test_checker.py` (14 tests)：纯中文 / 纯英文 / 混合 / 空 / 标点 / 数字 / JSON wrapper / 嵌套 / violation_segments 提取
- `test_golden_loader.py` (13 tests)：10 cases 加载 / 缺失目录 / 缺失字段 / 重复 ID / 损坏 JSON / 非法 source / range 解析 / stale 标记
- `test_runner.py` (14 tests)：run_case 正常/回归/score_range/expected_contains/stale + run_all aggregate + EvalReport 序列化 + 真实 10 cases
- `test_golden_cases.py` (10 parametrized + 3 class tests)：每 case 一个 test + SC-003 recall 验证 + 全量 aggregate
- `conftest.py`：autouse fixture 重置 LLM client singleton

轻微建议：CLI 缺自动化测试（test_cli.py 缺失）。tasks.md T040/T041 未要求 CLI 测试，但 exit code 语义 (0/1/2) + --node filter + --report-out 写文件逻辑值得补测。非阻塞。

### 4. Constitution Principle V (Observability) — PASS

`EvalReport` 结构化报告包含：
- `timestamp` (ISO 8601 UTC)
- `git_sha` (从 `git rev-parse --short HEAD` 或 `GIT_SHA` env var 读取)
- `model` (mock-llm / deepseek-v4-pro)
- `total_cases / passed_cases / failed_cases / skipped_cases`
- `per_node` 聚合（pass_rate + avg_chinese_fidelity）
- `case_results` 每案 verdict + metrics + failure_reasons

`to_json()` 输出 FR-013 格式；`to_dict()` 供程序消费。

029 OTel 边界清晰：026 不 emit OTel spans（US3 deferred 到 029）；git_sha + timestamp 可作为 029 trace 关联锚点。✅

### 5. 代码质量 — PASS（含轻微建议）

**checker.py JSON-aware 提取**：
- `_extract_text_for_fidelity` 先尝试 `json.loads`，失败则返回原文（纯文本 summary_md 场景）
- `_collect_string_values` 递归处理 dict / list / 非 string 值（返回 ""）
- L005 lesson 正确应用：JSON keys 不参与字符比例计算，只统计 string values
- 实测：嵌套 dict / 数组 / 非 string 值均正确处理

**golden_loader.py stale 处理**：
- 缺 `case_id` / `node` → 跳过（不可识别）
- 缺 `label` / 非法 `source` / 非法 `status` / `input_state` 非 dict / `llm_response` 非 str → 标记 `stale` 但仍加载
- 重复 `case_id` → 后加载的跳过 + structlog warning
- 损坏 JSON → 跳过 + structlog warning

**runner.py fail-fast**：
- 不支持的 node → `raise ValueError(f"unsupported_node:{node}")`
- node invocation 异常 → 捕获并记录 `node_invocation_error:{type:msg}`，不中断其他 case

**轻微建议**：
- `runner.py:229-230` `failed` 计数用 `" ".join(r.failure_reasons)` 子串检查，`skipped` 用 `any(... in fr for fr in ...)`；两处逻辑等价但写法不一致，建议统一为 `any(...)` 形式更清晰
- `runner.py:275-282` `_invoke_score_node` 中 `from app.agents.interview.nodes.score import _sink_to_error_book, score_node` 后用 `_ = _sink_to_error_book` 静默 F841；`patch` 接受字符串 target 已能自行导入模块，显式 import 多余，建议删掉冗余 import + `_ =` 静默行
- `runner.py:71-74` `to_json` 的 `default` 函数 `hasattr(obj, "__dict__")` 分支过宽（Path 等类型也有 `__dict__`）；`asdict(self)` 已递归转换 CaseResult，`default` 实际很少触发，可简化为 `return str(obj)` 单分支
- `cli.py` 无 `--json` stdout 模式（轻微，`--report-out` 已覆盖文件输出）

### 6. 安全性 — PASS

- **PII**：10 个 golden cases 全部使用 placeholder UUID (`00000000-0000-0000-0000-000000000001/2`) + `"user_answer": "..."` 占位符，无真实 PII ✅
- **Quota**：mock 模式 patch LLM client，不调 DeepSeek，不烧 quota；real 模式 opt-in（`--mode real`），用户手动管理；`_pre_deduct` 对不存在的 user_id 返回（不扣 quota），但实际 API token 仍消耗 DEEPSEEK_API_KEY 额度 — spec assumption 说 "non-production LLM quota bucket" 未实现独立 bucket，属 partial scope gap（US3+ 阶段补）
- **Env var**：`DEEPSEEK_API_KEY` / `LLM_MOCK_MODE` / `GIT_SHA` 读取安全（无 f-string 拼接 SQL）；`subprocess.run(["git", "rev-parse", ...])` 用列表形式无 shell 注入 ✅

### 7. 一致性 — PASS

- 5 graph 集成点：仅 interview (score + report) 接入；其余 4 graph (error_coach / resume_optimize / ability_diagnose / general_coach) 在 tasks.md Phase 10 标 ⏳ 后续 ✅
- 029 OTel 边界：plan.md 明确 "US3 完整 trace 采集 (029 OTel 接管)"；026 仅有 git_sha + timestamp 锚点，不 emit OTel spans ✅
- 测试目录 `backend/tests/eval/` 符合 AGENTS.md canonical test roots ✅
- golden cases 放 `specs/026-agent-eval-loop/golden/` 符合 FR-008 (版本控制随 spec 同步) ✅

### 8. partial 范围合理性 — PASS

`tasks.md` 清晰记录 ⏳ 后续项：
- Phase 7 (US3 trace) — 6 tasks T060-T065 全 ⏳
- Phase 8 (US4 DSPy) — 5 tasks T070-T074 全 ⏳
- Phase 9 (US5 self-evolution) — 5 tasks T080-T084 全 ⏳
- Phase 10 (US2 其余 4 graph golden cases) — 4 tasks T090-T093 全 ⏳
- T053 (requirements-status.md) ⏳

`plan.md` "Partial Scope Justification" 节明确收窄理由 (L004 api-quota-risk 教训) ✅
无过度完成度声明 ✅

### 9. plan.md / tasks.md 质量 — PASS

- plan.md 按 `.specify/templates/plan-template.md` 结构：Summary / Technical Context / Constitution Check / Project Structure / Implementation Strategy / Complexity Tracking / Partial Scope Justification
- Constitution Check 节含 5 原理表 (I-V) 全 ✅
- Complexity Tracking 节为空（无违规）✅
- tasks.md 按 `.specify/templates/tasks-template.md` 结构：Phase 组织 / [P] 标记 / [US] 标签 / Format / Dependencies / Implementation Strategy / Notes
- tasks.md "关键避坑" 节引用 L002 / L003 / L004 ✅

### 10. lesson L005 — PASS（含轻微建议）

L005 (ChineseFidelityChecker 必须先剥离 JSON wrapper 再计字符比例) 正确应用：
- `checker.py:179-199` `_extract_text_for_fidelity` 方法实现 JSON wrapper 剥离
- `checker.py:215-229` `_collect_string_values` 递归提取 string values
- 测试 `test_json_with_chinese_values_passes` + `test_english_feedback_regression_caught` 验证逻辑

轻微建议：plan.md / tasks.md "关键避坑" 节未显式引用 L005 ID（仅引用 L002/L003/L004）；建议在 tasks.md Notes 节补 L005 引用，便于回查。

---

## 发现的问题清单

| # | 严重度 | 维度 | 位置 | 原因 | 修改建议 |
|---|--------|------|------|------|----------|
| 1 | minor | 代码质量 | `backend/app/eval/runner.py:229-230` | `failed` 计数用 `" ".join()` 子串检查，`skipped` 用 `any(... in fr)`；逻辑等价但写法不一致 | 统一为 `any("stale_case_skipped" in fr for fr in r.failure_reasons)` |
| 2 | minor | 代码质量 | `backend/app/eval/runner.py:275-282` | `_invoke_score_node` 冗余 import `_sink_to_error_book` + `_ = _sink_to_error_book` 静默 F841 | 删除显式 import（patch 接受字符串 target 自行导入）+ 删除 `_ =` 行 |
| 3 | minor | 代码质量 | `backend/app/eval/runner.py:71-74` | `to_json` 的 `default` 函数 `hasattr(obj, "__dict__")` 分支过宽 | 简化为 `return str(obj)` 单分支（`asdict` 已递归转换） |
| 4 | minor | 测试覆盖 | `backend/tests/eval/` | 缺 `test_cli.py`；CLI exit code / --node / --report-out 逻辑无自动化测试 | 补 test_cli.py（tasks.md 未要求，非阻塞） |
| 5 | minor | 文档 | `backend/app/eval/` | 无 README.md 描述用途/API/配置/示例命令 | 可补 README.md（`__init__.py` docstring 已覆盖基本内容） |
| 6 | minor | 文档 | `specs/026-agent-eval-loop/tasks.md` Notes | "关键避坑" 节未引用 L005 | 补 L005 引用 |
| 7 | minor | CLI 协议 | `backend/app/eval/cli.py` | 无 `--json` stdout 模式 | 可后续加（`--report-out` 已覆盖文件输出，非阻塞） |

**无 severe / mid 问题。所有 minor 均为非阻塞建议。**

---

## 验证证据

- 60 eval tests passed: `cd backend && uv run pytest tests/eval/ -q` → 60 passed
- 466 全量回归: `cd backend && uv run pytest -q` → 466 passed, 26 skipped, 0 failed
- CLI smoke: `uv run python -m app.eval.cli run --mode mock` → 10/10 pass, exit 0
- typecheck: `npm run typecheck` → 1 pre-existing error (`markdown-it-emoji` 模块，与 026 无关；git stash 验证)

---

## code-simplification 执行结果

已对 `backend/app/eval/runner.py` 应用 3 处行为保持的简化：

1. **`run_all` 计数逻辑统一** (runner.py:228-236)
   - 前：`failed` 用 `" ".join()` 子串检查，`skipped` 用 `any(...)` — 写法不一致
   - 后：两者统一为 `any("stale_case_skipped" in fr for fr in r.failure_reasons)` 形式
   - 行为等价：stale case 仍只计为 skipped，不计为 failed

2. **`_invoke_score_node` 删除冗余 import** (runner.py:274-283)
   - 前：`from app.agents.interview.nodes.score import _sink_to_error_book, score_node` + `_ = _sink_to_error_book` 静默 F841
   - 后：仅 `from app.agents.interview.nodes.score import score_node`（`patch()` 接受字符串 target 自行导入模块）
   - 行为等价：patch 仍正确替换 `_sink_to_error_book` 模块属性

3. **`to_json` default 函数简化** (runner.py:66-75)
   - 前：`default` 函数含 `isinstance CaseResult` + `hasattr __dict__` + `str(obj)` 三分支；`hasattr` 分支过宽
   - 后：`default=lambda obj: str(obj)` 单分支（`asdict(self)` 已递归转换 CaseResult，default 仅处理意外非可序列化对象）
   - 行为等价：所有原有类型仍正确序列化

**验证**：简化后 `uv run pytest tests/eval/ -q` → 60 passed；`uv run python -m app.eval.cli run --mode mock` → 10/10 pass, exit 0。

## commit hash

`06950c4` — feat(026): agent eval-driven self-improvement loop (US1 + US2 partial)
