# InterCraft Test Plan

## Application Overview

InterCraft is a spec-driven full-stack web app: React + Vite frontend on port 5173, FastAPI backend on :8000. It is an AI-powered technical-job-search platform combining resume management, AI mock interviews, error book, jobs pipeline tracking, and a Personal Ability Profile (radar/timeline). Authentication is JWT (access+refresh) tokens stored in localStorage. Routes: /login, /register (mode toggle on Login), /dashboard, /resume, /resume/:branchId, /interview, /interview/new, /interview/:id/live, /interview/:id/report, /profile, /ability-profile, /ability-profile/:abilityKey, /jobs, /error-book, /settings, /coach, /help, /shared/:shareToken. Seeder credential: tester@local / Passw0rd! (registration fallback: e2e+planner@local / Passw0rd!).

## Test Scenarios

### 1. auth

**Seed:** `e2e/seed.spec.ts`

#### 1.1. login with seeded credentials

**File:** `e2e/auth/login-happy.spec.ts`

**Steps:**
  1. Navigate to http://localhost:5173/login
    - expect: Login form renders with email + password fields
    - expect: 欢迎回来 heading visible
  2. Enter email tester@local and password Passw0rd!
    - expect: Inputs accept values
    - expect: submit button enabled
  3. Click 登录 button
    - expect: Redirected to /dashboard
    - expect: No error alert visible
    - expect: topbar shows avatar placeholder

#### 1.2. login with wrong password shows error

**File:** `e2e/auth/login-bad-creds.spec.ts`

**Steps:**
  1. Navigate to /login
    - expect: Login page loads
  2. Enter tester@local and wrong password WrongPwd1
    - expect: Submit enabled
  3. Click 登录
    - expect: Inline error 邮箱或密码错误 appears (data-testid=auth-error)
    - expect: Still on /login

#### 1.3. register new account via mode toggle

**File:** `e2e/auth/register-happy.spec.ts`

**Steps:**
  1. Navigate to /register
    - expect: Login component renders in register mode
    - expect: 创建账号 heading visible
    - expect: Optional 姓名 field appears
  2. Enter email e2e+planner@local, password Passw0rd!, display name Planner
    - expect: All fields accept values
  3. Click 创建账号
    - expect: If account is new: redirected to /dashboard
    - expect: If email already taken: 该邮箱已被注册 inline error

#### 1.4. register with weak password rejected

**File:** `e2e/auth/register-weak-pwd.spec.ts`

**Steps:**
  1. Navigate to /register
    - expect: Register form visible
  2. Enter email weak@local and password 'abc1'
    - expect: Browser minLength OR server-side 密码强度不足 message shown
  3. Submit form
    - expect: Account is NOT created
    - expect: User stays on /register with validation message

#### 1.5. unauthenticated access redirects to login

**File:** `e2e/auth/guard-redirect.spec.ts`

**Steps:**
  1. Clear local storage and navigate to /dashboard
    - expect: Redirected to /login with from location state preserved
  2. Log in successfully with seeded credentials
    - expect: After login, returned to /dashboard (deep link preserved)

#### 1.6. password visibility toggle

**File:** `e2e/auth/show-password.spec.ts`

**Steps:**
  1. Navigate to /login
    - expect: Password input is type=password
  2. Click the eye icon in the password field
    - expect: Input type switches to text
    - expect: Password visible
  3. Click eye icon again
    - expect: Input type back to password

#### 1.7. invalid email format rejected

**File:** `e2e/auth/email-invalid.spec.ts`

**Steps:**
  1. Navigate to /login
    - expect: Login page loads
  2. Enter 'notanemail' as email and valid password
    - expect: Browser native validation OR server-side 邮箱格式不正确 shown
  3. Submit form
    - expect: Form not submitted (validation blocks)

### 2. dashboard

**Seed:** `e2e/seed.spec.ts`

#### 2.1. dashboard renders widgets after login

**File:** `e2e/dashboard/dashboard-happy.spec.ts`

**Steps:**
  1. Log in with tester@local / Passw0rd! and land on /dashboard
    - expect: Dashboard heading visible
    - expect: Ability radar mini-card visible
    - expect: Recent interviews card visible
    - expect: Error book summary visible
    - expect: Jobs pipeline summary visible

#### 2.2. dashboard click-through navigation

**File:** `e2e/dashboard/dashboard-nav.spec.ts`

**Steps:**
  1. From /dashboard, click '新建模拟面试' shortcut
    - expect: Navigates to /interview/new
  2. Go back to /dashboard, click '查看简历' shortcut
    - expect: Navigates to /resume
  3. Go back to /dashboard, click '能力画像' shortcut
    - expect: Navigates to /ability-profile

#### 2.3. dashboard empty state for new user

**File:** `e2e/dashboard/dashboard-empty.spec.ts`

**Steps:**
  1. Log in with a brand-new account (no resumes/interviews)
    - expect: Dashboard shows empty-state CTAs (新建简历, 开始第一次模拟面试)
    - expect: Ability radar shows zero-baseline state

### 3. resume

**Seed:** `e2e/seed.spec.ts`

#### 3.1. resume list shows branches

**File:** `e2e/resume/list-happy.spec.ts`

**Steps:**
  1. Navigate to /resume
    - expect: ResumeList renders
    - expect: PrimaryResumeCard visible at top if a primary branch exists
    - expect: Other branches listed with name + updated_at

#### 3.2. create new resume branch

**File:** `e2e/resume/create-branch.spec.ts`

**Steps:**
  1. From /resume, click 新建分支 button
    - expect: Modal opens with name input
  2. Enter '后端-Go' and confirm
    - expect: New branch appears in list with success toast
    - expect: Auto-opens editor for that branch

#### 3.3. open branch into editor

**File:** `e2e/resume/open-editor.spec.ts`

**Steps:**
  1. From /resume list, click a branch card
    - expect: Navigates to /resume/:branchId
    - expect: ResumeEditor renders with sidebar (基础信息/教育/项目/技能), Quick or WYSIWYG mode toggle, preview pane

#### 3.4. edit and autosave a block

**File:** `e2e/resume/edit-block.spec.ts`

**Steps:**
  1. In editor, click an existing block (e.g. 项目经验) and type new content
    - expect: Save indicator shows '保存中…' then '已保存'
    - expect: No console errors
  2. Reload the page
    - expect: Edit persisted

#### 3.5. add new block

**File:** `e2e/resume/add-block.spec.ts`

**Steps:**
  1. In editor, click + 新增 block button
    - expect: Block-type picker (经历/项目/技能/自定义) appears
  2. Choose type '自定义' and name '开源贡献'
    - expect: New block appears in editor and is persisted after reload

#### 3.6. switch editor mode (Quick <-> WYSIWYG)

**File:** `e2e/resume/mode-switch.spec.ts`

**Steps:**
  1. In editor, toggle Quick/WYSIWYG mode switch
    - expect: Editor swaps without data loss
    - expect: Save indicator shows '已保存'

#### 3.7. resume import modal

**File:** `e2e/resume/import-modal.spec.ts`

**Steps:**
  1. From /resume, click 导入简历
    - expect: ImportModal opens with file picker (PDF/DOCX/MD)
  2. Upload a non-supported file (e.g. .exe)
    - expect: Error message '不支持的文件类型' displayed

#### 3.8. AI optimize panel

**File:** `e2e/resume/ai-optimize.spec.ts`

**Steps:**
  1. In editor, open AI Optimize panel for a block
    - expect: Panel shows streaming suggestions
  2. Click '采纳' on a suggestion
    - expect: Suggestion merged into block content
    - expect: Save indicator '已保存'

#### 3.9. resume export menu

**File:** `e2e/resume/export.spec.ts`

**Steps:**
  1. From /resume or editor, open Export menu
    - expect: Menu lists PDF / Markdown / JSON options
  2. Choose PDF export
    - expect: PDF download triggers or new tab opens

#### 3.10. offline banner shows when network lost

**File:** `e2e/resume/offline-banner.spec.ts`

**Steps:**
  1. In editor, throttle network to offline
    - expect: OfflineBanner appears
    - expect: Edits queue to outbox; save indicator shows '离线'
  2. Re-enable network
    - expect: Banner clears, queued edits flush successfully

### 4. interview

**Seed:** `e2e/seed.spec.ts`

#### 4.1. interview list shows past sessions

**File:** `e2e/interview/list.spec.ts`

**Steps:**
  1. Navigate to /interview
    - expect: List of past sessions with status chips (已完成/进行中/异常)
    - expect: 点击行可查看报告 / 继续面试 depending on status

#### 4.2. start new interview happy path

**File:** `e2e/interview/new-happy.spec.ts`

**Steps:**
  1. Navigate to /interview/new
    - expect: Setup form shows resume selector, target role, difficulty, language toggles
  2. Select a primary resume, choose role=后端工程师, difficulty=中级, language=中文
    - expect: Submit enabled
  3. Click 开始模拟面试
    - expect: Navigates to /interview/:id/live
    - expect: First question streams in
    - expect: ProgressBar shows question 1/N

#### 4.3. submit answer and receive score

**File:** `e2e/interview/submit-answer.spec.ts`

**Steps:**
  1. In live interview, type an answer and click 提交
    - expect: ScoreDisplay shows score 0-100 and brief feedback
    - expect: Next question auto-streams (or button to continue)

#### 4.4. interview completes and shows report

**File:** `e2e/interview/report.spec.ts`

**Steps:**
  1. Finish all questions or click 完成面试
    - expect: Navigates to /interview/:id/report
    - expect: ReportCard shows overall score, per-question summary, ability delta

#### 4.5. interview error banner on stream failure

**File:** `e2e/interview/error-banner.spec.ts`

**Steps:**
  1. During live interview, simulate WS/stream failure (kill backend)
    - expect: ErrorBanner with 重试 button appears
    - expect: Click 重试 re-attempts the stream

#### 4.6. resume browse during interview

**File:** `e2e/interview/continue-old.spec.ts`

**Steps:**
  1. From /interview list, click an in-progress session
    - expect: Navigates to /interview/:id/live with resumed state (question counter preserved)

#### 4.7. negative: new interview with empty fields blocked

**File:** `e2e/interview/new-validation.spec.ts`

**Steps:**
  1. Navigate to /interview/new with no resumes available
    - expect: Resume selector is required; cannot submit
    - expect: Empty form shows validation message

### 5. ability-profile

**Seed:** `e2e/seed.spec.ts`

#### 5.1. ability profile radar renders

**File:** `e2e/ability-profile/radar.spec.ts`

**Steps:**
  1. Navigate to /ability-profile
    - expect: RadarChart with 6 axes (e.g. 算法/系统设计/沟通/工程/产品/英语) renders
    - expect: AbilityCards listed below with current score and trend

#### 5.2. drill into a single ability

**File:** `e2e/ability-profile/detail.spec.ts`

**Steps:**
  1. Click on an ability card or radar vertex
    - expect: Navigates to /ability-profile/:abilityKey
    - expect: TimelineChart shows score history points (interview events, error resolutions)

#### 5.3. empty ability profile for new user

**File:** `e2e/ability-profile/empty.spec.ts`

**Steps:**
  1. Log in with brand-new account, navigate to /ability-profile
    - expect: Radar renders with all axes at 0
    - expect: Hint: 完成模拟面试或标记错题以填充能力图谱

#### 5.4. share ability profile

**File:** `e2e/ability-profile/share.spec.ts`

**Steps:**
  1. Click 分享 button on /ability-profile
    - expect: ShareDialog opens with toggle for shareToken generation
  2. Enable sharing and copy link
    - expect: Link /shared/:shareToken is generated and accessible in incognito (no auth)
  3. Toggle off sharing
    - expect: Share link returns 404 or '已撤销'

#### 5.5. export ability profile

**File:** `e2e/ability-profile/export.spec.ts`

**Steps:**
  1. Click 导出 on /ability-profile
    - expect: Menu with PNG / JSON options
  2. Choose PNG
    - expect: PNG download triggers

### 6. profile

**Seed:** `e2e/seed.spec.ts`

#### 6.1. profile shows user info and avatar

**File:** `e2e/profile/profile-happy.spec.ts`

**Steps:**
  1. Navigate to /profile
    - expect: Avatar component renders (initial fallback if no upload)
    - expect: Email + display name shown
    - expect: Joined date shown

#### 6.2. upload avatar

**File:** `e2e/profile/avatar-upload.spec.ts`

**Steps:**
  1. Click avatar or 编辑头像 button, choose a valid PNG/JPG <2MB
    - expect: Preview shown immediately
    - expect: On save, avatar updated across topbar/dashboard/profile/sidebar
  2. Try uploading a 10MB image
    - expect: Error: 文件过大 (>2MB)

#### 6.3. edit display name

**File:** `e2e/profile/display-name.spec.ts`

**Steps:**
  1. In /profile, edit 姓名 field and save
    - expect: Display name persisted and reflected in topbar
  2. Try to save empty display name
    - expect: Validation error: 姓名不能为空 (or allowed to be empty per spec)

#### 6.4. ability update status indicator

**File:** `e2e/profile/ability-status.spec.ts`

**Steps:**
  1. Trigger an interview completion and check /profile AbilityUpdateStatus
    - expect: Shows last-updated timestamp and '能力画像已更新' toast/banner
