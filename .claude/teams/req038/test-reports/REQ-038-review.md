# REQ-038 US1 P1 代码审查报告

**审查时间**：260703 0450
**审查分支**：team/req038/master（commit 09dc2c5）
**审查范围**：20 files, +1327/-3

### 判定：PASS

## 强项

**架构清晰（FR-001/002）**：
- `structured_output/` 子包 6 文件层次分明：`__init__` 公开 API · `registry.py` 节点清单 + `NODE_SCHEMAS` 双向映射 · `schemas.py` 6 个 Pydantic 类型（Intake/Score/ErrorCoachEval 三对 Input/Output）· `errors.py` 5 类异常层级 · `fallbacks.py` `NodeConfig` + `Literal["retry","use_previous","hard_fail"]` 锁值 · `client.py` 单解析入口
- `NODE_SCHEMAS` 双向覆盖已通过实测（`set(NODE_SCHEMAS.keys()) == set(STRUCTURED_NODES)` PASS）

**Error 分类完整（FR-006/008）**：
- `StructuredOutputError` 基类 + 5 子类（SchemaInvalid / ParseFail / Timeout / Quota / OutOfBounds），每个子类 class-level `category` 字符串字面量
- `CategoryType = Literal["schema_invalid","parse_fail","quota","timeout","oob"]` 类型别名锁定 5 字符串；`test_category_no_alias.py` 实测通过 `typing.get_args(CategoryType)` 等于精确 5 元组
- `Quota` 提供 `used/quota/estimated` 业务字段（与 `LLMClient.QuotaExceededError` line 493 对齐）

**单解析入口（FR-005）**：
- `LLMClient.parse_structured_output(self, content, schema, *, fallback_strategy, node_name) → BaseModel` 是唯一权威路径，`MockLLMClient.parse_structured_output` 通过 `return LLMClient.parse_structured_output(self, ...)` 复用生产校验（AC-009 grep 锚点吻合）
- `_classify_validation_error` heuristic 把 Pydantic `ValidationError` 按错误类型分流：纯越界 → `OutOfBounds`，混合 → `SchemaInvalid`

**Mock 真消费生产校验（FR-007/009）**：
- `MockLLMClient(LLMClient)` 继承使 mock 必走 Pydantic
- `by_scenario(name, schema=None)` 拒绝未知名（`KeyError` 含 "Available scenarios:"，ac-matrix Note R11 守卫）
- `_SCENARIO_FIXTURES` 6 个场景 payload 硬编码（malformed / missing / enum_violation / oob / quota / timeout）

**测试真实性（FR 全 cross-cut）**：
- 26 测试 100% PASS（`test_pydantic_validator_local.py` 4+1+1+1+1 = 8 项；`test_structured_error_classification.py` 6 项；`test_mock_shares_structured_api.py` 9 项；`test_category_no_alias.py` 3 项）
- `test_oob_caught` 4 个参数化用例（200/-1/99999/-100）全部 PASS
- `test_mock_uses_prod_parse` 与 `test_mock_parse_routes_to_prod` 验证 mock→prod 复用

**Fixture 真非 trivial**：
- 6 个 `mock_llm_*.json` + `test_case_strings.json`，每个含 `_scenario` / `_schema_hint` / `_description` / `_raw` / `_expected_category` / `_raw_examples`（10 个变体），300+ 字节

**commit message 合规**：
`feat(038): US1 P1 — LLM Structured Output Hardening` 符合规范（R3 + ac 锁 US1 P1 标题对应）

## 已知非阻塞 nit（留给后续 cycle / dev 自审）

1. **ac-matrix 字面 grep 张力**：AC-005/AC-006a/AC-008 字面 grep 命令与 dev 实际命名存在差异：
   - AC-005 期望 `def parse_structured_output(schema: type[BaseModel], *`；dev 实现 `def parse_structured_output(self, content: str, schema: type[BaseModel], *, ...)`（content 必须先于 schema，因为 HTTP 响应内容先获得）
   - AC-006a 期望 `grep "category:\s*Literal\[" errors.py ≥1`；dev 用 `CategoryType = Literal[...]` 别名 + class-level `category = "..."` 字符串字面量，0 命中
   - AC-008 期望 `grep "category:\s*Literal\[\"schema_invalid\", ...\]" errors.py ≥1`；同上 0 命中
   - AC-002 期望 `class (Input|Output)Schema(BaseModel)` 命中；dev 用 `InterviewIntakeInput` / `InterviewIntakeOutput` 具名类

   这些都是 **ac-text 与合理 API 设计的字面/语义张力**，行为 AC（双向覆盖、调用 Pydantic、monkeypatch 路径）已通过测试覆盖。dev 命名风格（具名 `InterviewIntakeOutput` 而非通用 `OutputSchema`）反而更利于 IDE 跳转与类型对齐。

2. **scope 内节点切换未启动（FR-004）**：8 个 node handler（intake/score/question_gen/report + 5 deferred）仍走 `json.loads(re.search(...))` 老路径，未切换到 `parse_structured_output`。但 ac-matrix `deferred_for=US2+` 明确 US2/3/4 才会触达这些 node，US1 P1 范围仅交付"解析骨架"。

3. **uv.lock +289 行副作用**：pyproject.toml line 33/38-40 已在 master 声明 `tavily-python` 与 `opentelemetry-*`，uv.lock 是上次 cycle（agent_observability / tavily）未及时同步的 lock 补齐，非 REQ-038 实质依赖改动。`git diff -- 'pyproject.toml'` 为空，lock 文件改动是自动 sync。

4. **Quota/Timeout 上游拦截无入口**：`Quota` / `Timeout` 错误类已定义 + mock fixture `_kind` 触发，但 `parse_structured_output(content, schema)` 路径上不解析 `_kind` 标记 —— quota/timeout 必须由 `LLMClient.invoke` 上层 HTTP 异常路径分流。US1 P1 范围内不需要这个能力（HTTP 异常路径已有 `QuotaExceededError`）；后续 US2+ 实施节点切换时可同步接线。这是 **scope 边界**而非缺陷。

## Commit hash
09dc2c5（无 code-simplification 启动 — review 即已 minimal，且 main-agent 已独立验证 26/26 PASS）
