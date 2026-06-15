# M22 · 审计 / 可观测 / 对账

> 状态: draft · 所属领域: F · 优先级: P0
> 引用原文档: §11.3(可观测)、§17.2 / §17.3(双源对账)、§17.4(重连重放)

## 1. 需求摘要

实现生产环境**三件套**:① 审计日志(所有敏感读写 / 数据生命周期事件 / 权限变更)、② 可观测(OpenTelemetry trace + Prometheus 指标 + LangSmith **可选**,参见 [A17])、③ 双源对账(ai_messages ↔ langgraph_checkpoints 每日校准,断线重连 token 重放见 [A4])。本模块是 MVP 的「P0 必修」,无审计意味着无法过合规,无双源对账意味着 LangGraph 状态与业务消息一旦飘移就再也对不上。

## 2. 验收标准

### 审计日志
- [ ] `audit_logs` 表记录所有敏感字段读写(参见 [A16]: `request_id` / `changed_fields` / `endpoint`)
- [ ] 写入场景:登录 / 登出 / 失败登录;PII 字段读写;权限变更;数据生命周期(软删 / 硬删 / 匿名化 / 注销);导出 / 导入
- [ ] 不写:高频只读查询(列表 / 详情)、流式 token 推送
- [ ] 异步批量写入(批大小 100,刷新间隔 1s)避免阻塞业务
- [ ] 保留期:2 年(合规要求)
- [ ] 提供 `GET /api/v1/admin/audit-logs?actor_id=&action=&from=&to=` 查询端点(仅 super_admin)

### 可观测
- [ ] OpenTelemetry trace:所有 HTTP / WS / ARQ 任务 / LLM 调用 串联
- [ ] Prometheus 指标:HTTP 延迟分位(p50/p95/p99) / 错误率 / LLM token 用量 / 锁等待 / 队列长度 / 活跃 thread 数
- [ ] LangSmith 接入:由 `LANGSMITH_API_KEY` 环境变量控制,**默认关闭**(参见 [A17] 合规)
- [ ] Grafana dashboard:`/d/app-overview` 至少 4 个面板(请求 / 错误 / LLM / 锁)
- [ ] 告警规则:错误率 > 5% 持续 5min / 队列长度 > 1k 持续 10min / 锁等待 P99 > 30s

### 双源对账
- [ ] 每日 02:00 ARQ 任务 `reconcile_dual_source(date)`:对账前一天所有 `ai_messages` ↔ `langgraph_checkpoints`
- [ ] 不一致分类:`MISSING_IN_CKPT`(消息存在但 checkpoint 没记录)/ `MISSING_IN_MSG`(checkpoint 有但消息缺失)/ `DIVERGENT`(都在但内容不同)
- [ ] 不一致率 > 0.1% 时:写入 `audit_logs(action='reconcile.anomaly', severity='warn')` + 触发告警
- [ ] 不一致 > 1% 时:severity='critical' + 自动生成 GitHub issue(通过 webhook)
- [ ] 单元测试:人造不一致 fixture → 验证任务输出分类正确
- [ ] 集成测试:对账覆盖率 ≥ 99.9%(允许 0.1% 误差)

### 重连重放(参见 [A4])
- [ ] WS 重连时客户端携带 `last_seen_checkpoint_id`
- [ ] 服务端从该点之后开始重放 `token.delta` 事件
- [ ] 节点中途断线:重放从下个节点开始(丢弃断线节点的 partial tokens)
- [ ] 前端配合:断线时丢弃当前节点的 `token.delta` 直至 `node.started` 事件

## 3. 依赖与被依赖关系

**强依赖**: M02(ORM)、M14(双源数据写入位置)、M03(Redis 用作指标缓存)
**弱依赖**: 所有其他模块(均会触发审计 / 指标)
**被以下模块依赖**: M23(前端读取 Grafana 链接 / 上报前端错误)
**外部依赖**: Prometheus + Grafana(自部署或托管);OpenTelemetry Collector;LangSmith(可选);告警通道(Slack / PagerDuty / 企业微信)

## 4. 数据模型

**新表**:
```sql
-- 审计日志(2 年保留)
audit_logs (
  id bigserial PRIMARY KEY,
  request_id uuid,  -- 与 trace 关联
  actor_id uuid,  -- 触发者(user_id / admin_id / system / 'cron:{job_name}')
  actor_type text NOT NULL DEFAULT 'user',  -- user | admin | system | service
  action text NOT NULL,  -- auth.login | data.read | data.write | data.exported | data.hard_delete | ...
  target_type text,  -- users | resume_branches | ai_messages | ...
  target_id uuid,
  changed_fields jsonb,  -- 读取时为 null,写入时为 {field: {old, new}}
  endpoint text,  -- /api/v1/agents/interview/{id}/messages
  ip inet,
  ua text,
  severity text NOT NULL DEFAULT 'info',  -- info | warn | error | critical
  metadata jsonb,  -- 额外上下文(LLM 评分 / 锁 ID / 等)
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_actor_time ON audit_logs (actor_id, occurred_at DESC);
CREATE INDEX idx_audit_target ON audit_logs (target_type, target_id);
CREATE INDEX idx_audit_action_time ON audit_logs (action, occurred_at DESC);

-- 对账结果
reconciliation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_date date NOT NULL,
  started_at timestamptz NOT NULL,
  completed_at timestamptz,
  status text NOT NULL,  -- running | success | failed
  total_checkpoints int,
  total_messages int,
  missing_in_ckpt int DEFAULT 0,
  missing_in_msg int DEFAULT 0,
  divergent int DEFAULT 0,
  anomaly_count int DEFAULT 0,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 对账异常明细(供排查)
reconciliation_anomalies (
  id bigserial PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES reconciliation_runs(id),
  anomaly_type text NOT NULL,  -- missing_in_ckpt | missing_in_msg | divergent
  thread_id text NOT NULL,
  checkpoint_id text,
  message_id uuid,
  details jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 死信队列(异步任务失败 3 次后)
dead_letter (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_name text NOT NULL,
  args jsonb,
  last_error text,
  attempt_count int,
  first_failed_at timestamptz NOT NULL,
  last_failed_at timestamptz NOT NULL,
  resolved_at timestamptz,
  resolution_notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

**Prometheus 指标清单**(命名规范 `app_<domain>_<metric>_<unit>_<suffix>`):
```
app_http_request_duration_seconds_bucket{path, method, status}
app_http_requests_total{path, method, status}
app_llm_tokens_total{model, type}  # type: input | output
app_llm_request_duration_seconds_bucket{model}
app_lock_acquire_duration_seconds_bucket{resource_type}
app_lock_active_count{resource_type}
app_queue_pending_jobs{queue_name}
app_agent_active_threads{graph_name}
app_agent_node_duration_seconds_bucket{graph, node}
app_ai_messages_written_total
app_checkpoints_written_total
app_reconciliation_anomaly_total{type}
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/admin/audit-logs` | 查询审计日志(过滤 actor/action/target/time) |
| GET | `/api/v1/admin/audit-logs/export` | 导出审计日志(CSV / JSONL,带签名 URL) |
| GET | `/api/v1/admin/reconciliation/runs` | 列出对账运行历史 |
| GET | `/api/v1/admin/reconciliation/runs/{run_id}/anomalies` | 查询异常明细 |
| POST | `/api/v1/admin/dead-letter/{id}/resolve` | 标记死信已处理 |

**Prometheus 端点**:`GET /metrics`(无认证,K8s 内网访问)

**OTel Exporter**: 通过 `OTEL_EXPORPORTER_OTLP_ENDPOINT` 环境变量配置,默认指向 `otel-collector:4317`。

**WebSocket**: 告警事件 `sync.{user_id}/admin.alert`(仅 super_admin 收到)。

**ARQ 任务**:
```python
@worker_task
async def reconcile_dual_source(ctx, target_date: date):
    """每日 02:00 跑:对账前一天 ai_messages ↔ langgraph_checkpoints"""

@worker_task
async def flush_audit_buffer(ctx, batch: list[dict]):
    """每 1s 触发(由 scheduler 调度):把内存 buffer 批量写入 audit_logs"""

@worker_task
async def archive_old_audit_logs(ctx, retention_days: int = 730):
    """每天 03:30 跑:2 年前的审计日志归档到冷存(S3)"""
```

## 6. 关键设计点

- **审计写入策略**:
  - **同步关键路径**:登录、权限变更、注销、数据导出 → 同步写(失败阻塞业务并告警)
  - **异步批量写入**:其他场景 → 进内存 ringbuffer,定时 flush(降低业务延迟)
  - **永不失败**:批量写入用 retry-once + 失败落盘到本地文件,避免审计写入失败导致业务故障
- **PII 字段识别**:`email` / `phone` / `id_card_no` / `salary` / `birth_date` 等字段在 ORM 层面标记,任何读写自动审计
- **`changed_fields` 格式**:
  ```json
  {
    "email": {"old": "a@x.com", "new": "b@x.com"},
    "salary": {"old": "encrypted:xxx", "new": "encrypted:yyy"}
  }
  ```
- **可观测采样**:`OTEL_TRACES_SAMPLER=parentbased_traceidratio` + `OTEL_TRACES_SAMPLER_ARG=0.1`(10% 采样,LMM 调用 100%)
- **LLM 调用追踪**:每次 LLM 调用记录 `{model, prompt_tokens, completion_tokens, latency, prompt_hash}`(prompt_hash 用于查重 / 成本归因,**不存原文**)
- **对账算法**:
  1. 查 `langgraph_checkpoints` 中 `thread_id` ∈ 前一天活跃 thread 列表
  2. 对每个 thread:取最新 checkpoint 的 `channel_values.messages` → 校验所有 message id 都在 `ai_messages` 中
  3. 反向:`ai_messages` 中前一天写入的 → 校验对应 thread 的 checkpoint 包含
  4. 字段级 diff(`content` 字段):hash 对比(内容相同但 hash 不同 → divergent)
- **死信处理**:ARQ 任务重试 3 次后(参见 M18),自动写入 `dead_letter` 表 + 告警
- **Grafana 链接**:`GET /api/v1/admin/grafana-links` 返回各 dashboard URL(用环境变量配置 base URL)
- **LangSmith 可选**(参见 [A17]):通过 `LANGSMITH_TRACING=true` 启用,默认 `false`;启用时所有 LLM 调用额外上报到 LangSmith
- **__version__ = "1.0.0"**

## 7. 待澄清

- **[A4]** 节点中途断线 token 重放策略:本模块采用「节点级粒度重放」,需前端在 WS 客户端实现「断线时丢弃 partial tokens 直至 node.started」(M23 配合)
- **[A16]** `audit_logs` 字段粒度:本模块已补 `request_id` / `changed_fields` / `endpoint`
- **[A17]** LangSmith 接入:由环境变量控制,合规评审通过后才默认开启
- 审计日志的访问权限模型:仅 super_admin?还是机构 admin + 行级隔离(只看到自己机构的)?需 M04 RBAC 配合
- 告警通道:Slack / 企业微信 / 钉钉 / PagerDuty,选择决定 oncall 流程
- 对账异常修复 SOP:发现 anomaly 后是自动 reconcile 修复 / 人工 review / 触发 LangGraph 重跑,需 SRE 制定

## 8. 实现提示

- 文件:
  - `backend/app/core/audit.py`(`audit_service.log / log_async` + ringbuffer)
  - `backend/app/core/telemetry.py`(OTel 初始化 + Prometheus 导出器)
  - `backend/app/core/metrics.py`(指标注册表)
  - `backend/app/services/reconciliation_service.py`
  - `backend/app/workers/tasks/reconciliation.py` / `audit_flush.py`
  - `backend/app/api/v1/admin/audit.py` / `reconciliation.py` / `dead_letter.py`
  - `infra/grafana/dashboards/*.json`
  - `infra/otel-collector-config.yaml`
  - `infra/alerts/*.yaml`(Prometheus alert rules)
- 复用: M02 BaseRepository;M14 双源写入 hooks
- 依赖库:`opentelemetry-api` / `opentelemetry-sdk` / `opentelemetry-exporter-otlp` / `prometheus-client` / `langsmith`(可选)
- 与 mockData 关系:无(mockData 是新账号示例,审计 / 指标 / 对账不涉及)
- 测试:`tests/integration/reconciliation/` 用人造 fixture 验证分类
