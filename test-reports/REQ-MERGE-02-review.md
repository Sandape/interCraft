# 审查报告 REQ-MERGE-02

## 第 1 次审查

### 判定：FAIL

需求：023 checkpointer 收口（ability_diagnose ARQ retry + 6 个缺失 integration test + lifespan 降级）

审查范围：
- `backend/app/agents/checkpointer.py`（+248 行主改）
- `backend/app/agents/exceptions.py`（新增 16 行）
- `backend/app/agents/graphs/ability_diagnose.py`（inline retry loop）
- `backend/app/agents/graphs/{error_coach,resume_optimize,general_coach}.py`（wrap 调用点核对）
- `backend/app/agents/interview/graph.py`（wrap 调用点核对）
- `backend/app/workers/main.py`（ARQ on_job_start hook）
- `backend/app/main.py`（lifespan preheat 调用）
- `backend/app/core/exceptions.py`（503 handler）
- `backend/tests/unit/test_checkpointer_retry.py`
- `backend/tests/integration/test_{interview,error_coach,resume_optimize,general_coach}_idle_reconnect.py`
- `backend/tests/integration/test_arq_worker_retry.py`
- `backend/tests/integration/test_lifespan_preheat{,_failure}.py`

证据收集方式：直接运行 `preheat()` 抓取运行时 stack trace；读 `langgraph-checkpoint-postgres 1.0.9` 源码核对 `from_conn_string` / `list` 签名；mypy 实跑 5 个变更文件 + 4 个 reference graph 对比 pre-existing 错误。

---

### 问题清单

| # | 严重度 | 维度 | 位置 | 原因 | 修改建议 |
|---|--------|------|------|------|----------|
| 1 | 严重 | 后端 bug | `backend/app/agents/checkpointer.py:128` | `await cp.list(None, limit=1)` 运行时抛 `TypeError: object generator can't be used in 'await' expression`。`AsyncPostgresSaver.list` 在 v1.0.9 是 **sync generator**（内部用 `asyncio.run_coroutine_threadsafe` 桥接），不是 coroutine。实跑 `test_preheat_logs_ok_and_creates_checkpoint_tables` 抓到 `checkpointer.preheat_failed` + TypeError traceback，但测试仍 PASS（因为 `setup()` 已建表，断言只查表存在，不查 success log）。**FR-022「预热成功后 MUST 记录 info 日志 `checkpointer.preheat ok`」永远不被满足**，每次启动都打 `preheat_failed` false alarm。 | 改用 `async for _ in cp.alist(None, limit=1): break`，或直接删除 probe（`get_checkpointer()` 已调 `setup()` 验证连接，probe 多余）。同时强化 `test_preheat_logs_ok_and_creates_checkpoint_tables`：断言 `caplog` 中存在 `checkpointer.preheat ok` event name。 |
| 2 | 严重 | 后端 spec 违反 | `backend/app/agents/checkpointer.py:99` | `PgSaver.from_conn_string(sync_url)` 未传 `pool_config`。核对 v1.0.9 源码：`from_conn_string(cls, conn_string, *, pipeline=False, serde=None)` **不接受 `pool_config` 参数**，内部用 `AsyncConnection.connect(...)` 单连接（非 pool）。`_POOL_CONFIG` dict（min_size/max_size/max_idle/reconnect_timeout/timeout/keepalives_*）是 **死配置**，只在 `preheat()` log 里出现，从未真正生效。**FR-023（显式连接池参数）、FR-024（TCP keepalive）、FR-025（check_connection 回调）三项全部未达成**。`test_pool_config_present_in_module` 只断言 module 属性存在，不验证 pool 实际使用该配置，是误导性测试。 | 改为手动构造 `AsyncConnectionPool(conninfo=sync_url, min_size=1, max_size=10, max_idle=300.0, reconnect_timeout=300.0, timeout=30.0, kwargs={"keepalives":1,"keepalives_idle":30,"keepalives_interval":10,"keepalives_count":5}, open=False)`，再 `AsyncPostgresSaver(pool)` + `await pool.open()` + `await saver.setup()`。并加 integration test 断言 `pool.get_stats()` 反映 min/max_size。 |
| 3 | 严重 | 后端一致性 | `backend/app/agents/checkpointer.py:144-183` + 4 个 graph | `with_checkpointer_retry` 函数定义并 export 到 `__all__`，但 **5 个 graph 没有一个用它**。interview/error_coach/resume_optimize/general_coach 实际用 `retry_graph_op`（同文件 L211）。`with_checkpointer_retry` 仅在 `tests/unit/test_checkpointer_retry.py` 中被 import — **unit test 测的是死代码，生产路径 `retry_graph_op` 零 unit 覆盖**。**FR-001「shared `with_checkpointer_retry` wrapper」字面未达成**（虽然 `retry_graph_op` 功能等价替代）。更严重的是 `contracts/checkpointer-retry.md` 契约规定签名为 `@asynccontextmanager async def with_checkpointer_retry(*, thread_id, operation) -> AsyncIterator[AsyncPostgresSaver]`，实际实现是 `async def with_checkpointer_retry(thread_id, operation, max_retries=2) -> AsyncPostgresSaver`（非 context manager、位置参数、返回值不同）— **契约违反**。 | 二选一：(a) 删 `with_checkpointer_retry` 死代码 + 删对应 unit test，全生产路径统一 `retry_graph_op`，更新 spec/contract；(b) 把 4 个 graph 改回用 `with_checkpointer_retry`（需先把 `retry_graph_op` 的 `build_graph_fn` 重建逻辑搬过来），并修正签名为 `@asynccontextmanager`。推荐 (a)。 |
| 4 | 中等 | 测试质量 | `backend/tests/integration/test_{interview,error_coach,resume_optimize,general_coach}_idle_reconnect.py` | 4 个 graph 的 idle reconnect 测试都只调 `await _force_rebuild()` 重置 singleton，**从不 mock `OperationalError`**。这验证的是「singleton 重置后能重建」，不是「`retry_graph_op` 捕获 OperationalError 后重试」。`retry_graph_op` 的 retry 分支（L240 `_is_reconnectable` 判定 + L250 `checkpointer_reconnect_total.inc()` + L252 `_force_rebuild()`）**完全没被 exercise**。对比 `test_arq_worker_retry.py` 用 `fake_graph.ainvoke = flaky_ainvoke` 正确 mock 了第一次抛错第二次成功 — 那才是 retry 测试的正确姿势。**FR-003「retry 逻辑 MUST 对幂等操作直接重试」无 integration 覆盖**。 | 4 个 idle reconnect 测试各加一个 case：mock `retry_graph_op` 内部 `op(config, *args)` 第一次抛 `OperationalError("connection is closed")`、第二次成功，断言 `checkpointer_reconnect_total` inc 且返回正常 result。 |
| 5 | 中等 | 后端 spec 违反 | `backend/app/agents/graphs/{interview,error_coach,resume_optimize,general_coach}.py` 的 `ainvoke` 调用 | 4 个 graph 的 `ainvoke` 调用（如 `error_coach.py:97 result = await graph.ainvoke(None, config)`、`resume_optimize.py:99`、`general_coach.py:73`、`interview/graph.py:115,134`）**全部裸调，无 retry wrapper**。只有 `aget_state` / `aupdate_state` 走 `retry_graph_op`。**FR-011 明确要求 ability_diagnose 的 `ainvoke` wrap retry**（dev 已用 inline loop 落实），但其他 4 个 graph 的 `ainvoke` 同样会 hit checkpointer，idle 断连发生在 `aupdate_state` 之后、`ainvoke` 之前的窗口内仍会 500。FR-006/007/010/012「submit_answer MUST 调用共享 retry wrapper」字面只 cover 了 `aupdate_state`，没 cover `ainvoke`。 | dev 注释说 `retry_graph_op` 签名 `op(config, *args)` 不匹配 `ainvoke(state, config)`。建议给 `retry_graph_op` 加 `state_first: bool = False` 参数，True 时调用 `op(*args, config)`。lessons-learned 第2轮已识别此 wart，应在 023 内闭合而非遗留。 |
| 6 | 中等 | 后端一致性 | `backend/app/agents/graphs/ability_diagnose.py:75-92` | inline retry loop 与 `retry_graph_op` 语义不一致：(a) **无 backoff sleep**（`retry_graph_op` L251 `await asyncio.sleep(1.0 * (attempt + 1))`，inline loop 无）；(b) **无 warning log**（`retry_graph_op` L243-249 打 `checkpointer.retry_graph_op` event，inline loop 静默）；(c) **metric inc 顺序不同**（inline loop L88 先 inc 后 `_force_rebuild`，`retry_graph_op` L250-252 同序但多了 sleep）。**SC-006「连接池配置在启动日志可见」满足，但 SC-003「`checkpointer_reconnect_total` 可观测」在 ability_diagnose 路径下无对应 log event，排障困难**。 | 把 inline loop 提到 `retry_graph_op` 内（加 `state_first=True` 参数支持 `ainvoke(state, config)`），消除 duplication；或至少补 `logger.warning("checkpointer.retry_graph_op", op="ainvoke", attempt=..., exc_info=True)` + `await asyncio.sleep(1.0 * (attempt + 1))` 对齐 wrapper 行为。 |
| 7 | 中等 | 测试质量 | `backend/tests/integration/test_lifespan_preheat_failure.py` | 4 个测试中 2 个形同虚设：(a) `test_app_starts_when_preheat_fails` L69-73 只调 `create_app()` 构造 FastAPI 实例，**不触发 lifespan**（lifespan 在 `app.run()` / `TestClient.__aenter__` 时才执行），断言仅 `assert app is not None` 永真；(b) `test_preheat_logs_preheat_failed_event_on_failure` L83-94 注释自承「We can't easily inspect structlog records with stdlib caplog」，**未断言任何 log event**，只验证 `preheat()` 不抛。**FR-021「降级为懒加载并记录 warning 日志 `checkpointer.preheat_failed`」无真实测试覆盖**。 | (a) 用 `httpx.AsyncClient(transport=ASGITransport(app))` 或 `TestClient` 真正触发 lifespan，断言 `healthz` 200；(b) 用 `structlog.testing.capture_logs()` context manager 捕获 `checkpointer.preheat_failed` event name 并断言。 |
| 8 | 中等 | 后端类型 | `backend/app/agents/checkpointer.py:128` + `backend/app/workers/main.py:31,38,43` | mypy 实跑新增 **10 errors**（dev 报告「9 errors pre-existing」不准确）。其中 `checkpointer.py:128 Incompatible types in "await" (actual type "Iterator[CheckpointTuple]")` 是 **023 新引入**（与 #1 同源，await sync generator）。`workers/main.py` 3 个 `dict`/`list` type-arg 错误是新加的 `on_job_start`/`on_failure`/`auto_release_stale` 函数（后两个虽 pre-existing 但 dev 新增同款未修）。对比 4 个 reference graph 的 26 个 mypy 错误确认是 pre-existing 同 pattern（override / CompiledStateGraph / ainvoke attr），不算本次回归。 | 修 #1 后 `checkpointer.py:128` 自动消除。`workers/main.py` 新增函数签名改 `dict[str, Any]` / `list[Any]`（或跟进 `auto_release_stale` 同款债，但新增代码不应继承债）。 |
| 9 | 轻微 | 后端安全 | `backend/app/agents/checkpointer.py:189-193` | `_force_rebuild` 用 `except Exception: pass` 静默吞 cleanup 错误。若 `__aexit__` 抛（如 connection 已经断、psycopg 内部状态错乱），生产环境无任何日志可观测，排障困难。 | 改 `except Exception: logger.warning("checkpointer.cleanup_failed", exc_info=True)`。 |
| 10 | 轻微 | 测试稳定性 | `backend/tests/integration/test_general_coach_idle_reconnect.py::test_general_coach_msg2_after_reconnect_preserves_msg1_context` | 该测试单独跑 PASS，但与 `test_arq_worker_retry` + `test_interview_idle_reconnect` + `test_error_coach_idle_reconnect` + `test_resume_optimize_idle_reconnect` + `test_lifespan_preheat*` + `test_checkpointer_retry` 一起跑时**首次复现 `psycopg.OperationalError: the connection is closed`**（重跑又 PASS）。根因是 checkpointer singleton 跨 test 不重置 — `conftest.py` 无 `checkpointer` fixture，`_force_rebuild()` 只在测试内部调，不保证 teardown。**SC-007「并发触发 checkpointer 重连时仅重建 1 次」无测试覆盖**（T011/T094 已 decope）。 | `conftest.py` 加 autouse fixture：每个 test 后 `await _force_rebuild()` + `await close_checkpointer()`，保证 checkpointer singleton 干净。 |

---

### Spec 符合度核对

| FR / SC | 状态 | 证据 |
|---------|------|------|
| FR-001 `with_checkpointer_retry` 共享 wrapper | 字面未达成 | 生产用 `retry_graph_op`，`with_checkpointer_retry` 死代码（#3） |
| FR-002 4 子串匹配 OperationalError | PASS | `_CHECKPOINTER_RECONNECT_PATTERNS` L30-35 正确，`_is_reconnectable` L61-67 正确，unit test 6 case 覆盖 |
| FR-003 aget_state 幂等直接重试 / aupdate_state 先 aget_state 检查 | 部分达成 | `retry_graph_op` 实现了重试，但 aupdate_state 路径未先 aget_state 检查（contract 要求，实际未实现）。集成测试无覆盖（#4） |
| FR-004 `CheckpointerUnavailableError` → 503 | PASS | `exceptions.py` + `core/exceptions.py:130-142` 503 handler 正确，`Retry-After` header 正确 |
| FR-005 `asyncio.Lock` 并发安全 | 部分 | `get_checkpointer` L92 用 `_init_lock` + double-check，但 SC-007 无测试覆盖（T094 decope） |
| FR-006 interview `submit_answer` wrap | 部分 | `aget_state` / `aupdate_state` 已 wrap，`ainvoke` 未 wrap（#5） |
| FR-007 error_coach `submit_answer` / `abort` wrap | 部分 | 同上 |
| FR-010 resume_optimize `confirm` / `abort` wrap | 部分 | 同上 |
| FR-011 ability_diagnose `aget_state` / `ainvoke` wrap | PASS | inline loop 覆盖 ainvoke（#6 但功能正确） |
| FR-012 general_coach `send_message` / `close` wrap | 部分 | 同 FR-006 |
| FR-013 移除本地 retry impl | PASS | grep 无 `_is_checkpointer_alive` / `_rebuild_checkpointer` 残留 |
| FR-020 lifespan 预热 `get_checkpointer` + `setup()` + pool `open()` | 部分 | `get_checkpointer` + `setup()` OK，但无 pool（#2），`open()` 不适用 |
| FR-021 预热失败不阻塞启动 + warning 日志 | 字面达成但语义错 | `preheat()` 确实不抛（catch all），但「失败」是 #1 的 TypeError bug，不是真实 DB 不可达 |
| FR-022 预热成功 log `checkpointer.preheat ok` | **FAIL** | 永远不 emit（#1） |
| FR-023 显式连接池参数 | **FAIL** | `_POOL_CONFIG` 死配置（#2） |
| FR-024 TCP keepalive | **FAIL** | 同上 |
| FR-025 `check_connection` 回调 | **FAIL** | 同上（且 `AsyncConnection.connect` 无此机制） |
| FR-030 不改 API 契约 | PASS | grep 无 route schema 变更 |
| FR-031 不改 graph 业务节点 | PASS | `nodes/` 目录未动 |
| FR-032 不切 sync checkpointer | PASS | 仍用 `AsyncPostgresSaver` |
| FR-033 既有 E2E 零回归 | 未验证 | T092/T096 标 `[ ]` 未跑 |
| FR-034 `checkpointer_reconnect_total` 指标 | PASS | `core/metrics.py:84` 定义，3 处 `inc()` 调用 |
| FR-035 不升级 langgraph 主版本 | PASS | 仍 0.2.x + 1.0.9 |
| SC-001 5 graph idle 60s 后 100% 200 | 未真验证 | 集成测试用 `_force_rebuild()` 模拟，非真 60s idle（#4） |
| SC-002 首请求 ≤ 500ms | 未验证 | T080 标 `[X]` 但无 latency 断言 |
| SC-003 `checkpointer_reconnect_total` 可观测 | 部分 | 指标 inc 正确，但 ability_diagnose 路径无 log（#6） |
| SC-004 代码净减少 | PASS | `interview/graph.py` -191 行（大幅瘦身） |
| SC-005 E2E 零回归 | 未验证 | T092 标 `[ ]` |
| SC-006 启动日志含 pool_config | 字面达成 | `preheat()` L133 log `pool_config=_POOL_CONFIG`，但值是死配置（#2） |
| SC-007 并发仅重建 1 次 | 未验证 | T094 decope |

---

### 总结

本次实现有 **3 个严重问题**直接违反 spec FR：
1. `preheat()` 运行时必崩（TypeError on `cp.list`），FR-022 永远不满足
2. `_POOL_CONFIG` 完全死配置，FR-023/024/025 三项全未达成（library API 不支持）
3. `with_checkpointer_retry` 死代码，unit test 测错函数，FR-001 字面未达成

另有 **5 个中等问题**：integration test 不验证 retry 路径、4 graph 的 `ainvoke` 裸调、ability_diagnose inline loop 与 wrapper 行为不一致、lifespan failure 测试形同虚设、mypy 新增错误未修。

dev 报告「mypy 9 errors pre-existing」不准确 — 实际 10 errors，其中 `checkpointer.py:128` 是 023 新引入（与 #1 同源）。

lessons-learned 第2轮已识别 `retry_graph_op` 签名不匹配 `ainvoke` 的 wart，但未在 023 内闭合（选择 inline loop 绕过），导致 5 个 graph 的 retry 模式分裂为两套（wrapper + inline），SC-004「代码净减少」达成但代价是行为不一致。

**修复优先级**：#1（preheat 崩溃）→ #2（pool 配置）→ #3（死代码清理）→ #5（ainvoke wrap）→ #4/#7（测试补强）→ #6/#8（一致性与类型）→ #9/#10（轻微项）。

---

## 第 2 次审查（重审）

### 判定：FAIL

### 复核方法

独立运行测试 + 实跑 mypy + 实跑 preheat() 抓 structlog + 实证 ASGITransport 是否触发 lifespan（不轻信 dev 报告）。`uv run pytest` 406 passed / 26 skipped；023 专项 40 passed；mypy `checkpointer.py` + `workers/main.py` 0 errors。

### 上次 10 问题逐项复核

| # | 上次问题 | 当前状态 | 证据 |
|---|---------|---------|------|
| 1 | preheat `await cp.list()` TypeError | ✅ 已修复 | `checkpointer.py:167-194` `preheat()` 删 probe，仅调 `get_checkpointer()`（已含 `setup()` + `pool.open(wait=True)`）。`test_preheat_logs_ok_and_creates_checkpoint_tables` 用 `structlog.testing.capture_logs()` 真断言 `checkpointer.preheat ok` event（不是只查表存在）。实跑 preheat() 抓到 ok event。 |
| 2 | `_POOL_CONFIG` 死配置 | ✅ 已修复 | `checkpointer.py:126-146` 手动构造 `AsyncConnectionPool(conninfo, min_size, max_size, max_idle, reconnect_timeout, timeout, kwargs={keepalives...}, check=_check_connection, open=False)` + `await pool.open(wait=True)` + `AsyncPostgresSaver(pool)` + `await saver.setup()`。`from_conn_string` grep 仅余注释，无生产调用。`test_pool_config_reflects_in_pool_stats` 调 `pool.get_stats()` 真断言 `pool_min==1` / `pool_max==10` / `pool._check is not None`。 |
| 3 | `with_checkpointer_retry` 死代码 | ✅ 已修复 | grep `with_checkpointer_retry` in `backend/app/` 0 命中。`__all__` 已移除。`tests/unit/test_checkpointer_retry.py` 删 `TestWithCheckpointerRetry`，新增 `TestRetryGraphOpAgetState` / `AupdateState` / `AinvokeStateFirst` 3 类 9 case 覆盖生产路径。`contracts/checkpointer-retry.md` 更新为 `retry_graph_op` 单一生产路径 + state_first 语义。`tasks.md` T014 注明「originally specified with_checkpointer_retry was dead code, removed in round-1 fix-up」。 |
| 4 | integration test 不验证 retry 路径 | ✅ 已修复 | 4 个 idle reconnect 测试各加 `*_retries_on_operational_error` case：mock `patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph))` + `flaky_ainvoke` 第一次抛 `RuntimeError("connection is closed")` 第二次成功；断言 `call_count == 2` + `checkpointer_reconnect_total._value.get()` delta > 0。mock 注入位置正确（build_graph 返回 fake_graph，retry_graph_op 内部 `op = getattr(graph, op_name)` 拿到 fake_graph.ainvoke）。原 `_force_rebuild` case 全部保留。 |
| 5 | 4 graph `ainvoke` 裸调 | ✅ 已修复 | `retry_graph_op` 加 `state_first: bool = False` 参数（L232），True 时 `op(*args, config, **kwargs)` 匹配 `ainvoke(state, config)`。5 个 graph 共 6 处 ainvoke 全部 wrap：`error_coach.py:96,123` / `resume_optimize.py:98` / `general_coach.py:72` / `interview/graph.py:114,134` / `ability_diagnose.py:62`。注：3 个 graph 的 `start()` 方法仍裸调 `graph.ainvoke`（非 wrap），但 start 是首调用无 prior state，spec FR-006/007/010/012 仅要求 submit_answer/confirm/send_message wrap，不要求 start。 |
| 6 | ability_diagnose inline loop | ✅ 已修复 | `ability_diagnose.py:62-68` 删 inline `for attempt in range` loop，改用 `retry_graph_op(self.build_graph, config, "ainvoke", initial_state, state_first=True)`。grep `for attempt in range` in `backend/app/agents/graphs/` 0 命中（仅 `checkpointer.py:258` retry_graph_op 自身 + `llm_client.py` 无关）。5 graph retry 模式统一为单一 wrapper。 |
| 7 | lifespan test 形同虚设 | ⚠️ 部分修复 | **part (b) FIXED**：`test_preheat_logs_preheat_failed_event_on_failure` 用 `structlog.testing.capture_logs()` 真断言 `checkpointer.preheat_failed` event name + `log_level == "warning"`。**part (a) NOT FIXED**：`test_app_starts_when_preheat_fails` 用 `httpx.AsyncClient(transport=ASGITransport(app))`，但 **ASGITransport 不触发 FastAPI lifespan**。实证：mock `checkpointer.preheat` 后用 ASGITransport 发 GET /healthz，`preheat_called == 0`（lifespan 未执行）；同样 mock 用 `fastapi.testclient.TestClient` 则 `preheat_called == 1`（lifespan 执行）。dev 报告「真触发 lifespan」与 test docstring「triggers the FastAPI lifespan on context enter」均与事实不符。`patch.object(checkpointer, "get_checkpointer", side_effect=RuntimeError(...))` 是死 mock — 永不被调用。若有人从 `main.py` 删 `await checkpointer_preheat()` 行，此测试仍 PASS，零回归保护。 |
| 8 | mypy 新增错误 | ✅ 已修复 | `uv run mypy app/agents/checkpointer.py app/workers/main.py` 0 errors（await sync generator 自动消除；workers/main.py `dict[str, Any]` / `list[Any]` 已加 type-arg）。5 graph 文件余 17 errors 全是 pre-existing 同款（override / CompiledStateGraph / ainvoke attr / Returning Any / Literal / add_node overload）— 与 round-1 reviewer 确认的 4 reference graph 26 errors 同 pattern，非本次回归。`ability_diagnose.py:62` 新增 `Returning Any` 是 retry_graph_op 返回 Any 所致，与 error_coach.py:108 / resume_optimize.py:99 / general_coach.py:73 同款。 |
| 9 | cleanup log 静默吞 | ✅ 已修复 | `checkpointer.py:161` (`close_checkpointer`) + `checkpointer.py:209` (`_force_rebuild`) 均改为 `logger.warning("checkpointer.cleanup_failed", exc_info=True)`。grep `except Exception: pass` in checkpointer.py 0 命中。 |
| 10 | conftest singleton 不重置 | ✅ 已修复 | `conftest.py:98-105` 加 autouse async fixture `_reset_checkpointer_singleton`，每个 test 前后 `await _force_rebuild()`。`_force_rebuild` 在 `_pool=None` 时是 no-op，对不依赖 checkpointer 的 test 零成本。跨 test 状态泄漏已闭合。 |

### 新发现问题

| # | 严重度 | 维度 | 位置 | 原因 | 修改建议 |
|---|--------|------|------|------|----------|
| 11 | 中等 | 测试质量 | `backend/tests/integration/test_lifespan_preheat_failure.py:76-99` | `test_app_starts_when_preheat_fails` 用 `httpx.AsyncClient(transport=ASGITransport(app))`，但 ASGITransport **不触发 FastAPI lifespan**。实证：mock `checkpointer.preheat` 后 ASGITransport 路径 `preheat_called == 0`，而 `TestClient` 路径 `preheat_called == 1`。test docstring「triggers the FastAPI lifespan on context enter」与 dev 报告「真触发 lifespan」均与事实不符。`patch.object(checkpointer, "get_checkpointer", side_effect=RuntimeError(...))` 是死 mock — 永不被调用。若有人从 `main.py:49` 删 `await checkpointer_preheat()` 行，此测试仍 PASS，零回归保护。**FR-021「预热失败 MUST 不阻塞服务启动」的集成级验证缺失**（unit 级由 `test_preheat_does_not_raise_when_get_checkpointer_fails` + `test_preheat_logs_preheat_failed_event_on_failure` 覆盖，但 lifespan → preheat() 接线无任何测试保护）。 | 二选一：(a) 改用 `from fastapi.testclient import TestClient` + `with TestClient(app) as client: r = client.get("/healthz")`（同步，触发 lifespan）；(b) 手动调 lifespan context manager：`from app.main import lifespan` + `async with lifespan(app):` 包裹 ASGITransport 请求。推荐 (a) 更简洁。 |

### 上次问题状态汇总

- ✅ 已修复：#1, #2, #3, #4, #5, #6, #8, #9, #10（9 项）
- ⚠️ 部分修复：#7（part b yes / part a no）
- ❌ 未修复：无

### 总结

9.5/10 问题已修。3 个严重问题（preheat TypeError / pool 死配置 / with_checkpointer_retry 死代码）全部闭合，FR-022/023/024/025 真达成。406 tests passed 无回归。mypy 023 新引入错误清零。

**唯一未闭合**：#7 part (a) `test_app_starts_when_preheat_fails` 用 ASGITransport 不触发 lifespan，dev 报告「真触发 lifespan」与事实不符。该测试：
- PASS 但无效 — mock `get_checkpointer` 是死代码，永不被调用
- 不保护回归 — 删 `main.py:49` `await checkpointer_preheat()` 行仍 PASS
- docstring 与 dev 报告均与事实不符

修复成本极低（替换为 `TestClient` 或手动调 `lifespan(app)` context manager，3-5 行改动）。建议修完后第 3 轮重审只验 #7 part (a)。

### 修复优先级

#7 part (a)（lifespan 真触发）— 唯一阻塞项。

---

## 第 3 次审查（重审）

### 判定：PASS

### 复核方法

独立运行 4 个 lifespan test + 全量 406 tests + mypy + 反向验证（临时注释 `main.py:49` → 测试 FAIL → 恢复 → 测试 PASS）。不轻信 dev 报告。

### 上次唯一阻塞项 #7 part (a) 复核

| 检查点 | 期望 | 实测 | 状态 |
|--------|------|------|------|
| 用 `async with lifespan(app):` 包裹请求 | 是 | `test_lifespan_preheat_failure.py:124` `async with lifespan(app):` 真手动进入 lifespan context manager | ✅ |
| mock preheat 用 AsyncMock（不是 MagicMock） | 是 | `:119` `mock_preheat = AsyncMock()`（无 side_effect） | ✅ |
| 断言 `call_count >= 1` | 是 | `:134` `assert mock_preheat.call_count >= 1` | ✅ |
| 断言 healthz 200 | 是 | `:128` `assert r.status_code == 200` + `:130` body status check | ✅ |
| 反向验证有保护力 | 注释 `main.py:49` → 测试 FAIL | 实测：注释后 `call_count == 0`，`AssertionError: lifespan must call preheat; if this fails, main.py lost the preheat wiring`；恢复后 PASS | ✅ |
| git diff 无残留 | main.py diff 与初始 dirty M 状态一致 | `git diff backend/app/main.py` 显示 +5 行（023 pre-existing init commit，非本轮新增）；无 reverse-test 残留 | ✅ |

### AsyncMock vs MagicMock 决策合理性

| 检查点 | 实测 | 状态 |
|--------|------|------|
| `main.py:49` 是裸调（无 try/except 包裹 preheat） | `main.py:46-49` 仅 `from app.agents.checkpointer import preheat as checkpointer_preheat` + `await checkpointer_preheat()`，外层无 try/except | ✅ |
| `preheat()` 内部 catch 所有异常 | `checkpointer.py:180-194` `try: await get_checkpointer() ... except Exception: logger.warning("checkpointer.preheat_failed", ...)` — preheat 永不 raise | ✅ |
| 若 mock 用 `MagicMock(side_effect=Exception)` 会绕过 preheat 内部 try/except | 是 — patch.object 替换的是 `checkpointer.preheat` 函数本身，preheat 内部 try/except 不再执行；`side_effect=Exception` 直接 raise 穿透 lifespan → app 无法启动 → healthz 200 不可达 | ✅ |
| dev 用 AsyncMock（无 side_effect）的理由成立 | 是 — AsyncMock 默认返回 MagicMock（await 后得 AsyncMock），preheat 不抛，lifespan 完成 startup，healthz 可达；call_count 直接证明 lifespan 触发了 preheat | ✅ |
| preheat 内部失败降级路径由 unit test 覆盖 | `test_preheat_does_not_raise_when_get_checkpointer_fails`（patch get_checkpointer side_effect RuntimeError → 断言 preheat 不抛 + log preheat_failed）+ `test_preheat_logs_preheat_failed_event_on_failure`（同款 + capture_logs 断言 warning level）— 两条路径互补 | ✅ |

### 方案2 vs 方案1 选择合理性

| 检查点 | 实测 | 状态 |
|--------|------|------|
| conftest `_reset_checkpointer_singleton` 是 async autouse fixture | `conftest.py:98-105` `@pytest.fixture(autouse=True) async def _reset_checkpointer_singleton(request):` — async | ✅ |
| sync TestClient 与 async autouse fixture 不兼容 | 是 — sync TestClient 用自己的 event loop，无法 await async fixture teardown；dev 选方案2 避开此冲突 | ✅ |
| 方案2（手动 lifespan context）等价于 TestClient 的 lifespan 触发 | 反向验证证明：手动 `async with lifespan(app):` 让 `await checkpointer_preheat()` 真执行，`call_count == 1`（注释后 `call_count == 0`）；与 TestClient 路径行为等价 | ✅ |

### docstring 偏差文档化

`test_lifespan_preheat_failure.py:102-112` docstring 第 4 段「Deviation from task brief」显式说明：brief 建议 `MagicMock(side_effect=Exception)`，但实际用 AsyncMock，理由是 main.py 没包 try/except + preheat 内部已 catch all。偏差已文档化，未来维护者能理解决策。

### lessons-learned 第5轮条目

`lessons-learned.md:122-128` 新增「`httpx.ASGITransport` 不触发 FastAPI lifespan 事件」条目，详细记录：
- 问题（ASGITransport 只转发 HTTP 不跑 lifespan）
- 修复（手动 `async with lifespan(app):`）
- 适用场景（任何测 FastAPI lifespan startup 的集成测试）
- 避免（3 条：不要假设 ASGITransport 触发 lifespan / 不要用 side_effect=Exception mock preheat / capture_logs 不跨 lifespan）

### 零回归验证

| 测试集 | 上次 baseline | 本次实测 | 状态 |
|--------|--------------|----------|------|
| lifespan 专项（4 test） | 4/4 PASS | 4/4 PASS | ✅ |
| 023 专项（40 test） | 40/40 PASS | 40/40 PASS | ✅ |
| 全量 backend | 406 passed / 26 skipped | 406 passed / 26 skipped（246s） | ✅ |
| mypy `checkpointer.py` + `workers/main.py` | 0 errors | 0 errors（2 source files） | ✅ |
| grep `with_checkpointer_retry` in `backend/app/` | 0 命中 | 0 命中（#3 死代码仍清除） | ✅ |

### 其他 9.5 问题仍 PASS（无回归）

| # | 问题 | 本次状态 |
|---|------|---------|
| 1 | preheat structlog 断言 | ✅ `test_preheat_logs_ok_and_creates_checkpoint_tables` 仍用 capture_logs 断言 `checkpointer.preheat ok` event |
| 2 | pool.get_stats 断言 | ✅ `test_pool_config_reflects_in_pool_stats` 仍用 `pool.get_stats()["pool_min"]` / `pool._check` 真断言 |
| 3 | with_checkpointer_retry 死代码清除 | ✅ grep 0 命中 |
| 4 | 4 idle test retry mock | ✅ 4 个 `*_retries_on_operational_error` case 仍 PASS |
| 5 | 4 graph ainvoke wrap state_first | ✅ 5 graph 共 6 处 ainvoke 仍 wrap（含 ability_diagnose） |
| 6 | ability_diagnose inline loop 消除 | ✅ grep `for attempt in range` in `backend/app/agents/graphs/` 0 命中 |
| 7 part (b) | capture_logs 断言 | ✅ `test_preheat_logs_preheat_failed_event_on_failure` 仍断言 `log_level == "warning"` |
| 8 | mypy 023 清零 | ✅ 0 errors |
| 9 | cleanup log | ✅ `checkpointer.py:161,209` `logger.warning("checkpointer.cleanup_failed", exc_info=True)` |
| 10 | conftest autouse singleton reset | ✅ `conftest.py:98-105` autouse async fixture 仍存在 |

### git diff 范围确认

| 文件 | 状态 | 改动 | 评估 |
|------|------|------|------|
| `backend/tests/integration/test_lifespan_preheat_failure.py` | AM | +67/-32 | 本轮新增 #7 part (a) 修复 |
| `lessons-learned.md` | M | +10 | 本轮新增第5轮条目 |
| `backend/app/main.py` | M | +5 | 023 init commit pre-existing（last commit `0282157 init`），本轮反向验证已恢复无残留 |

`backend/app/main.py` 在会话开始时已是 dirty M 状态（023 pre-existing），本轮 review fix-up **未新增**改动到 main.py。反向验证临时注释 + 恢复后 `git diff` 与会话开始时一致。

### 总结

#7 part (a) 真修验证完成。lifespan 真触发（手动 context manager）+ 反向验证有保护力（注释后 FAIL）+ AsyncMock 决策合理（preheat 内部 try/except 使 side_effect 会绕过）+ 方案2 选择合理（async fixture 与 sync TestClient 不兼容）+ docstring 偏差已文档化 + lessons-learned 第5轮条目质量高。

10/10 问题全部闭合。406 tests passed / 26 skipped 零回归。mypy 023 清零。

**判定：PASS**

