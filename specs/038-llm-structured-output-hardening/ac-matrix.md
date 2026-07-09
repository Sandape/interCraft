---
req_id: REQ-038
status: draft
locked_at: null
locked_by: null
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-038 (LLM Structured Output Hardening)

## SC Gaps

无。spec.md ## Success Criteria 已覆盖 6 个 SC + 14 FR + 4 US + Edge Cases 7 条，
AC 可完全对齐。

> 注：spec.md 未声明「provider 不可用时降级路径」「validation 失败最大重试次数」这两项参数化指标；
> dev 在 plan 阶段若发现需要，必须回 main-agent 走 SC 补流程，不允许 AC 擅自加阈值。
> 本次 AC 仅约束「存在/不存在」与「是/否」，不引入数值阈值。

## AC 矩阵

| AC-ID | 描述 | 验证方式（命令/测试名/可观测指标） | 来源 (spec.SC / FR-N) |
|-------|------|-----------------------------------|---------------------|
| AC-01 | **Coverage Registry 完整**：100% 的 LLM-producing Agent 节点在 `coverage_registry` 中存在条目；每个条目声明 (a) 节点标识 + (b) `kind ∈ {structured, free_form}` + (c) structured 节点必须挂载一个 Pydantic output contract 名称与版本，free_form 节点必须挂载 `FR-014 exclusion_reason`。 | `cd backend && uv run pytest tests/agents/test_coverage_registry.py -v` 期望：脚本枚举所有 `app/agents/**/nodes/*.py` 中识别为 LLM-producing 的节点，断言 (i) 无遗漏；(ii) structured 节点的 contract_name 与 version 非空；(iii) free_form 节点的 exclusion_reason 非空。 | SC-001, FR-001, FR-014 |
| AC-02 | **Missing-field 拒绝**：structured 节点（如 `planner_generate` / `score` / `intake`）在 mock 返回缺必填字段（缺 `question_text` / 缺 `score` 等）时，structured invocation API 返回 typed failure `StructuredOutputFailure(category=SCHEMA_VALIDATION, ...)`，下游 Agent state 未被写入。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_missing_field_rejected -v` 期望：mock 返回 `{"score": 0.7}`（缺必填 `dimension`），断言 (i) `result.kind == "failure"`；(ii) `result.failure.category == "schema_validation"`；(iii) graph state 中相关字段保持调用前的初值。 | SC-002, FR-004, FR-006 |
| AC-03 | **Wrong-type 拒绝**：structured 节点在 mock 把 `score: int` 字段返回成 `score: "high"`（类型错）时，validation 失败；不会因 duck-typing 而静默通过。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_wrong_type_rejected -v` 期望：mock 返 `{"score": "high", "dimension": "logic"}`，断言 (i) Pydantic `ValidationError`；(ii) failure category 标记为 `schema_validation`（非 transport/non-refusal）。 | SC-002, FR-004 |
| AC-04 | **Invalid-enum / out-of-range 拒绝**：scoring / routing 节点在 mock 返回 (a) enum 非法值（如 `intent="unknown_kind"`）或 (b) score 越界（如 `score=15.0` 当合法区间是 `[0,10]`）时，validation 在 consume 前失败。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_invalid_enum_and_out_of_range_rejected -v` 期望：两个子 case 分别断言 `result.failure.category == "schema_validation"` 且 graph state 未被 patch。 | SC-002, US1.AC-2 |
| AC-05 | **Extra-fields policy**：structured 节点按 contract 声明的 `extra_field_policy` 处理额外字段——`forbid` 必须 reject；`ignore` 必须 drop 但通过；policy 写在 contract 自身。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_extra_fields_policy -v` 期望：两个 contract 分别配置 forbid/ignore，mock 注入额外字段 `{"_debug": "...", ...}` 验证两条路径。 | FR-002, FR-004 |
| AC-06 | **Markdown-fence 包裹 / 多 JSON 包裹 / 截断 / refusal / tool-call-shape 全部 reject**：模拟 provider 返回 (a) ` ```json\n{...}\n``` ` 包裹的 JSON、(b) 多 JSON 对象、(c) 截断的 `{"score": 0.5, "dim`、(d) `{"refusal": "I can't"}` refusal-style 输出、(e) tool-call-shaped 输出（`choices[0].message.tool_calls` 而非 content）。所有路径必须被识别为 `provider_output_unparseable` 或 `schema_validation` failure，不进入 state。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_provider_edge_shapes -v`（5 个 parametrized case）期望：每种 shape 都被本地 validator 拒绝且不污染 state。 | Edge Cases 第 77-78 行 |
| AC-07 | **Provider-native structured output 优先**：当 active provider path 支持 schema enforcement（DeepSeek JSON mode / function_calling / 后续 OpenAI structured outputs）时，invocation API 必须调用 provider-native schema request（即在 OpenAI-compat 调用时传入 `response_format` 或 tool schema），并仅在 provider 不支持时退化到「prompt + 本地 Pydantic validation」。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_provider_native_request_used -v` 期望：(i) mock 底层 `openai` client 的 `chat.completions.create`，断言调用体含 `response_format` 或 `tools` 且 schema 来自 contract；(ii) 在 provider capability = "unsupported" 的 fixture 下，断言不传 `response_format` 但本地 validator 仍跑。 | FR-003 |
| AC-08 | **Authoritative free-text extraction 移除**：所有之前用 `re.search(r'\{.*\}', content)` + `json.loads(content)` 作为**权威**解析路径的节点（intake / score / error_coach.evaluate / general_coach.intent / resume_optimize.suggest_blocks / planner_generate 等），必须改走 structured invocation API；剩余 fallback 仅作为 typed failure 的 fallback，不允许在 `result.kind == "success"` 路径上使用正则+json.loads。 | `cd backend && uv run bash scripts/check_no_authoritative_regex_json.sh`（CI 脚本）期望：grep `re.search` / `json.loads` 在 `app/agents/**/nodes/*.py` 中命中数 = 0；或命中仅出现在 `MockLLMClient` / golden fixture 内部，作为非生产路径被 ignore 列表显式声明。同时 `uv run pytest tests/agents/test_structured_invocation.py::test_no_regex_json_in_production_nodes -v` 用 AST 扫描验证。 | SC-006, FR-005 |
| AC-09 | **Typed failure 完整覆盖**：structured invocation API 返回 `StructuredInvocationResult` typed union — `Success(model=<PydanticModel>)` 或 `Failure(category, contract_name, contract_version, node, field_errors, fallback_used: bool)`。`category` 枚举至少含：`transport / provider / quota / timeout / refusal / schema_validation / provider_output_unparseable / downstream_business_rule`。每个 category 必须能被 pytest 单测断言。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_failure_categories_enumerated -v` 期望：(i) `StructuredInvocationResult` 的 type stub 包含 union；(ii) 至少 8 个 category 在 fixture 中各跑一次单测且断言 category 名字与 reason。 | FR-006, FR-008 |
| AC-10 | **Deterministic fallback 行为**：当 product flow 可安全继续时（如 resume_optimize 不阻断导出），structured-output failure 必须返回 contract-declared fallback（typed dict / Pydantic `FallbackResult` 子类），且 (a) fallback 内容 deterministic（同一 contract 同一失败输入同一输出）；(b) `fallback_used=true` 在 trace span / log event / metric counter 中可见。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_deterministic_fallback -v` 期望：(i) 同一失败输入两次调用产出 byte-equal fallback；(ii) structlog `capture_logs()` 抓到 `structured_invocation.fallback_used` event；(iii) `prometheus_client` counter `structured_fallback_total{contract=...}` inc ≥ 1。 | FR-007, FR-009 |
| AC-11 | **失败分类不混淆**：schema_validation failure **绝不**作为 generic LLM error 出现在 trace / eval report / log 中；分类器/UI 看到的错误类型必须含 contract_name + field_errors。 | `cd backend && uv run pytest tests/agents/test_structured_invocation.py::test_schema_failure_not_classified_as_llm_error -v` 期望：(i) 触发 schema 失败；(ii) 通过 trace inspector 读取 `llm_invocation.failure_category` 字段，断言 == `"schema_validation"` 而非 `"llm_error"` / `"other"` / `null`。 | FR-008, SC-005, US3.AC-1 |
| AC-12 | **Observability 完整字段**：一次 structured invocation 完成的 trace span / log event 至少含 `node / contract_name / contract_version / validation_status / failure_category / fallback_used / retry_count / provider_path` 8 个字段；可在 eval report 中以 first-class result 出现（非 generic LLM error row）。 | `cd backend && uv run pytest tests/agents/test_observability.py::test_structured_invocation_emits_full_record -v` 期望：用 `structlog.testing.capture_logs()` 抓 invocation 完成 event，断言 8 字段全部存在且 `validation_status ∈ {passed, failed, fallback}`。同时跑 `tests/eval/test_structured_output_eval_report.py` 期望生成的 JSONL report 中每个 structured 节点有独立 row 含上述字段。 | SC-005, FR-009, US3.AC-1, US3.AC-2 |
| AC-13 | **Mock + 不合规 fixture 全部覆盖**：既有 `MockLLMClient` 必须升级到同一 public structured API（`invoke_structured(contract, prompt, ...)`）；golden eval fixture 必须新增至少 1 套「malformed-output」场景文件 per structured Agent 域（interview / error_coach / general_coach / resume_optimize / ability_diagnose / planner），每套至少含 4 类失败 fixture：missing-field / wrong-type / invalid-enum / out-of-range。 | (i) `cd backend && uv run pytest tests/agents/test_mock_client_structured_api.py -v` 期望：`MockLLMClient.invoke_structured` 存在且行为与 production `StructuredInvocation` 同构；(ii) `ls backend/app/agents/{interview,error_coach,general_coach,resume_optimize,ability_diagnose,planner}/eval_fixtures/structured_failures/` 期望 6 个目录各含 ≥ 4 个 `*.json` fixture；(iii) `cd backend && uv run pytest tests/agents/test_structured_failures_fixtures.py -v` 期望 6×4 = 24 个 fixture 全部正确触发对应 failure category。 | SC-004, FR-010, US2.AC-2, US2.AC-3 |
| AC-14 | **本地校验脚本拦截**：CI 加 `scripts/check_structured_coverage.py`：枚举 `app/agents/**/nodes/*.py` 中的 structured 节点（按 FR-014 exclusion list 排除 free_form），断言每个都挂载 Pydantic contract；缺失 contract 或绕过 validation 的节点 fail CI。 | `cd backend && uv run python scripts/check_structured_coverage.py` 期望：exit 0；(ii) 反向验证：临时给一个 structured 节点去掉 contract annotation → 重跑 exit 1 且 stderr 输出节点名 + 原因；(iii) `uv run pytest tests/agents/test_local_verification_check.py::test_missing_contract_fails_ci -v`。 | FR-012, US2.AC-1 |
| AC-15 | **A2A 边界 enforcement**：当 Agent A 通过 A2A 调用 Agent B 且 `AgentDefinition.output_schema` 声明时，Supervisor boundary 在 merge 结果到 graph state 前必须 validate；违规时 B 的输出不写入 state 且持久化到 `a2a_messages` 表带 `schema_validation_failed=true`。 | `cd backend && uv run pytest tests/agents/test_a2a_boundary.py::test_delegated_output_schema_enforced -v` 期望：(i) mock B 输出违反 `output_schema`；(ii) 调用方 state 未更新；(iii) `a2a_messages` 表出现新 row，`schema_validation_failed=true`，`failure_category='schema_validation'`；(iv) 反向：合规输出正常 merge。 | FR-011, US1 隐含 |
| AC-16 | **Redaction / 现有 observability 零回归**：既有 LLM 调用 trace 中的 redaction（PII / token / system prompt 等）、raw_payload access policy、prompt fingerprint 缓存、retry + quota 计数在 structured invocation 路径上必须保持原行为——redaction 仍在 trace 落地前生效；prompt fingerprint cache 在同 contract 同 prompt 下命中。 | (i) `cd backend && uv run pytest tests/agents/test_observability.py::test_redaction_preserved_on_structured_path -v` 期望：构造 PII 输入，断言 trace span 内仍 redaction；(ii) `test_prompt_fingerprint_cache.py::test_cache_hit_on_structured_path` 期望同 (contract, prompt) 第二次调用命中 cache；(iii) `test_quota_accounting.py::test_quota_incremented_on_structured_path` 期望 quota counter +1；(iv) `test_retry.py::test_retry_preserved_on_structured_path` 期望 retry 计数与 production path 一致。 | FR-009（兼容既有 redaction/trace）, FR-013, US4.AC-1 |
| AC-17 | **既有 suite 零回归**：现有 Agent unit / integration / E2E / golden eval 全量套件在开启 structured-output enforcement 后通过率 = 之前通过率（≤ 0 差异）；中文语言保真度（zh-CN）user-visible text field 仍验证通过。 | (i) `cd backend && uv run pytest -q --tb=line` 期望：所有 pre-existing 测试 PASS（含 `test_interview_*` / `test_error_coach_*` / `test_general_coach_*` / `test_ability_diagnose_*` 等）；(ii) `cd backend && uv run pytest tests/eval/test_language_fidelity.py -v` 期望中文样本通过率不降；(iii) `cd backend && uv run pytest tests/e2e/ -v`（若存在）期望同；(iv) 用 git diff 在前后两次跑取测试结果，diff = 空。 | SC-003, FR-013, US4.AC-1, US4.AC-2 |
| AC-18 | **Free-form 排除列表**：项目 `docs/contracts/structured_output_exclusions.md` 列出所有 FR-014 free_form 节点 + 排除理由；CI 校验 exclusion list 与 coverage registry 一致（双向）。 | (i) 文件存在且每行格式 `node_path | kind=free_form | reason=<非空>`；(ii) `cd backend && uv run python scripts/check_exclusion_list.py` 期望：exit 0；(iii) 反向：在 exclusion list 加一个不存在的节点 → exit 1；(iv) 反向：删 registry 中一个 free_form 节点而不同步 exclusion → exit 1。 | FR-014, SC-001（一致性） |

## 起草说明（写给 tester）

### 设计意图

REQ-038 是「LLM 输出侧」容灾硬化，与既有 023（checkpointer）/ 024（audit）/
035（admin）形成 orthogonal 容灾层：
- 023 解决「持久层 idle 断连」；
- 038 解决「模型层返回非契约数据」。
两条路径独立，互不阻塞。

Pydantic + provider-native schema 是 spec 调研结论（README ## Source-Checked Best Practice）；
AC-07 直接钉死 provider-native 优先 + 本地 Pydantic 兜底，避免 dev 走回 prompt-only 老路。

### 已覆盖的边界

- 缺字段 / 类型错 / enum 非法 / 越界 / 多余字段 / markdown-fence / 多 JSON / 截断 / refusal / tool-call-shape — 10 类（AC-02/03/04/05/06）
- mock 与 production API 同构 — AC-13
- redaction / prompt fingerprint / quota / retry 兼容 — AC-16
- 失败分类与观测 — AC-09/10/11/12
- A2A 边界 enforcement — AC-15
- CI 本地校验 — AC-14
- free-form 排除 — AC-18

### 未覆盖的边界（已知风险）

- **Provider capability 探测**：spec 未规定 provider 路径上 schema 支持的探测时序（每 call 探测 vs 启动时缓存）；dev plan 阶段必须决定并写明。
- **Validation 失败最大重试次数**：spec 只说「retry + quota 兼容」(FR-013 隐含)，未规定 structured 失败时本地 Pydantic 校验失败是否触发 model call 重试；dev 必须明确「一次 model call + 一次本地 validation = 终态，不 retry validation」。
- **Fallback 内容来源**：FR-007 说「deterministic fallback」但未规定 fallback 是否由 contract 声明 vs 由调用方注入；dev 在 Pydantic contract 层加 `fallback_factory: Callable` 字段时必须 back-fill SC。
- **跨 graph 共享 contract**：当 planner graph 与 interview graph 共享 `QuestionList` contract 时，version bump 流程（spec 未写）需 dev 自定；建议向 main-agent 提 SC 补单。
- **Provider 配额耗尽 (429) 与 schema validation 失败的优先关系**：AC-09 把 quota 单列为 category，但 quota 失败发生在 transport 阶段、schema validation 发生在 response 阶段，两者互斥无歧义，但若 dev 在 quota path 上提前 short-circuit，需验证不会留下 half-validated 状态。

### 模糊词自检

- 已避开：快 / 稳定 / 高效 / 合理 / 差不多 / 正常情况。
- 所有数值（如 6×4=24 fixture / 8 字段 / 8 个 category）均可通过文件枚举或单测断言验证。
- 0/1 差异（AC-17 既有 suite 回归）使用 git diff 测试结果对比，不引入主观判断。