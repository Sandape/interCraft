# M13 · 客户端 IndexedDB + Outbox 同步

> 状态: draft · 所属领域: D · 优先级: P1
> 引用原文档: §5.1, §5.2, §10.4 (Idempotency)

## 1. 需求摘要

在 React 前端引入离线优先架构:Dexie.js 操作 IndexedDB(实体镜像 + outbox 队列 + 元数据);写操作先入 IndexedDB + outbox,联网时 FIFO 回放;Idempotency-Key 防重;409/423 冲突 UI;限速 10 ops/s 防压垮。本模块**只做客户端**,服务端配合在 M12。

## 2. 验收标准

- [ ] Dexie schema 定义:对每个核心实体(resume_branches, resume_blocks, error_questions, tasks 等)有镜像表
- [ ] `outbox` 表:`{id, method, url, body, idempotency_key, status, retry_count, created_at}`
- [ ] `meta` 表:`{key, value}` 存 last_sync_at / device_id 等
- [ ] 写操作钩子:UI 调 `repo.create(...)` → 同步写 IndexedDB + outbox(pending)
- [ ] 联网检测:`navigator.onLine` + 心跳 ping `/healthz`,联网时自动 flush outbox
- [ ] FIFO 回放,限速 10 ops/s
- [ ] 服务端响应:200/201 → 标记 `synced`;409 → 标记 `conflict`,UI 展示 diff 合并;423 → 标记 `locked`,UI 提示「锁冲突」
- [ ] Idempotency-Key 在 outbox 持久化,重试用同一 key
- [ ] 读操作:完全本地;后台增量同步(基于 `updated_at` 游标)
- [ ] 配额监控:`navigator.storage.estimate()` 超阈值提示用户

## 3. 依赖与被依赖关系

**强依赖**: M22(前端 Repository 抽象层)
**弱依赖**: M12(锁的 423 处理)、所有业务 API 端点
**被以下模块依赖**: M23(页面切换 mock→HTTP 后受益)
**外部依赖**: `dexie`, `workbox-window`, React Query

## 4. 数据模型

**IndexedDB Schema(Dexie)**:
```typescript
db.version(1).stores({
  resume_branches: '++id, user_id, parent_id, status, last_edited_at, pending_sync',
  resume_blocks: '++id, branch_id, order_index, pending_sync',
  error_questions: '++id, user_id, category, last_missed_at, pending_sync',
  tasks: '++id, user_id, due_at, status, pending_sync',
  activities: '++id, user_id, occurred_at',
  outbox: '++id, status, created_at',
  meta: 'key',
});
```

`pending_sync` 索引便于 UI 渲染同步状态徽章。

**outbox 行**:
```typescript
interface OutboxEntry {
  id: number;
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  url: string;
  body: object;
  idempotency_key: string;  // uuid v4
  status: 'pending' | 'in_flight' | 'synced' | 'conflict' | 'locked' | 'failed';
  retry_count: number;
  last_error?: string;
  created_at: number;
}
```

## 5. 接口契约

**前端 Repository 接口**(由 M22 提供,M13 实现 IndexedDB 适配器):
```typescript
interface IRepository<T> {
  list(filter?: object): Promise<T[]>;
  get(id: string): Promise<T | null>;
  create(data: Partial<T>): Promise<T>;
  update(id: string, data: Partial<T>): Promise<T>;
  delete(id: string): Promise<void>;
}
```

**同步引擎**:
```typescript
class SyncEngine {
  enqueue(method, url, body, idempotency_key): Promise<void>;
  flush(): Promise<void>;  // FIFO 回放
  onConflict(handler): void;  // 409 处理
  onLock(handler): void;  // 423 处理
  status$: Observable<'online'|'offline'|'syncing'|'conflict'>;
}
```

## 6. 关键设计点

- **写时序**:UI → repo.create → IndexedDB write(pending_sync=true)+ outbox enqueue → 内存 state 立即更新
- **回放**:WebWorker 内运行 SyncEngine,避免阻塞主线程;限速 10 ops/s(`p-throttle` 库或自研)
- **乐观更新冲突**:服务端返回 409(版本不匹配)→ 前端拉远程版本 → 显示 diff 视图 → 用户选「保留我的」/「丢弃我的」/「手工合并」
- **锁冲突(423)**:停止该实体的所有 outbox 回放 → UI 切「只读 + 提示其他端编辑中」 → 用户可选强制抢锁(M12 接口)
- **Idempotency-Key 持久化**:enqueue 时生成,持久到 outbox;重试用同一 key;服务端 24h 内返回首次结果(参见 §10.4)
- **配额管理**:超 80% 配额时提示「请联网同步以释放空间」;超 95% 拒绝新写入
- **增量拉取**:`GET /resource?updated_after=last_sync_at`,后台 worker 每 5 分钟一次
- **服务端 hint**:可选支持 `If-Match: <version>` 头携带本地版本,服务端早 reject
- **离线场景判定**(参见 A3):在 lock 资源(简历编辑)上,离线写入要标注「pending,需联网验证锁」

## 7. 待澄清

- **[A3]** 离线 + 锁的边界:本模块在锁资源的 outbox 项额外标注 `requires_lock: true`,回放时优先尝试 acquire lock,失败走冲突 UI
- Dexie 版本迁移:`db.version(N).upgrade(...)`,但 IndexedDB 在浏览器关闭中升级会卡;需要规划迁移策略
- 哪些实体走 IndexedDB 镜像,哪些直接 HTTP:核心:resumes/tasks/errors;直 HTTP:reports(只读)/ 大对象

## 8. 实现提示

- 文件:
  - `src/lib/db/dexie.ts`(schema)
  - `src/lib/sync/SyncEngine.ts`(核心)
  - `src/lib/sync/conflict.tsx`(冲突 UI 组件)
  - `src/lib/repository/*.ts`(M22 引入)
- 复用: M12 的 lock API、M22 的 Repository 接口
- 与 mockData 关系: 无(mockData 是静态常量,迁移到真实 API 后由本模块缓存)
