# M23 · 前端迁移(从 Mock 切到真实 API)

> 状态: draft · 所属领域: G · 优先级: P0
> 引用原文档: §12.1(前端架构)、§12.2(从 Mock 切换)

## 1. 需求摘要

把 `src/data/mockData.ts`(552 行静态常量)替换成**真实后端 API 调用**,采用**Repository 模式 + Zustand 状态 + React Query 缓存**三层架构,支持 `VITE_USE_MOCK` 环境变量一键回退到 mock 数据。**不一次性重写**,而是一个页面一个页面接入(每个页面 PR 独立可回滚)。这是产品从「Demo」走向「可用」的最后一公里。

## 2. 验收标准

### 基础设施
- [ ] `src/repositories/` 目录:每个领域一个 repository(ResumeRepository / InterviewRepository / ErrorBookRepository / AbilityRepository / TaskRepository / AuthRepository / AccountRepository),每个方法签名对应一个 REST 端点
- [ ] `src/stores/` 目录:Zustand store,按页面划分(useAuthStore / useResumeStore / useInterviewStore / useTaskStore),store 只存 UI 状态,数据走 React Query
- [ ] `src/hooks/queries/` 目录:React Query hooks(`useResumeBranches` / `useInterviewHistory` 等),统一处理 loading / error / 缓存失效
- [ ] `src/api/client.ts`:基于 `fetch` + 拦截器,自动注入 JWT、处理 401 跳转登录、处理 423 显示锁冲突、处理 409 提示冲突
- [ ] `src/api/ws.ts`:WebSocket 客户端,自动重连 + 指数退避 + `last_seen_checkpoint_id` 携带(配合 M14 + [A4])
- [ ] `VITE_USE_MOCK` 环境变量:`true` 时所有 repository 返回 mock 数据;`false`(默认)走真实 API
- [ ] 错误边界(React ErrorBoundary)+ 全局 Toast 提示

### WS 事件处理(参见 [A4])
- [ ] 断线时丢弃当前节点的 `token.delta` 直至 `node.started` 事件
- [ ] 重连成功后携带 `last_seen_checkpoint_id` 续传
- [ ] `sync.{user_id}` 频道事件:`lock.acquired` / `lock.released` / `lock.lost` / `account.lifecycle_changed` 等 → 触发 React Query 失效 + Toast

### 页面迁移顺序(按依赖关系)
- [ ] **P0 必做**(MVP 演示必需):
  1. 登录 / 注册页(对接 M04)
  2. 简历编辑器(对接 M06 + M07)
  3. 面试历史列表(对接 M11)
  4. 面试 Agent 页面(对接 M14 + M15)
  5. 简历优化 Agent 页面(对接 M16)
- [ ] **P1 应做**:
  6. 错题本页(对接 M08)
  7. 能力画像页(对接 M09 + M18)
  8. 任务 / 活动流页(对接 M10)
  9. Dashboard(聚合 M08 + M09 + M10 + M11)
  10. 错题强化 Agent(对接 M17)
  11. 通用 Coach Agent(对接 M19)
- [ ] **P2 可选**:
  12. 能力诊断(查看 M18 异步结果)
  13. 我的数据 / 导出 / 导入(对接 M20 + M21)
  14. 设备管理 / 安全设置(对接 M05)

### 测试
- [ ] 每个 repository 有对应的 mock 单测(MSW 拦截)
- [ ] 关键页面有 E2E 测试(Playwright,走 mock 后端)
- [ ] 视觉回归(可选):Chromatic / Percy
- [ ] 切换 `VITE_USE_MOCK=true` 后所有页面仍可演示(回退路径)

## 3. 依赖与被依赖关系

**强依赖**: 所有后端模块(M04 / M05 / M06-M23)
**弱依赖**: 无
**被以下模块依赖**: 无(终端模块)
**外部依赖**: Zustand / React Query / React Router v6 / Tailwind(已有) / MSW(测试) / Playwright(E2E)

## 4. 数据模型

无新表(前端不存数据)。本地状态结构:

```typescript
// src/stores/useResumeStore.ts
interface ResumeUIState {
  activeBranchId: string | null;       // 当前编辑的分支
  editingBlockId: string | null;       // 正在编辑的块
  isDragging: boolean;
  pendingPatch: JSONPatch | null;      // M16 中断时待确认的 patch
  setActiveBranch(id: string): void;
  // ...
}

// src/hooks/queries/useResumeBranches.ts
function useResumeBranches() {
  return useQuery({
    queryKey: ['resume-branches'],
    queryFn: () => resumeRepository.list(),
    staleTime: 30_000,  // 30s
  });
}

// src/repositories/ResumeRepository.ts
interface ResumeRepository {
  list(): Promise<ResumeBranch[]>;
  get(branchId: string): Promise<ResumeBranch>;
  create(input: CreateBranchInput): Promise<ResumeBranch>;
  update(branchId: string, patch: JSONPatch): Promise<ResumeBranch>;
  delete(branchId: string): Promise<void>;
  fork(sourceBranchId: string, name: string): Promise<ResumeBranch>;
  listBlocks(branchId: string): Promise<ResumeBlock[]>;
  reorderBlocks(branchId: string, blockIds: string[]): Promise<void>;
}
```

**WS 事件类型**(前端类型化):
```typescript
// src/api/ws-events.ts
type WSEvent =
  | { event: 'node.started', thread_id, node, data: any }
  | { event: 'token.delta', thread_id, token, message_id }
  | { event: 'node.finished', thread_id, node, data: any }
  | { event: 'interrupt', thread_id, graph, node, data: any }  // M16
  | { event: 'lock.acquired', resource_type, resource_id, owner_session }
  | { event: 'lock.released', resource_type, resource_id }
  | { event: 'lock.lost', resource_type, resource_id, reason }
  | { event: 'account.lifecycle_changed', status, reason }
  | { event: 'final', thread_id, summary };
```

## 5. 接口契约

**REST 客户端**(`src/api/client.ts`):
```typescript
class ApiClient {
  async request<T>(path: string, init?: RequestInit): Promise<T>;
  // 拦截器:
  // 1. 注入 Authorization: Bearer ${accessToken}
  // 2. 401 → 调 refresh endpoint → 重试
  // 3. refresh 失败 → 跳转 /login
  // 4. 423 → 抛 LockConflictError(UI 显示「资源被占用,是否抢锁?」)
  // 5. 409 → 抛 VersionConflictError(UI 显示 diff 预览)
  // 6. 410 → 抛 AccountGoneError(UI 显示「账号已注销」)
  // 7. 5xx → 上报到 Sentry + 通用错误 Toast
}
```

**Repository 模式**(统一接口):
```typescript
abstract class BaseRepository<T> {
  abstract list(params?: QueryParams): Promise<T[]>;
  abstract get(id: string): Promise<T>;
  abstract create(input: CreateInput<T>): Promise<T>;
  abstract update(id: string, input: UpdateInput<T>): Promise<T>;
  abstract delete(id: string): Promise<void>;
}

// 真实实现
class HttpResumeRepository extends BaseRepository<ResumeBranch> {
  constructor(private client: ApiClient) { super(); }
  async list() { return this.client.request<ResumeBranch[]>('/api/v1/resume-branches'); }
  // ...
}

// Mock 实现
class MockResumeRepository extends BaseRepository<ResumeBranch> {
  async list() { return mockData.resumeBranches; }
  // ...
}

// 工厂
const resumeRepository = import.meta.env.VITE_USE_MOCK
  ? new MockResumeRepository()
  : new HttpResumeRepository(apiClient);
```

**WebSocket 客户端**(`src/api/ws.ts`):
```typescript
class WSClient {
  connect(threadId: string, lastSeenCheckpointId?: string): void;
  on(event: WSEvent['event'], handler: (data: any) => void): void;
  send(message: ClientMessage): void;
  close(): void;
  // 自动重连:指数退避(1s / 2s / 4s / 8s / max 30s)
  // 心跳:每 30s 发送 ping
  // 断线时缓存 outgoing 消息(最多 100 条)
}
```

## 6. 关键设计点

- **Repository 模式**:
  - 所有数据访问走 repository,不直接在组件里调 `fetch`
  - repository 可替换(mock / 真实 / 离线 IndexedDB 镜像)
  - 配合 M13 客户端离线:可注入 `OfflineResumeRepository`(用 Dexie 数据 + outbox)
- **Zustand vs React Query 边界**:
  - **Zustand**:UI 状态(选中哪条记录 / 抽屉开关 / 表单暂存)
  - **React Query**:服务端数据(列表 / 详情),自带缓存 + 失效 + 重试
- **`VITE_USE_MOCK` 切换**:
  - 启动时读取环境变量,选不同 repository 实现
  - 切换无需重启:dev 模式下热重载;prod 模式构建时决定
  - 测试时强制 `true`;E2E 走 mock 后端(MSW)
- **错误处理**:
  - 网络错误 → Toast「网络异常,请重试」+ Retry 按钮
  - 401 → 静默 refresh,失败跳登录
  - 423 → 弹 Modal「该资源被其他端占用,是否抢锁?」(M12)
  - 409 → 弹 Modal「数据版本冲突,选择保留哪一版」(M06 / M07)
  - 410 → 跳注销说明页
  - 422 → 表单字段级错误
- **WS 断线重连(参见 [A4])**:
  - 客户端维护 `lastSeenCheckpointId`(由 `node.finished` / `node.started` 事件携带)
  - 重连时 URL 带 `?last_seen_checkpoint_id=...`
  - 服务端(M14)从该点之后开始重放
  - 断线期间:丢弃所有 `token.delta`,等待 `node.started` 后才重新接收(避免重复 token)
- **加载状态**:
  - Skeleton(首屏)/ Spinner(操作反馈)/ 禁用按钮(防重复提交)
  - 乐观更新:对低风险操作(标记任务完成)立即更新 UI + 失败回滚
- **降级**:
  - WS 失败 → 降级为 3s 轮询
  - API 超时 → 提示「服务繁忙」
  - mock 模式下所有功能可用(回退路径)
- **类型共享**(可选):后端用 `pydantic` 生成 OpenAPI → 前端用 `openapi-typescript` 生成 TS 类型,避免手写漂移
- **i18n 预留**:文案集中在 `src/i18n/zh-CN.ts` / `en-US.ts`,先只用中文
- **__version__ = "1.0.0"**

## 7. 待澄清

- **[A4]** 断线时 token 丢弃策略:需前端 WS 客户端实现「断线 → 缓存 partial tokens → 重连 → 若收到 node.started 则丢弃,否则重放」,具体状态机由前端设计
- **`VITE_USE_MOCK` 切换粒度**:全局 vs 页面级(只让某些页走 mock)?MVP 用全局
- Repository 层是否需要支持 IndexedDB 镜像(M13):MVP 不实现,repository 只服务 React Query;M13 镜像独立维护
- E2E 覆盖范围:每个 P0 页面至少 1 个 happy path E2E
- 是否做 Storybook 组件库:MVP 不做,组件直接写在页面里

## 8. 实现提示

- 文件结构(新增):
  ```
  src/
  ├── api/
  │   ├── client.ts          # HTTP 客户端 + 拦截器
  │   ├── ws.ts              # WebSocket 客户端
  │   ├── ws-events.ts       # WS 事件类型
  │   └── errors.ts          # 错误类(LockConflictError / VersionConflictError / ...)
  ├── repositories/
  │   ├── BaseRepository.ts
  │   ├── AuthRepository.ts
  │   ├── ResumeRepository.ts
  │   ├── InterviewRepository.ts
  │   ├── ErrorBookRepository.ts
  │   ├── AbilityRepository.ts
  │   ├── TaskRepository.ts
  │   ├── AccountRepository.ts
  │   └── index.ts           # 工厂(根据 VITE_USE_MOCK 决定)
  ├── stores/                # Zustand
  │   ├── useAuthStore.ts
  │   ├── useResumeStore.ts
  │   └── ...
  ├── hooks/
  │   ├── queries/           # React Query
  │   │   ├── useResumeBranches.ts
  │   │   ├── useInterviewHistory.ts
  │   │   └── ...
  │   └── mutations/         # 写操作
  │       ├── useUpdateBranch.ts
  │       └── ...
  └── pages/                 # 替换为真实 API(渐进式)
      ├── Login/
      ├── ResumeEditor/      # 替换 mockData
      ├── Interview/
      └── ...
  ```
- 复用:现有 `src/components/`(UI 组件不动);`src/data/mockData.ts` 改名为 `mockData.legacy.ts`,只给 mock repository 用
- 依赖库:`zustand` / `@tanstack/react-query` / `react-router-dom@6` / `openapi-typescript`(可选)
- 测试:`tests/msw/handlers.ts`(MSW mock handlers)+ `tests/e2e/`(Playwright)
- 迁移 checklist(每完成一项打勾):
  - [ ] Login 页接 M04
  - [ ] ResumeEditor 接 M06+M07
  - [ ] InterviewHistory 接 M11
  - [ ] InterviewAgent 接 M14+M15
  - [ ] ResumeOptimize 接 M16
  - [ ] ErrorBook 接 M08
  - [ ] AbilityProfile 接 M09+M18
  - [ ] Tasks 接 M10
  - [ ] Dashboard 聚合
  - [ ] ErrorCoach 接 M17
  - [ ] GeneralCoach 接 M19
  - [ ] AccountSettings 接 M20+M21+M05
- 与 mockData 关系:`mockData.ts` 是迁移源头(参考字段命名 / 默认值),迁移完成后**保留**给 `VITE_USE_MOCK=true` 模式
