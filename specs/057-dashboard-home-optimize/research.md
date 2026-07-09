# Research: REQ-057 求职训练指挥台

**Date**: 2026-07-10  
**Spec**: [spec.md](./spec.md)

## R1 — 今日面试数据源与过滤位置

**Decision**: 权威字段为 `jobs.interview_time`（TIMESTAMPTZ）。在 `dashboard-summary` 内按 `tz`（默认 `Asia/Shanghai`）将 `interview_time` 换算为本地日历日，过滤 `local_date`；前端今日列表只消费 summary，不再用 `GET /tasks`。

**Rationale**: 现有 `GET /jobs` 仅支持 `status`/`branch_id`/`limit`，无日期过滤；通用 tasks 与「今日面试」业务定义不符。服务端过滤避免拉满 50 条再客户端猜时区。

**Alternatives considered**:
- 仅前端 `useJobs` + 本地日过滤 — 可行作过渡，但重复请求多、时区易漂，拒绝作为终态。
- 扩展 `GET /jobs?interview_on=` — 有用，可作后续增强；本 REQ 以 summary 为主入口，避免 Dashboard 再 fan-out。

## R2 — 简历区数据源

**Decision**: 使用 `GET /api/v1/v2/resumes`（`resume_kind`: root/derived/standard）。Dashboard 与「是否有简历」一律 `useResumeV2List` / summary `resume_summaries`；`useResumeBranches` 保持退役 stub，不再被 Dashboard 引用。

**Rationale**: 036/055 已退役 v1 分支；当前 stub 导致空列表与错误 CTA。

**Alternatives considered**: 继续兼容分支 UI 字段（match_score 等）— 与根/派生模型不符，拒绝。

## R3 — 建议区形态

**Decision**: 方案 A — 单一「下一步」面板。服务端 `l1.next_action`（或 FE 选择器输入改为 summary 计数）驱动；删除第二栏与「实时」徽章。

**Rationale**: 现 `useDashboardSuggestions` 与 AI 栏同源重复；branches stub 使 tier 失真。

**Alternatives considered**: 方案 B 双栏（规则 + AI 产物）— 规格允许但默认不选，避免范围膨胀。

## R4 — 活动中文标题

**Decision**: 在 `dashboard.activity_labels`（BE）按 `ActivityType` + payload 渲染 `title_zh`/`detail_zh`；summary 的 `recent_activities` 只返回已渲染字段。FE 可保留薄 fallback 映射防漏网。

**Rationale**: 写入方多数无 `summary`；Dashboard `getActivityDisplay` fallback 到 raw `type`。

**Alternatives considered**: 仅改写入方补 summary — 历史行仍坏，且多处写入点易漏。

## R5 — 求职漏斗三段映射

**Decision**:

| 产品段 | 规则 |
|---|---|
| 投递中 | `status = applied` |
| 面试中 | `status IN (test, interview_1, interview_2, interview_3)` |
| 待反馈 | `status IN (test, interview_*)` 且 `interview_time IS NOT NULL` 且 `interview_time < now()`，且非终态 `failed/passed` |

在 summary 服务内聚合；**不**调用现有 `JobRepository.stats()`（仍含 oa/hr 等旧键，与前端新键不一致）。

**Rationale**: FSM 无 `waiting_feedback` 枚举；「待反馈」用时间+状态推导最贴近用户心智。

**Alternatives considered**:
- 仅展示 applied / interview_* / failed+passed — 「待反馈」语义弱。
- 修复 `/jobs/stats` 后复用 — 仍缺待反馈规则，可并行修但不阻塞 summary。

## R6 — 工作台摘要 API 与缓存

**Decision**:
- Endpoint: `GET /api/v1/me/dashboard-summary?tz=Asia/Shanghai`
- Redis key: `dashboard_summary:{user_id}:{local_date}`
- TTL: 60s（整包）；能力切片若拆分则 300s
- Miss/Redis 故障：直查 DB，不阻断
- 失效：job 写（含 interview_time/status）、resume v2 CRUD、interview session 状态变更、activity 写入 → `delete` 对应用户 key（当日 + 可选前日）

**Rationale**: 对齐 `card_renderer`/`drill_cache` 惯例；key 含 `local_date` 自然日切。

**Alternatives considered**:
- 仅 TanStack `staleTime` — 不满足跨请求 BE 减负与多端一致。
- 长 TTL（5min+）无写失效 — 今日面试易脏，拒绝。

## R7 — 可恢复面试会话

**Decision**: `status IN (pending, in_progress)` 的 session，链到现有 `/interview/{id}/live`；summary `l0.resumable_sessions` 最多 3 条。派生任务「继续」仅当存在稳定可恢复态时暴露（否则省略）。

**Rationale**: `InterviewList` 已用该规则；`resume` API 对 completed/expired 有 409/410。

## R8 — Auth 不重挡（REQ-037 最小集）

**Decision**: `useCurrentUser` 在已有 `user` 且 token 有效时，refetch/`isFetching` **不得** `setStatus('unknown')`；仅在无用户或 token 缺失时进入 unresolved。

**Rationale**: 登录成功 → invalidate CURRENT_USER → unknown → AuthGuard 全屏「正在校验」是已知根因。

**Alternatives considered**: 登录后不 invalidate — 会脏用户资料；拒绝。应 silent refresh。

## R9 — 能力数据

**Decision**: L2 使用轻量聚合（overall + 最弱维）；优先复用 ability-dimensions 或 summary 内聚合，完整 `ability-profile/dashboard`（含 history）不阻塞 L0。

**Rationale**: 完整 dashboard payload 偏重；指挥台只需快照。

## R10 — 前端查询策略

**Decision**: 单一 `useDashboardSummary({ localDate, tz })`，`placeholderData: previous`，`queryKey` 含 `localDate`；job/resume/interview mutation `onSuccess` → `invalidateQueries(['me','dashboard-summary'])`。L2 可同响应渲染，失败用面板 error。

**Rationale**: 满足 FR-022/027 与 SC-005/012；去掉 8+ fan-out。

## Open items closed for plan

| 原未知项 | 决议 |
|---|---|
| 今日过滤服务端 vs 客户端 | 服务端 summary |
| 待反馈无枚举 | 时间+面试态推导 |
| 是否必须 Redis | 必须（短 TTL + 失效） |
| AI 双栏 | 默认不做 |
| TZ | 默认 Asia/Shanghai + 查询参数 |
