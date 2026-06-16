# Feature Specification: Global Search Command Palette

**Feature Branch**: `[011-global-search]`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Topbar 全局搜索命令面板：搜索栏当前是装饰性的，placeholder 写"搜索简历、面试记录、能力维度…"但 onChange 没有处理；旁边有 ⌘K 提示但没有快捷键。范围限定为：1) 后端聚合搜索接口（resumes + interview_sessions + ability dimensions + FAQ + resources，限频 + 分页），2) 前端命令面板组件（Topbar 触发、Ctrl/Cmd+K 全局快捷键、上下键导航、Enter 跳转、Esc/外部点击关闭、空状态/无结果状态、加载状态），3) E2E：正常跨类型搜索 + 键盘快捷键 + 异常场景（空查询/无结果/外部点击关闭/重复快捷键切换/慢网络）。不做：移动端单独布局、深色模式独立优化（用现有系统）、搜索历史持久化、AI 语义排序。"

## Clarifications

### Session 2026-06-16

- Q: What search matching strategy should the backend use? -> A: Case-insensitive substring match (ILIKE) over the type-appropriate text fields. Simple, works with current Postgres setup, no extra index infrastructure required. Optional matching across both name and any human-friendly alias (e.g., `label_zh` for abilities).
- Q: How many results per type should the palette show? -> A: 5 results per type, with a total cap of 25 across all types. Keeps the response payload small and the palette scannable.
- Q: How should the frontend handle overlapping in-flight requests (e.g., user types fast)? -> A: Use `AbortController` on the client; the latest request cancels the previous one, and only the latest response renders. No need for a server-side generation token.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trigger and search from the topbar (Priority: P1)

A signed-in user opens the topbar search input or presses the global shortcut (Ctrl/Cmd+K), types a query of at least one character, and the command palette opens and shows results grouped by type (resume branches, interview sessions, ability dimensions, FAQ, resources) as the user types.

**Why this priority**: The current topbar search input is decorative only — it advertises a capability ("搜索简历、面试记录、能力维度…") that does nothing. This is the most user-visible dead surface in the shell and removes the most efficient way to navigate in a multi-feature product.

**Independent Test**: From any authenticated page, open the palette via the shortcut, type a query, and observe results appear in distinct groups with the keyword visible in at least one match. The palette closes after selecting a result and returns the user to a stable page.

**Acceptance Scenarios**:

1. **Given** an authenticated user on any page, **When** they press the global shortcut (Ctrl+K on Windows/Linux, Cmd+K on macOS), **Then** the command palette opens and the input is focused.
2. **Given** the palette is open, **When** the user types at least one non-whitespace character, **Then** results from multiple types appear grouped by type, with the matched term visibly highlighted or otherwise easy to spot.
3. **Given** the palette is open and showing results, **When** the user clicks a result, **Then** the palette closes and the user is routed to the appropriate destination.
4. **Given** the palette is closed, **When** the user clicks the topbar search input, **Then** the palette opens with the input focused and any prior query cleared.

---

### User Story 2 - Keyboard navigation inside the palette (Priority: P2)

A signed-in user can navigate the result list with the keyboard alone: arrow keys move the highlight, Enter opens the highlighted result, Escape closes the palette.

**Why this priority**: A command palette that requires the mouse to navigate defeats the "command" metaphor and the explicit `⌘K` hint visible in the topbar. Keyboard nav is the difference between a feature and a search box.

**Independent Test**: Open the palette, type a multi-result query, use the Down/Up arrow keys to move the highlight through every result, press Enter to navigate, and confirm the palette closes with focus returned to a stable page.

**Acceptance Scenarios**:

1. **Given** the palette is open and shows at least one result, **When** the user presses ArrowDown, **Then** the next result in the list is highlighted and scrolled into view.
2. **Given** a result is highlighted, **When** the user presses ArrowUp, **Then** the previous result is highlighted.
3. **Given** a result is highlighted, **When** the user presses Enter, **Then** the palette closes and the user is routed to that result's destination.
4. **Given** the palette is open, **When** the user presses Escape, **Then** the palette closes without navigating and focus is returned to the previously focused element.
5. **Given** the palette is open and the first result is highlighted, **When** the user presses ArrowUp, **Then** the highlight does not move (or wraps to the last item, but does not crash or clear).

---

### User Story 3 - Empty and error states (Priority: P3)

A signed-in user sees a clear, predictable state for every non-happy path: a placeholder hint when the palette opens with no query, a loading state while results are in flight, a clear "no results" state when the query matches nothing, and an inline error state if the request fails.

**Why this priority**: Without these states, the palette looks broken — a user cannot tell whether they should keep typing, wait, or assume the system is offline. The Constitution also requires error context, not silent failures.

**Independent Test**: Open the palette with an empty query and verify a hint is shown. Type a query that returns nothing and verify a "no results" message. Slow the network to a long delay and verify a loading state appears while in flight. Force a 5xx response and verify an error message appears with the palette remaining open.

**Acceptance Scenarios**:

1. **Given** the palette is open and the input is empty, **When** the user views the panel, **Then** a hint explains the supported types and that they can press Esc to close.
2. **Given** the user has typed a query, **When** the request is in flight, **Then** a loading indicator is visible inside the panel.
3. **Given** the request returns zero results, **When** the panel updates, **Then** a "no results" message is shown with the query echoed.
4. **Given** the request returns an error, **When** the panel updates, **Then** an error message is shown and the palette remains open so the user can retry.
5. **Given** the user types only whitespace, **When** the input updates, **Then** no request is sent and the hint state is shown.

---

### User Story 4 - Palette does not interfere with other interactions (Priority: P3)

A signed-in user can use the rest of the app normally while the palette is available: the shortcut never opens the palette on the login/register pages, the palette never opens while the user is typing in another input, and the palette can be toggled closed via the shortcut.

**Why this priority**: A global shortcut that hijacks the keyboard on the wrong screens or inside other text fields creates new dead behaviors. This is the same class of trust issue that motivated Spec 010 (topbar utility actions).

**Independent Test**: On the login and register pages, press the shortcut and confirm the palette does not open. While the palette is closed and the user is focused on another text input, type characters — the palette does not open. Press the shortcut a second time while the palette is open and confirm it closes.

**Acceptance Scenarios**:

1. **Given** the user is on the login or register page, **When** they press Ctrl/Cmd+K, **Then** the palette does not open.
2. **Given** the user is focused on any text input outside the palette, **When** they press Ctrl/Cmd+K, **Then** the palette opens (this is the global shortcut contract) and the user's previous focus is restored on close.
3. **Given** the palette is open, **When** the user presses the shortcut again, **Then** the palette toggles closed.
4. **Given** the palette is open, **When** the user clicks outside the palette, **Then** the palette closes without navigating.

### Edge Cases

- The user opens the palette, types a query, then navigates away via the browser back button — the palette should close and not reappear on the next page.
- Two search requests are in flight and the second completes after the first; the panel MUST display the second (latest) result set, not the first.
- A result is stale by the time the user clicks it (e.g., the underlying record was deleted); the destination handler should still resolve gracefully, and the palette MUST close.
- Very long input (>200 characters) MUST NOT crash the request; the input is truncated to a reasonable length before sending.
- The shortcut MUST work regardless of focused element, except for the two known public pages (login/register).
- A query that matches the user's own data MUST still respect RLS (i.e., never leak other users' data via the search endpoint).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The topbar search input MUST open the command palette on click.
- **FR-002**: A global keyboard shortcut (Ctrl+K on Windows/Linux, Cmd+K on macOS) MUST open the command palette from any authenticated page and toggle it closed when pressed again.
- **FR-003**: The global shortcut MUST NOT open the palette on the login or register pages.
- **FR-004**: The palette MUST show a grouped list of results from at least the following types: resume branches, interview sessions, ability dimensions, FAQ, and learning resources. The backend returns up to 5 results per type and a hard total cap of 25 results across all types in a single response.
- **FR-005**: The palette MUST show a hint state when the input is empty, a loading state while a request is in flight, a "no results" state when the query matches nothing, and an error state when the request fails.
- **FR-006**: The palette MUST support keyboard navigation: ArrowDown/ArrowUp to move the highlight, Enter to open the highlighted result, Escape to close without navigating.
- **FR-007**: Clicking a result MUST close the palette and route the user to the corresponding destination.
- **FR-008**: Clicking outside the palette MUST close it without navigating.
- **FR-009**: The backend search endpoint MUST enforce per-user rate limiting and respect the existing RLS policy so users can only see their own resumes, their own interview sessions, and their own ability scores. FAQ and resources are platform-wide content and are not subject to per-user RLS.
- **FR-010**: The backend search endpoint MUST paginate results per type and cap the total response size to keep the palette responsive.
- **FR-011**: When two overlapping requests are in flight, the palette MUST only display the latest result set. The frontend uses `AbortController` to cancel the previous request when a new one starts, so only the latest response is rendered.
- **FR-012**: All interactive palette controls MUST expose stable test identifiers for E2E verification.
- **FR-013**: The palette MUST truncate inputs longer than 200 characters before sending a request.
- **FR-014**: The shortcut MUST NOT trigger while the user is focused inside a text input that captures the Ctrl/Cmd+K combination for a different purpose (e.g., the topbar's own search input on click), to avoid double-firing.
- **FR-015**: The backend search endpoint MUST match queries using a case-insensitive substring (ILIKE) over the type-appropriate text fields. For ability dimensions, the match MUST also include the human-friendly alias (e.g., `label_zh`).

### Key Entities

- **Search Result**: A normalized result item surfaced in the palette. Attributes: id, type (one of: resume, interview, ability, faq, resource), title, subtitle, destination (the route the user is sent to on click), and a relevance score for ordering within its type.
- **Search Group**: A header band in the palette that contains results of a single type. Attributes: type key, label, and a list of Search Result items.
- **Search Query State**: The transient visible state of the palette. Attributes: open/closed, current input value, request status (idle, loading, success, error), highlighted result index, and request generation token (to discard stale results).
- **Search Response**: A single backend response. Attributes: total counts per type, per-type result lists (capped), and the request generation token it belongs to.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the always-visible topbar utility controls (help, notifications, avatar menu, search) perform a user-visible action within one click or one keyboard shortcut.
- **SC-002**: A signed-in user can find any of the user's own resume branch, interview session, ability dimension, FAQ entry, or learning resource by name in under 3 seconds from any authenticated page.
- **SC-003**: The palette returns and renders grouped results in under 1.5 seconds for 95% of queries in the development environment.
- **SC-004**: A request that fails (network error or 5xx) shows an inline error and keeps the palette open so the user can retry, in 100% of error cases.
- **SC-005**: Search results respect RLS: zero cross-user records appear in the palette, verified by an E2E isolation test.
- **SC-006**: The keyboard shortcut works in 100% of tested authenticated pages, and is correctly suppressed on 100% of public pages.

## Assumptions

- The existing user-scoped tables (resumes, interview_sessions, ability scores) already have RLS policies in place. The search endpoint reuses the same authenticated session and DB user, so RLS is enforced automatically.
- The topbar is rendered on every authenticated page via `AppShell`, so adding a global shortcut listener at the topbar level covers the entire authenticated area.
- The existing `content` module exposes FAQ and resource models that can be queried with simple case-insensitive substring matching — semantic search is out of scope.
- The backend has a working dependency-injection / service container that makes adding a new module (search) consistent with how other modules like `content` are organized.
- The frontend `useAuthStore` already exposes the current user's session, and the existing `apiClient` already attaches the bearer token, so no new auth plumbing is needed.
- The existing `Tooltip` or `Command` icon component is reusable for the new palette without new visual primitives.
- The first version does not persist search history; results are fetched fresh each time the palette opens or the query changes.
