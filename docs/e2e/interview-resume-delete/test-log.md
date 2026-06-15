# E2E 测试日志: 继续未完成面试 + 删除面试记录

**目标**: 验证 InterviewList 支持"继续未完成的面试"和"删除面试记录",并在浏览器中以真实用户视角完成端到端验证。

**环境**:
- 前端: vite dev server @ `http://localhost:5178`
- 后端: FastAPI @ `http://127.0.0.1:8000`,通过 vite proxy 暴露
- 浏览器驱动: Playwright MCP
- 日期: 2026-06-15

**测试账号**: `e2e-resume-delete@intercraft.io` / `Demo1234`
**测试用户 ID**: `019ec72b-09d0-781d-b1d4-1e3cfba84660`

---

## 测试场景

1. 登录账号
2. 创建新的模拟面试(Backend Engineer @ ByteDance)
3. 主动离开面试页面 → 回到面试列表
4. 验证列表显示"进行中"徽章 + "继续面试"按钮
5. 点击"继续面试" → 进入面试页面,验证消息流恢复
6. 删除一条面试记录 → 验证软删除生效
7. DB 落库验证 (`deleted_at` IS NOT NULL)

## 关键步骤截图与时间线

| # | 步骤 | 截图 | 关键观察 |
|---|---|---|---|
| 01 | 登录页填表 | `01-login-filled.png` | 邮箱/密码输入框填充 |
| 02 | 登录后跳转工作台 | `02-dashboard.png` | 顶部欢迎 + 工作台卡片 |
| 03 | 进入模拟面试列表(空) | `03-interview-list-empty.png` | "还没有面试记录"空状态 |
| 04 | 新建面试:填表(岗位+公司) | `04-setup-filled.png` | "Senior Backend Engineer @ ByteDance" |
| 05 | 点击开始面试 → 加载中 | `05-live-start.png` | "正在创建面试..." → 进入 live |
| 06 | 第一题 WS 错误(已知 Phase4 问题) | `06-after-intro-ws-error.png` | AsyncPostgresSaver 空闲连接关闭 |
| 07 | 主动离开,回到列表(进行中) | `07-list-with-in-progress.png` | "进行中" 徽章 + "继续面试" 按钮 + 删除图标 |
| 08 | 点击"继续面试" → 恢复会话 | `08-resumed-live.png` | 标题旁"已恢复" + 开场消息恢复 + 第 0/5 轮 |
| 09 | 点击删除图标 → 确认对话框 | `09-delete-confirm-dialog.png` | "删除面试记录 / ByteDance · Senior Backend Engineer / 软删除" |
| 10 | 点击"确认删除" → 列表清空 | `10-list-after-delete.png` | "还没有面试记录,开始你的第一场模拟面试吧" |

---

## 步骤 8: 继续面试(resume)验证细节

URL: `http://localhost:5178/interview/78f90d97-c197-464f-9f6c-c1a5813c6dfc/live`

**Header 状态**:
- 角色:`A面` 头像
- 副标题:`AI 面试官 · 在线 · 已恢复` ← **resume 标记**
- 岗位上下文:`ByteDance · Senior Backend Engineer`
- 进度:`第 0/5 轮`

**消息流**:
- 左侧气泡:`AI 面试官 · 开场`
- 内容:`你好，我是 AI 面试官。本次面试共 5 道题,覆盖技术深度、系统架构、工程实践、沟通协作和算法能力五个维度。请先简单介绍一下你自己,包括你的项目经验和目标岗位。`

**侧栏反馈**:
- `等待首轮评分 / 回答第一道题后将显示实时评分`
- WS 状态:`已连接`

> **注**: 第一次 resume 在原 backend 上失败,因为 AsyncPostgresSaver 空闲后连接关闭(`the connection is closed`)。重启后端以 `run.py` (SelectorEventLoop) 后,resume 调用成功,见 `08-resumed-live.png`。

## 步骤 9: 删除确认对话框

按钮文案:`确认删除`(红色,带 trash 图标)
取消按钮:低饱和 ghost 样式
主消息:完整显示 session 标签 `ByteDance · Senior Backend Engineer`
副说明:`此操作会软删除该面试,列表中将不再显示。`
外层遮罩点击取消(非 pending 状态)

## 步骤 10: 删除后状态

- 列表 Tab 计数:`历史记录 0`
- 累计面试指标:`0 场 / 0 场已完成`
- 平均评分/通过率/练习时长:全部归 0(空状态文案 "暂无数据")
- 主区空状态:`还没有面试记录,开始你的第一场模拟面试吧`

---

## DB 落库验证

使用 `backend/scripts/verify_soft_delete.py`(封装 asyncpg + RLS GUC):

```sql
SET LOCAL app.user_id = '019ec72b-09d0-781d-b1d4-1e3cfba84660';
SELECT id, status, deleted_at, position, company
FROM interview_sessions
WHERE id = '78f90d97-c197-464f-9f6c-c1a5813c6dfc'::uuid;
```

**结果**:
```
id         = 78f90d97-c197-464f-9f6c-c1a5813c6dfc
company    = ByteDance
position   = Senior Backend Engineer
status     = in_progress
deleted_at = 2026-06-14 17:39:32.150018+00:00
[OK] soft delete persisted: deleted_at is set
```

**关键发现**:
- 行仍然存在(软删除,非硬删除)
- `status` 保持 `in_progress`(delete 不变更业务状态)
- `deleted_at` 与浏览器中的删除点击时间一致(2026-06-14 17:39:32)

## API 一致性验证(删除后)

使用同一用户 token 调 API:

| 调用 | 期望 | 实际 |
|---|---|---|
| `GET /api/v1/interview-sessions` | `data.length === 0` | `0` ✅ |
| `GET /api/v1/interview-sessions/{deletedId}` | 404 | `HTTP 404` ✅ |
| `DELETE /api/v1/interview-sessions/{deletedId}` (idempotent) | 404 | `HTTP 404` ✅ |

---

## 验收结论

| 验收项 | 结果 |
|---|---|
| **1. 后端业务正确和落库正确** | ✅ 通过 |
| 1a. DELETE 接口存在并返回 204 | ✅ 单元/集成测试覆盖 |
| 1b. 软删除(`deleted_at`)在 PG 中正确写入 | ✅ 实际查询确认 |
| 1c. 软删除行不返回 list API | ✅ `list count=0` |
| 1d. 软删除行 `GET` 返回 404 | ✅ |
| 1e. 二次 DELETE 幂等返回 404 | ✅ |
| 1f. RLS 隔离(其他用户不能删) | ✅ 集成测试 `test_cross_user_delete_404` 覆盖 |
| **2. 完整 E2E(Playwright + 截图 + 日志)** | ✅ 通过 |
| 2a. 登录 → 创建面试 → 中途离开 | ✅ 截图 01-07 |
| 2b. 列表显示"进行中" + "继续面试" + 删除图标 | ✅ 截图 07 |
| 2c. 继续面试恢复消息流 | ✅ 截图 08(包含"已恢复"标记) |
| 2d. 删除确认对话框 UI | ✅ 截图 09 |
| 2e. 删除后列表清空 | ✅ 截图 10 |

## 已知遗留问题(非本次目标范围)

- `AsyncPostgresSaver` 空闲后连接关闭,首次 `submit_answer` 失败,**重试是 no-op**。建议在 `app/agents/checkpointer.py` 改为每次调用 `aclose()` 后重建,或启用 `pool_pre_ping` 类似的健康检查。
- `InterviewReport` 存在 `BarChart3 is not defined` 错误(运行时未在本次 E2E 触发,但存在于 console 日志),需要从 `lucide-react` 补全 import。
- 计划任务: `interview_checkpointer_caveat.md` memory 已有记录,见 session `ac094a77-d924-48ae-bac5-0ea654fbcc06`。
