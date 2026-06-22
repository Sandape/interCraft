# Feature Specification: Phase 2 (M5-M11) spec/code 偏差审计与修复

**Feature Branch**: `024-phase2-audit-fix`

**Created**: 2026-06-22

**Status**: Draft

**Input**: User description: "Feature 024 — Phase 2 (M5-M11) spec/code 偏差审计与修复。补齐 v1 Phase 2 模块的 spec/code 偏差，范围聚焦在六项高/中严重度 gap（来自 v2 启动前的 Phase 2 审计扫描）：(1) M9 岗位追踪 Offer 字段未实现；(2) M9 status_history 字段名前后端不一致；(3) M9 JobsDetailPanel 80% FR 缺失；(4) M9 outbox 未接入；(5) M7 archived 状态过度实现；(6) M8 能力画像 PIN/ProfileView 过度实现 + PDF 导出语义偏差。修复策略：M9 补齐 Offer 字段+UI+outbox（大改），M9 status_history 前端字段对齐后端（小改），M7 archived 状态移除+FSM 回归 spec（小改），M8 PIN/ProfileView 评估保留或移除（决策项），M8 PDF 导出对齐 spec「直接下载」（小改）。不改既有 API 契约（除新增 Offer 字段），不破坏既有 E2E。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 求职者记录 Offer 信息并查看完整岗位时间线 (Priority: P1)

作为求职者，当某岗位进入 offer 阶段时，我期望在岗位详情面板中录入 offer 薪资、联系人、联系方式、截止日期等信息，并在岗位时间线上看到完整的 status 流转记录（从 fresh → applied → interviewing → offered → accepted/rejected），而不是当前只能看到 basic info 和两个 CTA 按钮。当前后端 `jobs` 表缺少 spec 014 FR-018 要求的 4 个 Offer 字段，前端 `JobsDetailPanel` 缺 FR-002 时间线 / FR-003 编辑推进删除 / FR-009 编辑模式 / FR-019 Offer 区 / FR-025 activities，US1/US2/US3/US7 基本未实现，用户无法在系统中完成端到端的岗位追踪。

**Why this priority**: 岗位追踪是 M9 的核心功能，Offer 字段和时间线是用户最常查看的信息。当前 80% FR 缺失意味着用户只能在系统中看到一个岗位列表，无法实际使用此模块管理求职流程。这是 v1 上线后 Phase 2 最大的功能完整性 gap。

**Independent Test**: 创建一个用户 + 一个岗位，通过 API 录入 Offer 字段（薪资/联系人/联系方式/截止日期），调用 `GET /api/v1/jobs/{id}` 应返回完整 Offer 字段；前端打开 JobsDetailPanel 应看到时间线、编辑按钮、Offer 区、activities 列表。

**Acceptance Scenarios**:

1. **Given** 用户已创建岗位并推进到 `interviewing` 状态，**When** 用户在 JobsDetailPanel 点击「推进到 offer」并填写 offer 薪资/联系人/联系方式/截止日期，**Then** 岗位 status 变为 `offered`，Offer 字段持久化到数据库，时间线新增一条 `{from: interviewing, to: offered, at: <timestamp>, note: "Offer 录入"}` 记录。
2. **Given** 岗位已进入 `offered` 状态，**When** 用户打开 JobsDetailPanel，**Then** 面板展示 Offer 区（薪资、联系人、联系方式、截止日期）、完整时间线（按时间倒序）、activities 列表（含投递、面试、offer 三类活动）。
3. **Given** 用户在编辑模式下修改岗位 title/company/salary_range_text，**When** 点击保存，**Then** 岗位 basic info 更新，时间线新增一条 `{from: <原值>, to: <新值>, at: <timestamp>, note: "编辑 basic info"}` 记录（或按 spec 014 约定不记录编辑事件，仅记录 status 流转）。
4. **Given** 用户点击「删除岗位」，**When** 确认删除，**Then** 岗位软删除（`deleted_at` 设值），从列表中消失，不级联删除时间线和 activities（保留审计痕迹）。

---

### User Story 2 - 岗位写操作在离线时回退到 outbox 后续补发 (Priority: P1)

作为求职者，当我在地铁等弱网环境下创建/编辑/推进/删除岗位时，系统应当将写操作放入 outbox 在本地持久化，待网络恢复后自动同步到后端，而不是直接报错丢失我的操作。当前前端 `Jobs.tsx` 用 react-query 直接打后端，无 outbox 接入，离线时所有写操作失败。

**Why this priority**: outbox 模式是 spec 014 FR-022/023/024 明确要求的 4 类写操作兜底机制，也是 v1 宣传的离线优先能力。未接入 outbox 意味着岗位追踪在弱网下不可用，与产品定位（移动场景求职管理）严重背离。

**Independent Test**: 模拟离线（断网/后端关停），在 Jobs.tsx 创建一个岗位，应看到 toast「已加入待同步队列」；恢复网络后 outbox 自动 flush，岗位出现在列表中。

**Acceptance Scenarios**:

1. **Given** 用户处于离线状态，**When** 用户创建新岗位并点击保存，**Then** 岗位暂存到 outbox 队列，UI 显示「待同步」标记，不报错。
2. **Given** outbox 中有 3 条待同步岗位写操作，**When** 网络恢复，**Then** outbox 按 FIFO 顺序提交到后端，3 条操作全部成功后 UI「待同步」标记消失。
3. **Given** outbox 中某条操作因冲突（如岗位已被删除）失败，**When** 重试达到最大次数，**Then** 该条操作标记为 dead letter，UI 提示用户「同步失败，请手动处理」，不阻塞队列中其他操作。

---

### User Story 3 - 前端时间线字段名与后端契约对齐 (Priority: P2)

作为前端开发者，当我调用 `GET /api/v1/jobs/{id}` 获取岗位时间线时，后端返回的 `status_history` 字段使用 `{from, to, at, note}`，但前端 `JobRepository.ts` 和 `JobTimeline.tsx` 仍按 `{from_status, to_status, changed_at}` 读取，导致时间线组件渲染空白或 undefined。spec 014 承诺修复但未落地。

**Why this priority**: 字段名不一致是 v1 上线时就该修复的契约 bug，用户感知是「时间线不显示」。优先级低于 US1/US2（新功能 + 离线兜底），但仍是 P2 必修项。

**Independent Test**: 调用 `GET /api/v1/jobs/{id}` 获取含 3 条 status_history 的岗位，前端 JobTimeline 组件应渲染 3 条时间线节点，每条显示 from/to/note/at 字段。

**Acceptance Scenarios**:

1. **Given** 后端返回 `status_history: [{from: "fresh", to: "applied", at: "2026-06-22T10:00:00Z", note: "投递"}]`，**When** 前端 JobTimeline 渲染，**Then** 时间线节点显示「fresh → applied」「投递」「2026-06-22 10:00」。
2. **Given** 前端 `JobRepository.ts` 类型定义，**When** 运行 `npm run typecheck`，**Then** 无类型错误，字段名与后端响应 schema 一致。
3. **Given** 既有 round-1/round-2 E2E 中涉及岗位时间线的用例，**When** 重新运行 E2E，**Then** 所有用例通过，无字段名导致的回归。

---

### User Story 4 - 错题本状态机回归 spec 授权的 3 态 + reset (Priority: P2)

作为错题本用户，我期望错题状态仅在 `fresh` / `practicing` / `mastered` 三态间按 spec 016 FR-007/008 授权的路径流转（fresh→practicing→mastered + reset 回 fresh），而不是当前实现额外引入 `archived` 第 4 态（每态都可→archived）和 `practicing→fresh` 的回退路径。spec 016 明确说软删走 `deleted_at`，无任何 FR 覆盖 `archived` 状态。

**Why this priority**: 状态机过度实现是 spec/code 偏差的典型，会导致用户看到未授权的「归档」按钮或状态，与产品定义不一致。优先级 P2，因为 archived 状态当前 UI 未暴露给用户（仅后端有），但仍是必须修复的偏差。

**Independent Test**: 调用 `PATCH /api/v1/error-questions/{id}/status` 尝试 `fresh→archived`，应返回 422「非法状态转换」；尝试 `fresh→practicing→mastered→fresh (reset)` 应全部成功。

**Acceptance Scenarios**:

1. **Given** 错题当前 status=`fresh`，**When** 调用 `PATCH /error-questions/{id}/status` body=`{status: "archived"}`，**Then** 响应 422，错误信息包含「非法状态转换」。
2. **Given** 错题当前 status=`practicing`，**When** 调用 `PATCH /error-questions/{id}/status` body=`{status: "fresh"}`（回退），**Then** 响应 422，错误信息包含「非法状态转换」。
3. **Given** 错题当前 status=`mastered`，**When** 调用 `PATCH /error-questions/{id}/status` body=`{status: "fresh", reset: true}`，**Then** 响应 200，status 更新为 `fresh`，`mastered_at` 清空。
4. **Given** 后端 `VALID_TRANSITIONS` 常量，**When** 代码审查，**Then** 仅包含 `{fresh→practicing, practicing→mastered, mastered→fresh (reset)}` 三条路径，无 `archived` 相关转换。

---

### User Story 5 - 能力画像分享链接按 spec 走过期 + revoke (Priority: P2)

作为能力画像用户，我期望通过分享链接对外展示我的能力画像，链接支持过期时间和主动撤销（revoke），与 spec 006 FR-008/010 对齐。当前后端 `ability_profile` 表额外引入了 `pin_hash` + PIN 校验 + `ProfileView` IP 追踪表，这些能力 spec 006 未覆盖，属于过度实现。需评估保留或移除：若保留需在 spec 中追加 FR 覆盖；若移除需清理后端代码 + 迁移。

**Why this priority**: PIN/ProfileView 是 v1 开发中「顺手加的」能力，未走 spec 流程。保留则需补 spec FR，移除则需清理代码。决策项，优先级 P2。

**Independent Test**: 创建一个能力画像分享链接（expiration=7 天），7 天后访问应返回 410 Gone；在过期前调用 revoke 接口，访问应返回 403 Forbidden。

**Acceptance Scenarios**:

1. **Given** 用户已生成分享链接（`expires_at = now + 7d`），**When** 第 6 天访问链接，**Then** 响应 200，展示能力画像内容。
2. **Given** 同一链接，**When** 第 8 天访问，**Then** 响应 410 Gone，错误信息「链接已过期」。
3. **Given** 用户在链接过期前调用 `DELETE /api/v1/ability-profile/shares/{id}`，**When** 再次访问链接，**Then** 响应 403 Forbidden，错误信息「链接已撤销」。
4. **Given** PIN/ProfileView 决策为「移除」（plan 阶段确认），**When** 代码审查后端 `ability_profile` 模块，**Then** 无 `pin_hash` 列、无 PIN 校验逻辑、无 `ProfileView` 表（或迁移归档）。
5. **Given** PIN/ProfileView 决策为「保留并补 spec」（plan 阶段确认），**When** 查看 spec 006，**Then** 新增 FR 覆盖 PIN 校验和 ProfileView IP 追踪，acceptance scenario 定义 PIN 输错 3 次锁定等边界。

---

### User Story 6 - 能力画像 PDF 导出按 spec 直接下载 (Priority: P2)

作为能力画像用户，我期望点击「导出 PDF」按钮后浏览器直接下载 PDF 文件，而不是当前实现的「触发 ARQ 异步任务 → 轮询任务状态 → 任务完成后下载」三步走流程。spec 006 FR-018 明确说「直接下载」，实现却是 ARQ 异步 job（`service.py:419-420`），语义偏差。

**Why this priority**: PDF 导出语义偏差是用户感知层面的体验问题：用户期望「点击即下载」，当前实现需要等待 + 轮询，体验差。优先级 P2，修复成本小（同步生成 PDF 即可，PDF 内容通常 < 1MB，同步生成 < 2s）。

**Independent Test**: 点击「导出 PDF」按钮，浏览器应在 ≤ 3 秒内开始下载 `ability-profile-{user_id}-{date}.pdf` 文件，无需轮询任务状态。

**Acceptance Scenarios**:

1. **Given** 用户已登录并有能力画像数据，**When** 点击「导出 PDF」按钮，**Then** 浏览器在 ≤ 3 秒内触发下载，文件名 `ability-profile-{user_id}-{YYYYMMDD}.pdf`，文件大小 > 0。
2. **Given** PDF 导出请求，**When** 后端处理，**Then** 响应 `Content-Type: application/pdf` + `Content-Disposition: attachment; filename=...`，不走 ARQ 任务队列。
3. **Given** 用户连续点击 3 次「导出 PDF」，**When** 每次点击，**Then** 每次都立即触发下载，不因 ARQ 任务去重而拒绝。
4. **Given** 既有 ARQ PDF 任务代码（`service.py:419-420`），**When** 代码审查，**Then** ARQ 任务相关代码移除（或保留为「批量导出」独立功能，但单次导出走同步路径）。

---

### Edge Cases

- 当用户在编辑模式下修改 basic info 但未点击保存就切换页面时，必须有 unsaved-changes 警告，避免数据丢失。
- 当用户在 offer 阶段录入 offer_deadline_at 早于当前时间时，必须校验并提示「截止日期不能早于今天」。
- 当 outbox 中某条操作被用户手动取消（撤销）时，必须从队列中移除，不提交到后端。
- 当 outbox flush 过程中网络再次中断时，必须保留未提交的操作，下次恢复时继续。
- 当 status_history 时间线节点数 > 50 时，前端必须分页或虚拟滚动，避免渲染卡顿。
- 当用户删除岗位后，outbox 中待同步的该岗位写操作必须标记为 stale，不再提交。
- 当错题状态机收到非法转换请求时，必须记录 warning 日志（含 user_id / question_id / from / to），便于排查前端 bug。
- 当能力画像分享链接被撤销后，已生成的 PDF 缓存（若有）必须失效，访问应返回 403。
- 当 PDF 导出过程中用户关闭浏览器，同步生成路径无需清理（请求取消即终止），不产生孤儿任务。
- 当 PIN/ProfileView 决策为「保留」时，必须确保既有用户数据不丢失（`pin_hash` 列保留，迁移仅新增 FR 覆盖）。

## Requirements *(mandatory)*

### Functional Requirements

#### US1 — M9 Offer 字段 + JobsDetailPanel 补齐

- **FR-001**: 系统 MUST 在 `jobs` 表新增 4 列：`offer_salary_text` (text, nullable)、`offer_contact_name` (text, nullable)、`offer_contact_info` (text, nullable)、`offer_deadline_at` (timestamptz, nullable)，通过 Alembic 迁移创建。
- **FR-002**: 系统 MUST 在 `PATCH /api/v1/jobs/{id}` 接口接受这 4 个 Offer 字段（仅在 status=`offered` 或 `accepted` 时允许写入）。
- **FR-003**: 系统 MUST 在 `GET /api/v1/jobs/{id}` 响应中返回这 4 个 Offer 字段（null 或具体值）。
- **FR-004**: 前端 `JobsDetailPanel` MUST 渲染时间线组件（FR-002 of spec 014），按 `status_history` 倒序展示所有状态流转。
- **FR-005**: 前端 `JobsDetailPanel` MUST 提供编辑/推进/删除三类操作（FR-003 of spec 014），编辑模式可切换 basic info 字段为 input。
- **FR-006**: 前端 `JobsDetailPanel` MUST 提供 Offer 区（FR-019 of spec 014），在 status=`offered` 或 `accepted` 时展示 4 个 Offer 字段，支持编辑。
- **FR-007**: 前端 `JobsDetailPanel` MUST 渲染 activities 列表（FR-025 of spec 014），展示投递/面试/offer 三类活动的 timestamp + note。
- **FR-008**: 前端 `JobsDetailPanel` MUST 在编辑模式下提供保存/取消按钮，未保存切换页面时弹出 unsaved-changes 警告。

#### US2 — M9 outbox 接入

- **FR-010**: 前端 `Jobs.tsx` 的 4 类写操作（创建/编辑/推进/删除）MUST 通过 `src/lib/outbox/` enqueue 入队，不直接调用 react-query mutation。
- **FR-011**: outbox 队列 MUST 在本地持久化（IndexedDB 或 localStorage），刷新页面后不丢失。
- **FR-012**: outbox flush 逻辑 MUST 在网络恢复时自动触发，按 FIFO 顺序提交到后端。
- **FR-013**: outbox 中单条操作重试失败达 3 次后 MUST 标记为 dead letter，UI 提示用户「同步失败」。
- **FR-014**: outbox 中操作被用户撤销时 MUST 从队列移除，不提交到后端。
- **FR-015**: outbox flush 过程中网络再次中断时 MUST 保留未提交操作，下次恢复继续。

#### US3 — M9 status_history 字段名对齐

- **FR-020**: 前端 `JobRepository.ts` 的 `status_history` 类型定义 MUST 使用 `{from, to, at, note}` 字段名，与后端响应 schema 一致。
- **FR-021**: 前端 `JobTimeline.tsx` MUST 从 `entry.from` / `entry.to` / `entry.at` / `entry.note` 读取字段，不使用 `from_status` / `to_status` / `changed_at`。
- **FR-022**: 系统 MUST 保持后端 `status_history` 响应字段名不变（`{from, to, at, note}`），不向后端旧字段名妥协。
- **FR-023**: 前端 `npm run typecheck` MUST 通过，无字段名不一致导致的类型错误。

#### US4 — M7 archived 状态移除

- **FR-030**: 后端 `VALID_TRANSITIONS` 常量 MUST 仅包含 `{fresh→practicing, practicing→mastered, mastered→fresh (reset)}` 三条路径，移除所有 `archived` 相关转换。
- **FR-031**: 后端 `PATCH /api/v1/error-questions/{id}/status` 接口 MUST 对 `fresh→archived` / `practicing→archived` / `mastered→archived` / `practicing→fresh` 等未授权转换返回 422。
- **FR-032**: 后端 `error_questions` 表 MUST 移除 `archived_at` 列（通过 Alembic 迁移），软删统一走 `deleted_at`。
- **FR-033**: 后端 MUST 对非法转换请求记录 warning 日志（含 user_id / question_id / from / to），便于排查前端 bug。
- **FR-034**: 系统 MUST 保持既有 `fresh→practicing→mastered + reset` 路径的 E2E 测试通过，无回归。

#### US5 — M8 PIN/ProfileView 决策 + 分享链接过期/撤销

- **FR-040**: plan 阶段 MUST 对 PIN/ProfileView 做保留或移除决策，并在 spec 中记录决策依据。
- **FR-041**: 若决策为「移除」: 后端 MUST 移除 `pin_hash` 列、PIN 校验逻辑、`ProfileView` 表（通过 Alembic 迁移），清理相关 service 代码。
- **FR-042**: 若决策为「保留并补 spec」: spec 006 MUST 新增 FR 覆盖 PIN 校验（含输错 3 次锁定）和 ProfileView IP 追踪，acceptance scenario 定义边界。
- **FR-043**: 系统 MUST 保持 spec 006 FR-008（分享链接过期）和 FR-010（revoke）功能可用，`expires_at` 到期返回 410，revoke 后返回 403。
- **FR-044**: 前端分享链接管理 UI MUST 展示「过期时间」「撤销按钮」「访问次数（若 ProfileView 保留）」。

#### US6 — M8 PDF 导出对齐 spec「直接下载」

- **FR-050**: 后端 `GET /api/v1/ability-profile/export-pdf` MUST 同步生成 PDF 并直接返回（`Content-Type: application/pdf` + `Content-Disposition: attachment`），不走 ARQ 任务队列。
- **FR-051**: 后端 MUST 移除既有 ARQ PDF 任务相关代码（`service.py:419-420` 的 `enqueue_job` 调用 + worker 任务函数），或保留为「批量导出」独立功能但单次导出走同步路径。
- **FR-052**: 前端「导出 PDF」按钮 MUST 触发浏览器原生下载（`window.location.href = url` 或 `<a download>`），不使用轮询任务状态。
- **FR-053**: PDF 生成耗时 MUST ≤ 3 秒（单用户能力画像 < 1MB），不阻塞 event loop。
- **FR-054**: 系统 MUST 保持 PDF 内容与既有实现一致（能力维度雷达图 + 维度说明 + 建议），仅切换同步/异步路径。

#### 跨切面

- **FR-060**: 本 feature MUST 不改动既有 API 请求/响应契约（除新增 4 个 Offer 字段 + 移除 `archived_at` 列外）。
- **FR-061**: 本 feature MUST 不破坏既有 round-1 / round-2 E2E 测试套件，回归零退化。
- **FR-062**: 本 feature MUST 不引入新的运行时依赖（除非 PDF 同步生成需要的库已在依赖中）。
- **FR-063**: 本 feature MUST 保持所有既有 API 端点路径不变，仅扩展响应字段或调整内部实现。
- **FR-064**: 本 feature 涉及的数据库迁移 MUST 在生产环境通过 `CONCURRENTLY` 或非锁表方式执行，避免长锁。
- **FR-065**: 本 feature MUST 不改动其他 Phase 2 模块（M5/M6/M10/M11）的既有实现，范围严格限定在 M7/M8/M9。

### Key Entities *(include if feature involves data)*

- **jobs**: 新增 4 列 `offer_salary_text` / `offer_contact_name` / `offer_contact_info` / `offer_deadline_at`，nullable，仅在 status=offered/accepted 时写入。
- **status_history**: 字段名对齐 `{from, to, at, note}`，不改表结构（既有的 JSON 列），仅前端类型定义修正。
- **error_questions**: 移除 `archived_at` 列，保留 `deleted_at` 用于软删，`VALID_TRANSITIONS` 收敛到 3 态 + reset。
- **ability_profile_shares**: 保持既有 `expires_at` / `revoked_at` 列，决策项若移除 PIN 则删除 `pin_hash` 列 + `ProfileView` 表。
- **outbox_jobs**: 新增前端持久化队列（IndexedDB），存储 4 类岗位写操作，字段含 `id` / `type` / `payload` / `status` / `retry_count` / `created_at`。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 4 个 Offer 字段在 `jobs` 表存在，`GET /api/v1/jobs/{id}` 响应包含这 4 个字段，前端 JobsDetailPanel Offer 区可编辑并持久化。
- **SC-002**: JobsDetailPanel 渲染时间线、编辑/推进/删除按钮、Offer 区、activities 列表 5 大区域，覆盖 spec 014 FR-002/003/009/019/025。
- **SC-003**: 4 类岗位写操作（创建/编辑/推进/删除）在离线状态下进入 outbox 队列，网络恢复后自动同步，dead letter 率 ≤ 1%。
- **SC-004**: 前端 `JobRepository.ts` / `JobTimeline.tsx` 使用 `{from, to, at, note}` 字段名，`npm run typecheck` 通过，时间线组件渲染所有 status_history 节点。
- **SC-005**: 后端 `VALID_TRANSITIONS` 仅含 3 条授权路径，`PATCH /error-questions/{id}/status` 对 archived 相关转换返回 422，`error_questions` 表无 `archived_at` 列。
- **SC-006**: PIN/ProfileView 决策落地（保留并补 spec FR，或移除并清理代码），plan 阶段记录决策依据。
- **SC-007**: `GET /api/v1/ability-profile/export-pdf` 同步返回 PDF（≤ 3 秒），不走 ARQ 任务，前端点击即下载。
- **SC-008**: 既有 round-1 + round-2 E2E 测试套件 100% 通过，无回归（含 021 的 3 个 error_coach E2E）。

## Assumptions

- 后端使用 SQLAlchemy 2.x + Alembic，迁移可通过 `op.add_column` / `op.drop_column` / `op.drop_table` 实现，生产环境通过 `CONCURRENTLY` 或非锁表方式。
- 前端使用 React 18 + react-query + Vite + TypeScript，`src/lib/outbox/` 已有 outbox 基础设施（用于其他模块），本 feature 仅接入岗位写操作。
- PDF 同步生成使用既有 PDF 库（如 reportlab / weasyprint），能力画像内容 < 1MB，生成耗时 ≤ 3 秒可接受。
- `status_history` 字段名对齐仅涉及前端类型定义和组件读取，后端响应 schema 不变（后端已用 `{from, to, at, note}`）。
- `archived` 状态当前 UI 未暴露给用户（仅后端 VALID_TRANSITIONS 有），移除不影响用户感知。
- PIN/ProfileView 决策在 plan 阶段完成，spec 中保留两种分支的 acceptance scenario，决策后保留对应分支。
- outbox 队列已有基础设施（用于 resume 模块），本 feature 仅扩展到 jobs 模块的 4 类写操作。
- 本 feature 不修复 Phase 2 其他模块（M5/M6/M10/M11）的 spec/code 偏差，留待后续 feature。
- 本 feature 不升级既有依赖版本（如 langgraph / sqlalchemy），避免引入 breaking change。
- 数据库迁移在生产环境通过 `CONCURRENTLY` 执行，避免锁表；本地开发可普通 DDL。
