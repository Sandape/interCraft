# CLI Contracts — WeChat Conversational Agent

**Module**: `python -m app.modules.agent.cli`  
**Principle**: Constitution II — local-first, `--json` where useful

## Existing (REQ-052, keep)

- `send-test-message <user_id> <text>`
- `agent-status <user_id>`
- `list-bindings`

## New (REQ-054)

### `parse-intent`

```text
python -m app.modules.agent.cli parse-intent "<message>" [--json]
```

| Aspect | Contract |
|--------|----------|
| Input | 自然语言字符串（可含中文） |
| Behavior | 调用意图解析（可 mock LLM in tests）；**不**执行工具 |
| stdout (default) | 人类可读：intent / confidence / entities |
| stdout (`--json`) | `IntentParseResult` JSON |
| Exit | `0` 成功解析（含 unknown）；`2` LLM 不可用；`1` 其它错误 |

### `simulate-chat`

```text
python -m app.modules.agent.cli simulate-chat <user_id> [--json-lines]
```

| Aspect | Contract |
|--------|----------|
| Input | 已存在的 InterCraft `user_id`（需能加载 jobs/sessions） |
| Behavior | 交互式 REPL：每行用户输入 → Orchestrator（**绕过 iLink**，出站打印到终端） |
| Side effects | 真实写 DB（create/status）——文档需警告；测试用专用用户 |
| Exit | `0` 正常结束（EOF / `quit`）；`1` 用户不存在 |

**Non-goals**: 不启动长轮询；不发送真实微信。

## Suggested CI usage

```bash
cd backend
uv run python -m app.modules.agent.cli parse-intent "帮我记一个腾讯的后端岗" --json
```
