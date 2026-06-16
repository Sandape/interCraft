# Feature Specification: Error Book Completion

**Feature Branch**: `[016-error-book-completion]`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "针对当前系统中的错题本模块完成完整代码开发。按 speckit specify/clarify/plan/tasks/implement 工作流推进，clarify 默认使用推荐选项；实现后完成代码审计、后端 curl 调用、前端调试、浏览器视觉验证与 E2E 测试。"

## Clarifications

### Session 2026-06-16

- Q: 错题本本次验收是否包含 Agent 强化对话的完整智能评分？ -> A: 不包含。本 feature 聚焦 M08 错题本 CRUD、状态推进、答对一次 recall、页面交互和异常恢复；M17 Error Coach 入口保留并兼容，但智能对话不作为本次完成条件。
- Q: “答对一次”后如何处理 frequency 和状态？ -> A: 每次 recall 将 frequency 减 1 并记录练习时间；frequency 2/1 为 practicing，frequency 0 为 mastered，mastered 可通过 reset 回到 fresh。
- Q: 删除行为如何定义？ -> A: 用户删除即从默认错题本视图移除，后端执行软删除；已删除题目不再通过列表或详情读取。
- Q: 异常退出重进场景是否要覆盖错题本筛选/详情状态？ -> A: 是。用户创建或练习错题后离开页面再进入，应能从后端数据恢复列表、筛选结果和详情操作入口。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 记录并管理错题 (Priority: P1)

求职者在错题本页面手动记录一道面试错题，填写题目、参考答案和能力维度，并立即在列表中看到该错题，可筛选、搜索和查看详情。

**Why this priority**: 这是错题本的核心价值；没有可靠的记录和查看能力，后续复习、强化和能力闭环都无法成立。

**Independent Test**: 注册或登录用户进入错题本，新增一道错题后通过列表、搜索、维度筛选和详情面板验证内容完整显示。

**Acceptance Scenarios**:

1. **Given** 用户已登录且错题本为空，**When** 用户新增一道包含题目、参考答案和维度的错题，**Then** 列表显示该错题，详情面板显示题目、答案、维度、状态和频次。
2. **Given** 用户已有多道不同维度错题，**When** 用户使用维度筛选或关键词搜索，**Then** 列表仅显示符合条件的当前用户错题。
3. **Given** 用户提交空题目或超长题目，**When** 用户尝试保存，**Then** 系统阻止提交或显示清晰错误，不创建无效错题。

---

### User Story 2 - 复习推进与掌握状态 (Priority: P1)

求职者复习错题后点击“答对一次”，系统自动降低频次并推进状态；答对到 0 后标记为已掌握，用户可在需要时重置为未掌握继续复习。

**Why this priority**: 错题本必须帮助用户从“记录错误”走向“消灭错误”，状态和频次是复习闭环的核心反馈。

**Independent Test**: 创建 frequency=3 的错题，连续点击“答对一次”三次，验证状态从 fresh/practicing 到 mastered，并验证 reset 可恢复 fresh/frequency=3。

**Acceptance Scenarios**:

1. **Given** 一道 fresh 且 frequency=3 的错题，**When** 用户点击“答对一次”，**Then** 错题变为 practicing 且 frequency=2，并记录最近练习时间。
2. **Given** 一道 practicing 且 frequency=1 的错题，**When** 用户点击“答对一次”，**Then** 错题变为 mastered 且 frequency=0。
3. **Given** 一道 mastered 错题，**When** 用户点击“重置为未掌握”，**Then** 错题变为 fresh 且 frequency=3。
4. **Given** 用户试图对不存在、已删除或非本人错题执行 recall/reset，**When** 请求提交，**Then** 系统返回错误且不改变任何错题。

---

### User Story 3 - 删除、异常和重进恢复 (Priority: P2)

求职者可以删除不再需要的错题；当网络或服务异常导致操作失败时，页面给出可理解反馈；用户中途离开并重进错题本后，已成功保存的状态仍可恢复。

**Why this priority**: 错题本是高频学习工具，失败反馈和恢复能力决定用户是否信任数据没有丢失。

**Independent Test**: 创建错题后删除并确认默认列表不可见；模拟失败响应确认页面显示错误；创建或 recall 后离开页面再进入，确认数据从后端恢复。

**Acceptance Scenarios**:

1. **Given** 用户选中一道错题，**When** 用户删除该错题，**Then** 详情面板关闭且默认列表不再显示该题。
2. **Given** 后端拒绝一次无效状态操作，**When** 用户触发该操作，**Then** 页面显示错误提示，并保留原列表和详情状态。
3. **Given** 用户对错题执行创建或 recall 后离开页面，**When** 用户重新进入错题本，**Then** 列表展示后端最新状态。

### Edge Cases

- 用户没有任何错题时，页面必须显示明确空状态和新增入口。
- 用户筛选条件无结果时，页面必须说明没有匹配错题，而不是呈现空白区域。
- 已掌握错题不应显示“答对一次”入口，但应显示“重置为未掌握”入口。
- 已删除错题的详情请求应返回不存在，且前端不得继续展示过期详情。
- 后端必须将跨用户访问表现为不可见，避免泄露其他用户错题存在性。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow authenticated users to list only their own non-deleted error questions with optional status, dimension, frequency, keyword-side filtering, and bounded limit.
- **FR-002**: System MUST allow authenticated users to create an error question with question text, optional answer, optional reference answer, optional score, optional tags, and optional controlled dimension.
- **FR-003**: System MUST validate error question input and reject invalid dimensions, empty question text, question text longer than 2000 characters, invalid score values, and invalid frequency/state combinations.
- **FR-004**: System MUST allow authenticated users to view a single non-deleted error question that belongs to them.
- **FR-005**: System MUST allow authenticated users to partially update editable fields without forcing clients to resend unchanged fields.
- **FR-006**: System MUST support a recall action that represents “answered correctly once” and atomically decreases frequency, updates status, and records last practiced time.
- **FR-007**: System MUST map frequency/status after recall as: frequency 3 => fresh, frequency 2 or 1 => practicing, frequency 0 => mastered.
- **FR-008**: System MUST allow reset only from mastered to fresh/frequency=3.
- **FR-009**: System MUST soft-delete user-owned error questions and exclude them from default list and detail reads.
- **FR-010**: System MUST return consistent, user-safe error responses for validation failures, illegal state transitions, missing records, deleted records, and cross-user access.
- **FR-011**: Users MUST be able to create, search, filter, select, recall, reset, and delete error questions from the error book page without broken text, layout overlap, or invalid hook/runtime errors.
- **FR-012**: The error book page MUST provide loading, empty, no-results, success, and error states for primary workflows.
- **FR-013**: The error book page MUST restore persisted list and item state after navigation away and back, based on server data.
- **FR-014**: System MUST preserve compatibility with the existing Error Coach entry point by showing the start action only for questions with frequency greater than 0.

### Key Entities *(include if feature involves data)*

- **Error Question**: A user-owned interview mistake record with question text, optional answer/reference, dimension, score, tags, status, frequency, last practiced time, archive/delete timestamps, and creation/update timestamps.
- **Recall Action**: A user action indicating one successful review attempt for an error question; it changes frequency/status and records practice time.
- **Error Book View State**: Page-level status filter, dimension filter, search term, selected error question, and operation feedback visible to the user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A logged-in user can create and find a new error question in under 60 seconds using the error book page.
- **SC-002**: 100% of recall attempts on valid user-owned questions produce the expected frequency/status transition.
- **SC-003**: 100% of invalid create, invalid recall/reset, deleted-record, and cross-user requests leave existing error question data unchanged.
- **SC-004**: The error book page renders without console errors or broken Chinese text across desktop and mobile-width browser checks.
- **SC-005**: E2E coverage proves both a normal complete review flow and an interrupted leave-and-return flow.

## Assumptions

- Existing authentication, current-user scoping, database session, and RLS-like repository filters are reused.
- This feature does not introduce new AI scoring logic; Error Coach remains an integration point, not a completion dependency.
- Existing status names remain canonical: fresh, practicing, mastered, archived.
- The first completed slice should preserve current API paths and add only backward-compatible fields/actions.
