# Quickstart: WeChat Conversational Agent

**Feature**: REQ-054 | **Date**: 2026-07-09

验证对话编排端到端可用。实现细节见 [plan.md](./plan.md)、契约见 [contracts/](./contracts/)。

## Prerequisites

- REQ-052：微信绑定 + 消息管道可用（或使用 `simulate-chat` 绕过 iLink）
- REQ-053：Jobs 新状态 + `interview_time` 校验已落地
- Redis 可写（ConversationContext）
- DeepSeek / `LLMClient` 可用（意图解析）；单测可 mock
- 测试用户已绑定微信（真实微信路径）或仅用 CLI 模拟

## Setup

```bash
cd backend
uv run alembic upgrade head   # 若有可选 agent_messages metadata 迁移
# 确保 Redis、Postgres、ARQ worker（出站 drain）运行
```

## VS-1 — 意图解析 CLI

```bash
uv run python -m app.modules.agent.cli parse-intent "新增岗位：腾讯，后端开发工程师" --json
```

**Expect**: `intent=create_job`, entities 含 `company=腾讯`, `position=后端开发工程师`, `confidence≥0.6`。

## VS-2 — 新增岗位（确认流）

**Path A — simulate-chat**:

```bash
uv run python -m app.modules.agent.cli simulate-chat <USER_ID>
# > 帮我记一个字节跳动的AI应用开发工程师岗位
# < 确认卡片
# > 确认
# < ✅ 已创建…
```

**Expect**: `jobs` 表新增对应记录；未确认前无写入。

**Path B — E2E**: mock 入站消息（见 `tests/e2e/wechat-conversation/create-job.spec.ts`）→ 断言 API/DB。

## VS-3 — 状态推进 + 相对时间

```text
用户: 字节进一面了，下周一 14:00 面试
Agent: 确认卡展示 Asia/Shanghai 绝对日期（按处理日推算下周一）
用户: 确认
```

**Expect**: `status=interview_1`，`interview_time` 正确；非法回退被拒绝并提示 Web。

## VS-4 — 元数据更新与拒绝删除

```text
用户: 把腾讯那个岗位地点改成深圳
→ 确认 → 仅 base_location 更新

用户: 删掉腾讯那个岗位
→ 不删除，引导 Web
```

## VS-5 — 查询

```text
用户: 我的求职进展
→ 状态分布摘要 ≤300 字

用户: 我的能力画像
→ 六维文字版或引导首次面试
```

## VS-6 — 微信模拟面试（互斥 + 续面）

1. 无进行中 session：`开始模拟面试` → 选模式 → 开始 → 5 轮文字作答 → 摘要报告  
2. Web 已有 `in_progress`：微信再 `开始模拟面试` → **拒绝新建**，提示继续/结束  
3. Web 进行到第 2 轮后：微信 `继续面试` → 收到第 3 题（共享 checkpoint）

**Expect**: SC-007 路径可测；评分文案 ≤500 字。

## VS-7 — LLM 降级

Mock `LLMClient` 连续失败 2 次：

**Expect**: 友好降级文案；**无** jobs 写入；指标/日志记录失败。

## VS-8 — 低置信度

注入 `confidence=0.4` + alternatives：

**Expect**: 列出 2–3 选项；用户选择后执行对应意图，不二次误解析写错。

## Automated tests (target)

```bash
cd backend
uv run pytest -q tests/unit/agent/conversation tests/integration/agent

# repo root
npm run e2e -- tests/e2e/wechat-conversation
```

## Definition of done (validation)

- [ ] VS-1…VS-8 手工或自动通过
- [ ] SC-005：无未确认写操作
- [ ] FR-021 CLI 可用
- [ ] 指标 `conversation_turns_total` 等有导出（或测试断言 inc）
