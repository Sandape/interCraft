# Quickstart: Phase 3 — 同步与离线打通

**Status**: Phase 3 validation guide · **Date**: 2026-06-13 · **Spec**: [spec.md](./spec.md) | **Phase 3 Plan**: [phase-3.md](./phase-3.md) | **Data Model**: [data-model-phase-3.md](./data-model-phase-3.md) | **Research**: [research-phase-3.md](./research-phase-3.md)

> 5 个可运行的验证场景,证明 Phase 3 的锁 + 离线 Outbox + WS 推送核心路径端到端可用。

## 0. Prerequisites

- Phase 1 + Phase 2 已就位(账号 + 简历 CRUD + 错题/Jobs/活动流 API 可用)
- Redis 7(本机 localhost:6379 已运行)
- PostgreSQL 15(在线 DB)
- 前端 `npm run dev` (localhost:5173) + 后端 `uv run uvicorn app.main:app` (localhost:8000)
- `VITE_USE_MOCK=false`
- 两个浏览器或两个隐身窗口(模拟多端)

---

## 1. 锁获取与释放(基础路径)

**证明**:悲观锁正常获取、阻止并发编辑、主动释放。

### 1.1 Lock Acquire → Edit → Release

```
1. 浏览器 A 登录,进入 ResumeEditor,打开简历分支 "字节·高级前端"
2. 观察:编辑器进入可编辑模式,分支标题旁显示 "🔒 正在编辑" (持锁标记)
3. curl 验证:
   curl -s -H "Authorization: Bearer $TOKEN_A" \
     "http://localhost:8000/api/v1/locks/resume_branch/$BRANCH_ID" | jq .locked
   # → true
4. 浏览器 A 点击退出编辑器或关闭 Tab
5. curl 再次验证:
   # → false (锁已释放)
```

### 1.2 Concurrent Edit Rejected

```
1. 浏览器 A 进入 ResumeEditor(获取锁成功)
2. 浏览器 B(登录另一个用户)访问同一简历分支 → UI 显示 "🔒 只读 · 张三正在编辑"
3. curl 验证(用户 B 尝试获取锁):
   curl -s -X POST http://localhost:8000/api/v1/locks/acquire \
     -H "Authorization: Bearer $TOKEN_B" \
     -H "Content-Type: application/json" \
     -d '{"resource_type":"resume_branch","resource_id":"'$BRANCH_ID'"}' | jq .error.code
   # → "lock.resource_locked"
```

---

## 2. WS 锁事件推送(多端实时)

**证明**:锁状态变更通过 WS 实时推送到所有在线客户端。

### 2.1 Lock Acquired Broadcast

```
1. 浏览器 A 和 B 同时以不同用户登录,Dashboard 都已打开
2. 浏览器 A 进入 ResumeEditor → 获取锁
3. 浏览器 B Dashboard → 顶部通知出现 "张三 开始编辑简历 '字节·高级前端'"
4. WS 抓包验证:
   ← {"type":"lock.acquired","resource_type":"resume_branch","resource_id":"...","user_name":"张三"}
```

### 2.2 Lock Released Broadcast

```
1. 浏览器 A 关闭 Tab(或主动退出编辑器)
2. 浏览器 B Dashboard → 通知 "张三 已退出编辑"
3. WS 抓包:
   ← {"type":"lock.released","resource_type":"resume_branch","resource_id":"...","reason":"manual"}
```

---

## 3. 离线编辑 + Outbox 回放(无锁资源)

**证明**:离线状态下编辑错题/Jobs/设置,联网后自动回放。

### 3.1 Offline Edit → Online Replay

```
1. 浏览器 A 登录,进入 ErrorBook 页,看到 3 条错题记录
2. DevTools Network → Offline
3. 编辑第 1 条错题的 tags:加上 "离线测试" → 保存
4. 编辑第 2 条错题:改 frequency 为 0,status 为 "mastered" → 保存
5. UI 显示: "离线 · 已暂存 2 条"
6. DevTools Application → IndexedDB → intercraft_outbox → outbox_entries:
   验证 2 条记录,status = "pending"
7. DevTools Network → Online
8. 观察:UI 从 "离线 · 已暂存 2 条" → "同步中..." → "已同步 2 条"
9. 刷新页面 → 验证修改已持久化
```

### 3.2 Offline → Conflict → Diff Merge

```
1. 浏览器 A 进入 ErrorBook(在线),记录错题 X 的 tags = ["A"]
2. 浏览器 A DevTools → Offline,编辑错题 X tags = ["A", "B(离线)"]
3. 浏览器 B(在线)编辑同一错题 X tags = ["A", "C(在线)"] → 成功
4. 浏览器 A DevTools → Online,outbox 回放错题 X
5. → 收到 409 conflict,server_entity.tags = ["A", "C(在线)"]
6. Diff 合并视图弹出:
   ┌─────────────────────────────────┐
   │ 本地版: ["A", "B(离线)"]        │
   │ 服务端版: ["A", "C(在线)"]      │
   │                                 │
   │ [√] 本地版  → [保留本地]        │
   │ [ ] 服务端版 → [采用服务端]      │
   └─────────────────────────────────┘
7. 用户选择 "保留本地" → 调用 PATCH /error-questions/{id} → outbox 标记 synced
8. 验证:tags = ["A", "B(离线)"]
```

---

## 4. 离线编辑锁资源告警 + Diff 合并

**证明**:离线超 60s 后编辑锁资源触发告警,联网后走 diff 合并。

### 4.1 Lock Resource Offline Warning

```
1. 浏览器 A 进入 ResumeEditor,获取锁成功
2. 浏览器 A DevTools → Offline
3. 等待 60s → UI 显式告警:"⚠ 锁可能已失效,离线超过 60 秒。联网后需手动解决冲突。"
4. 此时 IndexedDB **不** 存储简历编辑(锁资源不走 Outbox),编辑器保持在脏状态
```

### 4.2 Lock Resource Reconnect → Diff Merge

```
1. 步骤同 4.1,离线期间对简历 block 做了 2 处修改(本地内存中)
2. 此时另一用户 B 在线修改了同一 block 并保存
3. 浏览器 A DevTools → Online
4. UI 提示:"检测到服务端版本更新,请手动合并"
5. Diff 合并视图:字段级逐一对齐本地修改 vs 服务端版本
6. 用户逐字段选择 → 合并提交 → 服务端落盘新版本
```

---

## 5. 锁自动过期与心跳恢复

**证明**:锁在 90s 无心跳后自动释放,锁丢失时原用户收到通知。

### 5.1 Heartbeat Lost → Lock Auto-release

```
1. 浏览器 A 进入 ResumeEditor,获取锁
2. 强制关闭浏览器 A 进程(不是正常退出 Tab,模拟崩溃)
3. 浏览器 B 刷新同一简历分支 → 看到 "🔒 只读(锁持有者已离线)"
4. 等待约 90s → 浏览器 B 收到 WS 推送:
   ← {"type":"lock.released","reason":"heartbeat_lost"}
5. 浏览器 B UI 自动切换为可编辑模式
```

### 5.2 Lock Lost Notification

```
1. 浏览器 A 进入 ResumeEditor
2. 管理员或过期机制强制释放 A 的锁(curl):
   curl -s -X DELETE http://localhost:8000/api/v1/locks/$LOCK_ID \
     -H "Authorization: Bearer $TOKEN_ADMIN"
3. 浏览器 A WS 收到:
   ← {"type":"lock.lost","reason":"admin_revoked","message":"锁已被释放..."}
4. 浏览器 A UI:编辑器切换为只读,顶部提示 "保存草稿后重新获取锁"
```

---

## 6. 验收标准 Check List

- [ ] 锁获取 → 编辑 → 主动释放完整闭环
- [ ] 并发获取锁被拒(409),UI 正确显示只读状态
- [ ] WS 实时推送 lock.acquired / lock.released / lock.lost
- [ ] 离线编辑无锁资源(错题/Jobs/设置)→ Outbox 暂存 → 联网自动回放
- [ ] Outbox 回放 409 conflict → diff 合并视图 → 用户手动解决
- [ ] 离线超 60s 编辑锁资源 → 显式告警 → 联网 diff 合并
- [ ] 心跳 90s 无响应 → 锁自动释放
- [ ] 锁丢失通知(lost) → 前端正确切换只读

---

## 7. 演示脚本(5 分钟)

```
0:00  登录两个浏览器(A = user1, B = user2),Dashboard 就绪
0:30  A 进入 ResumeEditor → lock.acquired → 编辑 2 个 block
1:30  B 访问同一分支 → 只读标记 + WS 事件校验
2:00  A 离线 → 编辑 1 个错题 + 1 个 Job status → Outbox 暂存
2:30  B 编辑同一错题 → 成功落盘
3:00  A 联网 → Outbox 回放 → Job 成功,错题 Conflict → diff 合并
4:00  A 恢复编辑简历 → 离线 60s 告警验证
4:30  A 崩溃(kill 进程)→ B 90s 后自动获得编辑权 → lock.released 验证
5:00  完成
```
