---
req_id: REQ-034-US9
title: E2E coverage for v2 content editing (10 section dialogs + basics + picture + custom section)
status: locked
round: 1
locked_at: 260629 2420
locked_by: negotiation
negotiation_rounds: 1
parent_spec: specs/034-v2-reactive-resume-parity/spec.md
scope_cast: "US9 = 1 个新 E2E spec 文件 tests/e2e/034-v2-content-editing.spec.ts 覆盖 US1-US6 + US7 内容编辑能力; 不重复 032-v2-mvp 已覆盖场景; 不改 backend / 不改前端组件"
moderation_log: "Round 1 (negotiation): tester 14 反例 (5 blocker / 5 major / 4 minor) → main-agent 14/14 接受 (3 部分接受含范围 cast) → 跳过 dev round 2 直接锁定 (L007 token 风险 + US5/6/7/8 precedent) → 14 修订编码 Phase 2 Implementation Spec 段"
---

# Acceptance Matrix for REQ-034-US9 — E2E coverage for v2 content editing

## SC Gaps

- spec.md (US9 段) 描述"add `tests/e2e/034-v2-content-editing.spec.ts` covering all 10 section dialogs + basics form + picture + custom section"。spec 未列 10 dialog 具体名称 + 各自 success criteria；下表来源以 spec §"User Story US9" 隐含 + 实际 `src/modules/resume/v2/editor/dialogs/` 盘点。
- **范围澄清（避免 US8 陷阱）**：
  - US9 **不**新增功能，**不**改 backend，**不**改前端组件
  - US9 = **1 个新 E2E spec 文件** `tests/e2e/034-v2-content-editing.spec.ts`
  - **不重复** 032-v2-mvp 已覆盖场景：创建 resume + 选 Onyx 模板 + 打开 builder + 3-panel render + Undo/Redo + PDF export
  - 复用 032-v2-mvp 的 `loginAsDemo` + `isBackendUp` + dev-server skip pattern
- **范围 cast（实际 13 个 dialog / 13+2 个 item 类型）**：
  - US1: BasicsDialog + PictureDialog (2)
  - US2: ExperienceDialog (1)
  - US3: EducationDialog + ProjectsDialog + SkillsDialog (3)
  - US4: ProfileDialog (1)
  - US5: LanguageDialog + InterestsDialog + AwardsDialog + CertificationsDialog + PublicationsDialog + VolunteerDialog + ReferencesDialog (7)
  - US6: CustomSectionDialog + CustomItemDialog (2)
  - US7: 不新增 dialog（info-panel 范围已 ship 在 032-v2-mvp 032 路径外，本 US9 不覆盖）
- **关键阻塞（dev Phase 2 必须解决）**：
  - **US5 7 个 dialog 缺 data-testid**：`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/LanguageDialog.tsx` 等 7 个文件全部 0 hits
  - **CustomItemDialog 有 testid**（custom-item-{idx}-key/value/remove），但 CustomSectionDialog items 列表也用 pattern `custom-item-edit-{itId}`
  - **ProfileDialog** 部分 testid 已 ship（profile-network/username/website-url/cancel）
  - **Education/Projects/Skills** 全部 testid 已 ship（完整覆盖 create + reorder + cancel）
  - **Experience** 完整 testid 已 ship（含 role reorder test triggers）
  - **Basics + Picture** 完整 testid 已 ship（custom-fields + file-input + url + border-color）

## AC 矩阵

| AC-ID | 类型 | 描述 | 验证方式 | 期望结果 | 来源 |
|-------|------|------|----------|----------|------|
| AC-01 | static | **spec 文件存在 + 不重叠 032** — `tests/e2e/034-v2-content-editing.spec.ts` 文件创建；不复制 032-v2-mvp 已覆盖的 create-resume / Onyx-template / 3-panel-render / Undo-Redo / PDF-export 5 个场景；直接 reuse `loginAsDemo` + `isBackendUp` pattern | (1) `ls tests/e2e/034-v2-content-editing.spec.ts` 期望 1 hit；(2) `grep -c "describe\|test(" tests/e2e/034-v2-content-editing.spec.ts` 期望 ≥ 13 test blocks（13 dialog 场景）+ ≥ 1 helper；(3) 静态断言 `grep -c "create a v2 resume" tests/e2e/034-v2-content-editing.spec.ts` 期望 0 hits（不重 032 MVP create 路径），仅复用 `loginAsDemo` | 1 新 spec + 13+ test cases + 不与 032 MVP 重复 | SC-9A + spec scope + 032 范围避让 |
| AC-02 | happy | **Basics form 完整 CRUD (US1)** — 打开 section-row-basics → BasicsDialog 显示 → 改 name/email/phone/url/summary → Save → `PATCH /api/v1/v2/resumes/{id}` 200 + body 含新值 → 刷新后值保留（reload + 重新 PATCH 后 GET 不变） | (1) `git grep -c 'basics-' src/modules/resume/v2/editor/dialogs/BasicsDialog.tsx` 期望 ≥ 10 hits（testid 完整）；(2) E2E step `await page.getByTestId('section-row-basics').click()` → `expect(page.getByTestId('basics-dialog')).toBeVisible()` → fill name/email/phone/url/summary → click save → 拦截 `page.waitForResponse(/\/api\/v1\/v2\/resumes\/[a-f0-9-]+/)` 期望 200；(3) reload page + 重新 open dialog → 期望值 == 上次填入 | BasicsDialog 完整 CRUD + 持久化 | US1 spec + BasicsDialog.tsx testid 盘点 |
| AC-03 | happy | **Picture picker 上传图片 (US1)** — 打开 section-row-picture → PictureDialog 显示 → `page.locator('[data-testid="picture-file-input"]').setInputFiles('tests/e2e/_fixtures/sample-avatar.png')` → Save → PATCH 200 + `picture.url` 含 `/uploads/` 或 `data:` URI prefix → reload 后 picture.url 保留 | (1) `ls tests/e2e/_fixtures/sample-avatar.png` 期望 1 hit（fixture 已 ship）；(2) E2E step `await page.getByTestId('section-row-picture').click()` → `setInputFiles` → save → intercept PATCH 期望 200；(3) reload + open picture dialog → 期望 `picture-url` input value 非空 + 包含 fixture 内容 hash 或 upload 路径 | Picture upload 完整 + 持久化 | US1 spec + PictureDialog.tsx picture-file-input testid |
| AC-04 | happy | **Experience item create + roles reorder (US2)** — open experience-section-list → click `experience-add-item` → ExperienceDialog 显示 → fill company/position/period/description → add 2 个 role → reorder 第一个 role 到第二位 → Save → PUT 200 + body.data.sections.experience.items[*].roles 顺序变更 | (1) `git grep -c 'experience-' src/modules/resume/v2/editor/dialogs/ExperienceDialog.tsx src/modules/resume/v2/editor/left/ExperienceSectionList.tsx` 期望 ≥ 25 hits（testid 完整含 reorder triggers）；(2) E2E step fill company + position + period + description + 2 roles → click `experience-test-reorder-r1-r2` (test reorder trigger 已 ship) → save → intercept PUT 期望 200；(3) response body data.sections.experience.items[0].roles[0].position == 第二个 role 的 position（reorder 生效） | Experience create + roles reorder + 持久化 | US2 spec + ExperienceDialog testid + reorder triggers |
| AC-05 | happy | **Education item create (US3)** — open education-section-list → click `education-add-item` → EducationDialog 显示 → fill school/degree/area/period/score → Save → PATCH 200 + education.items[*] 含新 row | (1) `git grep -c 'education-' src/modules/resume/v2/editor/dialogs/EducationDialog.tsx src/modules/resume/v2/editor/left/EducationSectionList.tsx` 期望 ≥ 15 hits；(2) E2E step fill school + degree + area + period + score → save → intercept PATCH 200；(3) response body 含 `sections.education.items[0].school == "TEST_SCHOOL"` | Education create + 持久化 | US3 spec + EducationDialog testid |
| AC-06 | happy | **Project item create (US3)** — open projects-section-list → click `projects-add-item` → ProjectsDialog 显示 → fill name/period/url/description + 1 highlight → Save → PATCH 200 + projects.items[*] 含新 row | (1) `git grep -c 'projects-' src/modules/resume/v2/editor/dialogs/ProjectsDialog.tsx src/modules/resume/v2/editor/left/ProjectsSectionList.tsx` 期望 ≥ 15 hits；(2) E2E fill name + period + url + 1 highlight → save → intercept PATCH 200；(3) response 含 `sections.projects.items[0].highlights[0] == "TEST_HIGHLIGHT"` | Project create + highlights + 持久化 | US3 spec + ProjectsDialog testid |
| AC-07 | happy | **Skill item create + keywords (US3)** — open skills-section-list → click `skills-add-item` → SkillsDialog 显示 → fill name + level + 2 keywords → Save → PATCH 200 + skills.items[*].keywords 数组含 2 个新 keyword | (1) `git grep -c 'skills-' src/modules/resume/v2/editor/dialogs/SkillsDialog.tsx src/modules/resume/v2/editor/left/SkillsSectionList.tsx` 期望 ≥ 15 hits；(2) E2E fill name + level(3) + 2 keywords → save → intercept PATCH 200；(3) response 含 `sections.skills.items[0].keywords == ["k1", "k2"]` | Skill create + keywords + 持久化 | US3 spec + SkillsDialog testid |
| AC-08 | happy | **Profile item create + icon picker (US4)** — open profile-section-list → click `profile-add-item` → ProfileDialog 显示 → click `profile-icon-picker-trigger` → picker 弹出 → 选 `GitHub` icon → fill network/username/url → Save → PATCH 200 + profile.items[*].icon == "github" | (1) `git grep -c 'profile-' src/modules/resume/v2/editor/dialogs/ProfileDialog.tsx src/modules/resume/v2/editor/left/ProfileSectionList.tsx` 期望 ≥ 25 hits（icon picker 已 ship）；(2) E2E click trigger → 选 GitHub icon → fill network="GitHub" + username + url → save → intercept PATCH 200；(3) response 含 `sections.profiles.items[0].icon == "github"` + `network == "GitHub"` | Profile create + icon picker + 持久化 | US4 spec + ProfileDialog icon-picker testid |
| AC-09 | happy | **Language item create (US5) — [AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]** — open languages section → add new language item → fill language/fluency/level → Save → PATCH 200 + languages.items[*] 含新 row | (1) **`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/LanguageDialog.tsx` 当前期望 0 hits** — **dev Phase 2 必加 testid**: `language-dialog` + `language-name` + `language-fluency` + `language-level` + `language-level-input` + `language-cancel` + `language-hidden`（参考 SkillsDialog 同字段模式）；(2) E2E step (dev 加 testid 后) fill language + fluency + level(3) → save → intercept PATCH 200；(3) response 含 `sections.languages.items[0].name == "TEST_LANG"` | Language create + 持久化（受 US5 dialog testid 阻塞） | US5 spec + LanguageDialog 缺 testid 阻塞 |
| AC-10 | happy | **Interest item create (US5) — [AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]** — open interests section → add new interest → fill name + 2 keywords → Save → PATCH 200 + interests.items[*].keywords 数组 | (1) **`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/InterestsDialog.tsx` 当前期望 0 hits** — dev 必加 testid: `interests-dialog` + `interests-name` + `interests-keywords` + `interests-keywords-add` + `interests-keywords-empty` + `interests-keywords-list` + `interests-keyword-input-{idx}` + `interests-keyword-remove-{idx}` + `interests-cancel` + `interests-hidden`（参考 SkillsDialog keywords 同模式）；(2) E2E fill name + 2 keywords → save → intercept PATCH 200；(3) response 含 `sections.interests.items[0].keywords == ["k1", "k2"]` | Interest create + keywords + 持久化（受 US5 dialog testid 阻塞） | US5 spec + InterestsDialog 缺 testid 阻塞 |
| AC-11 | happy | **Award item create (US5) — [AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]** — open awards section → add new award → fill title/awarder/date/url + description → Save → PATCH 200 + awards.items[*] 含新 row | (1) **`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/AwardsDialog.tsx` 当前期望 0 hits** — dev 必加 testid: `awards-dialog` + `awards-title` + `awards-awarder` + `awards-date` + `awards-website-url` + `awards-website-label` + `awards-website-inline-link` + `awards-description` + `awards-cancel` + `awards-hidden`；(2) E2E fill title + awarder + date + url + description → save → intercept PATCH 200；(3) response 含 `sections.awards.items[0].title == "TEST_AWARD"` | Award create + 持久化（受 US5 dialog testid 阻塞） | US5 spec + AwardsDialog 缺 testid 阻塞 |
| AC-12 | happy | **Certification item create (US5) — [AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]** — open certifications section → add new cert → fill name/issuer/date/url → Save → PATCH 200 | (1) **`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/CertificationsDialog.tsx` 当前期望 0 hits** — dev 必加 testid: `certifications-dialog` + `certifications-name` + `certifications-issuer` + `certifications-date` + `certifications-website-url` + `certifications-website-label` + `certifications-website-inline-link` + `certifications-cancel` + `certifications-hidden`；(2) E2E fill + save → intercept PATCH 200；(3) response 含 `sections.certifications.items[0].name == "TEST_CERT"` | Certification create + 持久化（受 US5 dialog testid 阻塞） | US5 spec + CertificationsDialog 缺 testid 阻塞 |
| AC-13 | happy | **Publication item create (US5) — [AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]** — open publications section → add new pub → fill name/publisher/date/url/summary → Save → PATCH 200 | (1) **`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/PublicationsDialog.tsx` 当前期望 0 hits** — dev 必加 testid: `publications-dialog` + `publications-name` + `publications-publisher` + `publications-date` + `publications-website-url` + `publications-website-label` + `publications-website-inline-link` + `publications-summary` + `publications-cancel` + `publications-hidden`；(2) E2E fill + save → intercept PATCH 200；(3) response 含 `sections.publications.items[0].name == "TEST_PUB"` | Publication create + 持久化（受 US5 dialog testid 阻塞） | US5 spec + PublicationsDialog 缺 testid 阻塞 |
| AC-14 | happy | **Volunteer item create (US5) — [AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]** — open volunteer section → add new → fill organization/position/startDate/endDate/summary → Save → PATCH 200 | (1) **`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/VolunteerDialog.tsx` 当前期望 0 hits** — dev 必加 testid: `volunteer-dialog` + `volunteer-organization` + `volunteer-position` + `volunteer-period` + `volunteer-website-url` + `volunteer-website-label` + `volunteer-website-inline-link` + `volunteer-summary` + `volunteer-cancel` + `volunteer-hidden`；(2) E2E fill + save → intercept PATCH 200；(3) response 含 `sections.volunteer.items[0].organization == "TEST_ORG"` | Volunteer create + 持久化（受 US5 dialog testid 阻塞） | US5 spec + VolunteerDialog 缺 testid 阻塞 |
| AC-15 | happy | **Reference item create (US5) — [AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]** — open references section → add new → fill name/description/phone/email → Save → PATCH 200 | (1) **`git grep -l 'data-testid' src/modules/resume/v2/editor/dialogs/ReferencesDialog.tsx` 当前期望 0 hits** — dev 必加 testid: `references-dialog` + `references-name` + `references-description` + `references-phone` + `references-email` + `references-cancel` + `references-hidden`；(2) E2E fill + save → intercept PATCH 200；(3) response 含 `sections.references.items[0].name == "TEST_REF"` | Reference create + 持久化（受 US5 dialog testid 阻塞） | US5 spec + ReferencesDialog 缺 testid 阻塞 |
| AC-16 | happy | **Custom section create + items (US6)** — open SectionsPanel 底部 add custom section → CustomSectionDialog 显示 → fill title + icon + type + items 数组 → Save → PATCH 200 + sections.custom[*] 含新 section | (1) `git grep -c 'custom-' src/modules/resume/v2/editor/dialogs/CustomSectionDialog.tsx` 期望 ≥ 20 hits（testid 完整）；(2) E2E fill title + icon + 2 items → save → intercept PATCH 200；(3) response 含 `sections.custom[*]` 新 section + items 数组非空 | Custom section create + items + 持久化 | US6 spec + CustomSectionDialog testid |
| AC-17 | static | **范围澄清（non-goals 显式 cast 死）** — US9 spec 范围 = 13 dialog E2E 覆盖（basics/picture + 10 section + custom）+ 0 backend 改动 + 0 frontend 组件改动。**不在范围**：(a) PDF export 验证（已在 032-v2-mvp 覆盖）；(b) Tiptap 编辑器内部实现验证（仅 black-box input/output）；(c) Drag-drop 鼠标轨迹验证（用 test-reorder triggers 代替）；(d) US7 info-panel (已 ship 032 路径外)；(e) Template gallery + 3-panel render（已在 032-v2-mvp） | US9 dev report 显式 cast 13 dialog 范围 + 5 non-goals | non-goals 显式 cast 死 | spec out-of-scope + 032 范围避让 |
| AC-18 | edge | **dev-server skip pattern 复用** — 沿用 032-v2-mvp 的 `isBackendUp` + `test.beforeAll` skip 模式：backend 或 frontend 不可达时 spec self-skip 不阻塞 dev machine 测试套件（per L004 quota-safety） | (1) `grep -c 'isBackendUp\|test.skip' tests/e2e/034-v2-content-editing.spec.ts` 期望 ≥ 2 hits；(2) `grep -c 'FRONTEND_BASE\|BACKEND_BASE' tests/e2e/034-v2-content-editing.spec.ts` 期望 ≥ 2 hits（env override pattern） | skip pattern 完整复用 | L004 quota-safety + 032 pattern |

## 起草说明（写给 tester）

**设计意图**：

- **范围严格修正**：spec US9 描述"covering all 10 section dialogs + basics form + picture + custom section"。实际盘点 = 2 (US1) + 1 (US2) + 3 (US3) + 1 (US4) + 7 (US5) + 1 (US6) = **15 个 dialog**（spec 隐含 10 section + 2 single + custom 实际 13；本 AC cast 死 = **13 个独立 test case** 因为 US5 7 个 dialog 共享 list/add button pattern 但每个 dialog 是独立 testid surface）。
- **关键阻塞 — US5 dialog 缺 testid**（AC-09 ~ AC-15）：当前 US5 7 个 dialog 全部 0 data-testid hit，**E2E spec 无法稳定定位 input / save 按钮**。AC-09~AC-15 显式标记 `[AC REQUIRES TESTID TXXX — DEV PHASE 2 必加]`，dev 实施时按 SkillsDialog 同模式补全（`{section}-dialog` + `{section}-{field}` + `{section}-cancel` + `{section}-hidden`）。
- **tester 红队未跑**（本轮为 ac-draft）：tester red-team 阶段会从 13 dialog 字段完整性 / setDataMut rollback / network race / RLS 跨用户 / 编辑冲突 等维度出反例。本 ac-draft 只 cast 范围 + 静态 grep + happy-path success criteria。
- **不重复 032-v2-mvp**：复用 `loginAsDemo` + `isBackendUp` + dev-server skip pattern。**不**重写创建 resume 流程 — 032-v2-mvp US1 已 ship happy path（create resume + 进入 editor），US9 直接 `await loginAsDemo(page)` 后 `await page.goto(\`${FRONTEND_BASE}/resume/v2/${existingResumeId}\`)` 复用现有 resume fixture。
- **复用 032 已 ship testid**（testid 锁定 by Batches 1-3）：`sections-panel` + `section-row-{id}` + `panel-*` + `v2-editor` 等 editor shell testid 全在 032 spec 注释里锁定，US9 不重新发现直接用。
- **E2E 网络拦截模式**：`page.waitForResponse(/\/api\/v1\/v2\/resumes\/[a-f0-9-]+/)` 期望 200，避免 time-based race（per [us1_e2e_test_runs] L008 / [v2_032_e2e_test_runs] L009 PUT-refetch race 教训）。
- **MCP PG 落库验证可选**：AC-02 ~ AC-16 全部用 `waitForResponse` 验证 PATCH 200 + body shape；DB 落库由 backend US8 (ship-readiness) 验证（per [feedback_postgres_mcp_validation]），E2E 不重复查 DB。
- **关键风险**：US5 7 个 dialog 补 testid 是 dev Phase 2 必做前置；如果 dev 不补，**AC-09 ~ AC-15 必须标记 DEFERRED**，整个 US9 退化为"只覆盖 US1-US4 + US6 = 8 个 dialog"的子集。

## Tester 反驳日志

### R1 — scope creep — US5 dialog testid 添加不属于 US9
**反例**: AC-09~AC-15 验证方式第一段直接列出「dev Phase 2 必加 testid: language-dialog + language-name + ...」共 70 个 testid attribute。**US9 是「E2E coverage」不是「测试基础设施补全」**——testid 添加属于 US1/US5 的实施 dev task，应在各自 US 的 spec/tasks 里追踪。
**风险**: 把 US5 dialog 的 dev 实施工作（添加 ~70 testid）伪装成「AC 验证动作」= 偷换 scope。若 dev 不补 testid，AC 矩阵直接退化 7 行，整 US9 scope 不可锁定。
**建议**: 把 AC-09~AC-15 改写为「AC 条件性可执行」——前置条件 = 「dev 在 US5 spec 已 ship testid（独立 TXXX 任务）」；AC 验证方式只描述「假设 testid 存在时的 E2E 步骤」，并在 AC 表头加一行 `前置依赖: TXXX (US5 testid hardening) — 未完成则 AC 标记 DEFERRED, 不阻塞 US9 锁定」。

### R2 — 重复造轮子 — loginAsDemo / isBackendUp pattern 应在 AC-01 显式 cast 范围
**反例**: AC-01 写「reuse `loginAsDemo` + `isBackendUp` pattern」但未声明是 import 复用 032-v2-mvp.spec.ts:67 / 76 的 helper，还是在新 spec 里复制粘贴。dev 起草报告说「不重写创建 resume 流程 — 032-v2-mvp US1 已 ship happy path」但 AC-01 第三步断言 `grep -c "create a v2 resume" ... = 0` 只排除 create 步骤，没显式排除 page.goto + dialog 启动流程。
**风险**: helper 被复制粘贴 → 032 改 helper 时 US9 spec 漏改 → dev-server skip pattern 双源失同步。
**建议**: AC-01 验证方式 (1) 加 `grep -c "import.*from.*032-v2-mvp" tests/e2e/034-v2-content-editing.spec.ts 期望 ≥ 2 hits`（强制 import 复用，禁止拷贝）。

### R3 — 缺失 case — 跨 section 拖拽 reorder (US2) AC-04 不充分
**反例**: AC-04 写「add 2 个 role → reorder 第一个 role 到第二位」只覆盖 **Experience item 内 roles[] 拖拽**。spec §US2 同时要求 `dialogs/.../experience.tsx` + `left/sections/experience.tsx` 双向（item 级 + role 级）。AC-04 完全漏了 **section-item 拖拽 reorder（多个 experience item 之间的顺序调整）**，这正是 reactive-resume parity 验证报告里点名的「UI only exposes section metadata」反向补全证据。
**风险**: US2 验收只看 role reorder，item 拖拽漏测 → dev 实现若只 ship role reorder 不 ship item reorder → spec US2 部分达成但 E2E 报告说「全过」。
**建议**: AC-04 拆为 AC-04a（role reorder）+ AC-04b（experience items 拖拽 reorder），后者验证方式：(1) `git grep -c 'experience-item-reorder\|experience-section-drag' left/ExperienceSectionList.tsx` ≥ 4 hits；(2) E2E 创建 2 个 experience item → 拖第二个到第一个之前 → PATCH 200 → body.sections.experience.items 顺序反转。

### R4 — 缺失 case — Education/Project/Skill 的 item reorder 整段缺失
**反例**: AC-05 / AC-06 / AC-07 全是「create 一个 item + PATCH 200」，**完全没覆盖 item 之间拖拽 reorder**。reactive-resume `left/sections/{education,project,skill}.tsx` 都有 `SectionItem` drag-handle。如果 US3 验收只看 create，US3 拖拽能力漏测。
**风险**: US3 dev 若只 ship dialog 不 ship item reorder → spec US3 「拖拽能力」半成品，E2E 报告误判 PASS。
**建议**: AC-05 / AC-06 / AC-07 各加 1 条 sub-AC：创建 2 个 item → 拖第二个到第一个之前 → 验证 PATCH 200 + items 数组顺序反转。

### R5 — 缺失 case — 必填项验证 / 错误输入 / 非法 URL
**反例**: 13 个 dialog AC 全部 happy-path（fill + save + 200），**没有任何一条覆盖必填项空提交 / 非法 URL (mailto: / javascript:) / 超长字符串 (>10K char) / XSS payload in summary**。
**风险**: spec §US1/US2 提到 `RichTextEditor` 复用 react-quill → summary / description 字段是 XSS 高危面。如果 US9 spec 全是 happy-path，XSS / 必填校验 / 超长截断这些 case 全靠 backend 兜底，E2E 完全黑盒不到。
**建议**: 新增 AC-19 (edge / negative case): 对每个 dialog 跑 (a) save-without-required-field 期望 inline error + dialog 不关闭 + **不发 PATCH**; (b) URL 字段输入 `javascript:alert(1)` 期望表单拒绝或 sanitize; (c) summary 字段输入 `<script>alert(1)</script>` + 2000 字，期望 PATCH 200 + reload 后渲染无 script 执行（用 page.on('dialog') 监听 alert）。

### R6 — 不可测 AC — AC-16 Custom section「items 数组非空」无具体断言
**反例**: AC-16 验证方式 (3) 写「response 含 `sections.custom[*]` 新 section + items 数组非空」——「非空」是模糊断言，没指定 items 长度 / 内容 / 字段 schema。
**风险**: dev 写 `items: []` + PATCH 200 → AC-16 误判 PASS。custom section 是 US6 唯一可写 schema，items schema 不锁 = US6 验收漏水。
**建议**: AC-16 改为具体断言：(3) `response.sections.custom[0].items.length == 2` + `items[0].key == "TEST_KEY_1"` + `items[0].value` 含输入字符串 + `items[0].id` 非空 UUID。

### R7 — 集成点 4 surface — 13 个 dialog AC 全缺「刷新后持久化」后半段
**反例**: AC-02 / AC-04~AC-16 验证方式都是 (1) grep testid (2) E2E fill + PATCH 200 (3) response body shape。**只有 AC-02 第三步显式 reload + 重新 open 验证持久化**（行 42）——其余 12 个 AC 第三步只看 response body，**完全不验证 reload 后页面值保留**。Per [feedback_dialoghost_integration_4surface]，dialog 关闭后必须 4 集成点全覆盖：DialogType union / switch case / SectionsPanel mount / backend PATCH 200 / **刷新页面持久化**。
**风险**: 若 dev 实现 setDataMut 仅更新 store 不触发 PATCH（debounce 500ms 内关闭页面）→ response 200 但 reload 丢数据 → 静默丢内容。
**建议**: AC-04 ~ AC-16 第三步统一加：`await page.reload() + waitForResponse(GET /api/v1/v2/resumes/{id}) + reopen dialog + 期望 input value == 上次填入值`。

### R8 — 集成点 4 surface — 缺 store 状态 + SectionsPanel mount 实时刷新验证
**反例**: 13 个 AC 全是「PATCH 200 + body」验证。**无一条验证 PATCH 200 后 store 是否实时反映到 SectionsPanel 列表**（即左侧 section item list 是否多出新 row）。dialog 关闭 → store 更新 → SectionsPanel mount 重渲染 是 dialog 集成的第三个 surface。
**风险**: dev 仅 PATCH 但 store 没调 setDataMut → PATCH 200 + reload 后数据在，但 dialog 关闭后左侧 list 不刷新，用户体感「保存了但列表没显示」。
**建议**: AC-02~AC-16 各加 1 sub-step：save 后 `expect(page.getByTestId('{section}-item-row-{n}')).toBeVisible()` 不需 reload。

### R9 — 不可测 AC — AC-17 「non-goals 显式 cast 死」是声明不是 AC
**反例**: AC-17 类型标 `static`，验证方式写「US9 dev report 显式 cast 13 dialog 范围 + 5 non-goals」——验证动作是读 dev report，不是 grep / E2E / 命令。**这是元声明（meta-claim），不是可执行 AC**。任何 dev 都可以在 report 里写「我 cast 死 13 dialog」然后 AC-17 永远 PASS。
**风险**: non-goals 锁不住 → dev 在 Phase 2 加 drag-drop 测试 / PDF 二次验证 / Tiptap editor E2E → scope creep 无 AC 拦截。
**建议**: AC-17 改为 (1) `grep -c "PDF\|tiptap\|drag" tests/e2e/034-v2-content-editing.spec.ts` 期望 0 hits（PDF / Tiptap / 鼠标轨迹不出现）；(2) `grep -c "describe.*TemplateGallery\|describe.*Export\|describe.*info-panel" tests/e2e/034-v2-content-editing.spec.ts` 期望 0 hits（不重 032 路径）。

### R10 — 不可测 AC — AC-18 「dev-server skip pattern 复用」是模式检查不是行为验证
**反例**: AC-18 验证方式只 grep `isBackendUp\|test.skip` ≥ 2 hits + `FRONTEND_BASE\|BACKEND_BASE` ≥ 2 hits。**这是静态 grep 不验证 skip 行为真实生效**。如果 dev 写 `function isBackendUp() { return true }` → grep 命中但 dev machine 不可达时仍跑测试 → quota 烧光（L004 风险）。
**风险**: skip pattern 形式存在但行为不真 → L004 quota-safety 失效。
**建议**: AC-18 加 E2E 行为验证：`test('dev-server skip pattern actually skips when backend down', async ({ page }) => { process.env.BACKEND_BASE = 'http://localhost:1' (不可达); ...test.skip handler triggered → test.info().status === 'skipped' })`。

### R11 — 缺失 case — 并发编辑 / 同 resume 两 tab / 撤销-重做 interaction
**反例**: 18 条 AC 全是单 tab 单操作流。spec §US17 (= 032 US17) 提到 Undo/Redo，但 **dialog 操作触发 undo stack 后再 reload 是否丢内容？** **同 resume 两 tab 编辑的 last-write-wins 行为？** 没任何 AC 覆盖。
**风险**: 032 US17 已 ship Undo/Redo 但 US9 dialog 与 undoStack 集成未验证 → undo 后 PATCH 是否回滚 → 用户按 Ctrl+Z 后发现远端已被 PATCH 修改。
**建议**: 新增 AC-20 (concurrent edit): (a) open resume in page1 + page2 → page1 dialog save → page2 reload → 期望 page2 显示 page1 新值 (last-write-wins) 或冲突提示; (b) dialog save → Ctrl+Z → reload → 验证 undo 是否回滚已 PATCH 的内容。

### R12 — scope creep vs 重复造轮子 — AC-01 「13 test blocks」vs 实际盘点 15 dialog
**反例**: AC-01 验证方式 (2) 期望 `grep -c "describe\|test(" ≥ 13 test blocks`；起草说明行 64 又写「实际盘点 = 15 个 dialog ... 本 AC cast 死 = 13 个独立 test case」。**15 vs 13 不一致**：CustomSectionDialog + CustomItemDialog 合并为 1 还是 2？US5 7 个 dialog 是否合并为 1 个 describe block 内 7 个 test？
**风险**: dev 实施时 13 vs 15 摇摆 → AC-01 grep 计数永远存在歧义。
**建议**: AC-01 改为精确：`grep -c "^  test(" tests/e2e/034-v2-content-editing.spec.ts` 期望 == 15（每个 dialog 独立 test）。或者明确合并规则：US5 7 个合并为 1 describe block 内 7 个 test + 13 dialog 全展开 = 描述行 ≥ 13 + test 行 ≥ 7。

### R13 — 不可测 AC — AC-08 icon picker 「选 GitHub icon」无 icon 标识
**反例**: AC-08 写「选 GitHub icon → fill network=GitHub → save → 期望 icon == github」。**用什么 testid 定位 GitHub icon？** 起草报告列 ProfileDialog 部分 testid 已 ship（profile-network/username/website-url/cancel），**没列出 icon picker 内部 icon 元素的 testid**。
**风险**: icon picker 若是 `<div role="button">` 网格（无 testid），E2E 无法稳定点击 GitHub → AC-08 flaky fail。
**建议**: AC-08 验证方式 (1) 加 `git grep -c 'profile-icon-' src/modules/resume/v2/editor/dialogs/ProfileDialog.tsx` 期望 ≥ 15 hits（含每个 icon 的 testid 如 `profile-icon-github` / `profile-icon-linkedin`）。dev 缺则列为 Phase 2 阻塞。

### R14 — 缺失 case — CustomItemDialog (US6) 编辑 / 删除 / 拖拽 完全没列
**反例**: 起草说明行 31 提「CustomItemDialog 有 testid (custom-item-{idx}-key/value/remove)」，但 AC-16 只测 CustomSectionDialog 的 create。**CustomItemDialog 本身的 add item / edit item / delete item / drag-reorder items 完全没单列 AC**。
**风险**: US6 spec 要求「Custom section dialog + per-section design tab」，CustomItemDialog 是 US6 实施的核心组件之一。漏测 = US6 拖拽 / 删除 / 编辑能力 0 E2E 覆盖。
**建议**: AC-16 拆为 AC-16a (CustomSectionDialog create) + AC-16b (CustomItemDialog add/edit/remove/reorder)。

### 判定 MAJOR

US9 AC v1 范围 cast 与 13 dialog 清单基本可用，但 18 行 AC 在 4 surface 集成 / 必填校验 / 持久化 / 并发编辑 / testid 阻塞依赖处理 上系统性漏水。R1（scope creep）、R5（缺失 negative case）、R7（持久化后半段）、R8（store 实时刷新）、R14（CustomItem 漏列）属 blocker 级别——不接受则 US9 进入 Phase 2 后 dev 实施会撞 US5 testid 阻塞 + dialog 集成点不全 + US6 CustomItem 漏测。**锁定前必须 R1 + R5 + R7 + R8 + R14 全部回应**，R2 / R3 / R4 / R6 / R9 / R10 / R11 / R12 / R13 至少在 round 2 修订里给出处理意见。
---

## Moderation Log (Main-agent 裁判, Round 1)

| # | 反例类型 | 标题 | 裁判 | 编码为 Phase 2 硬约束 |
|---|---------|------|------|---------------------|
| R1 | scope creep | US5 dialog testid 添加不属于 US9 | **接受** | 修订 #1: AC-09~AC-15 改「前置依赖 cast」— testid 添加属 US5/6/7 实施任务 (TXXX)，未 ship 则 AC 标 DEFERRED，不阻塞 US9 锁定 |
| R2 | 重复造轮子 | loginAsDemo/isBackendUp import cast | **接受** | 修订 #2: AC-01 加 `grep -c "import.*from.*032-v2-mvp" tests/e2e/034-v2-content-editing.spec.ts` ≥ 2 hits |
| R3 | 缺失 case | 跨 section 拖拽 reorder (US2) AC-04 不充分 | **部分接受** | 修订 #3: AC-04 拆 AC-04a (role reorder) + AC-04b (item reorder); AC-04b 前置依赖 US2 item-drag ship |
| R4 | 缺失 case | Education/Project/Skill item reorder 整段缺失 | **部分接受** | 修订 #4: AC-05/06/07 各加 sub-AC (item reorder); 前置依赖 US3 item-drag ship |
| R5 | 缺失 case | 必填项 / 错误输入 / 非法 URL / XSS | **部分接受** | 修订 #5: 新增 AC-19 (edge/negative); sub-case (c) XSS 完整渗透测属 US10 hardening, US9 仅基本 XSS + 2000 char |
| R6 | 不可测 AC | AC-16 Custom section items 模糊断言 | **接受** | 修订 #6: AC-16 改 length==2 + key + value + id UUID 具体断言 |
| R7 | 集成点 4 surface | 13 dialog AC 全缺「刷新后持久化」 | **接受** | 修订 #7: AC-04~AC-16 第三步统一加 reload + reopen + 验证 input value 保留 |
| R8 | 集成点 4 surface | 缺 store 状态 + SectionsPanel mount 实时刷新 | **部分接受** | 修订 #8: AC-02~AC-16 各加 sub-step `expect(page.getByTestId('{section}-item-row-{n}')).toBeVisible()`; 前置依赖 SectionItem testid ship |
| R9 | 不可测 AC | AC-17 non-goals 声明不是 AC | **接受** | 修订 #9: AC-17 改 grep `PDF\|tiptap\|drag` == 0 hits + `TemplateGallery\|Export\|info-panel` describe == 0 hits |
| R10 | 不可测 AC | AC-18 dev-server skip 模式检查不验证行为 | **接受** | 修订 #10: AC-18 加 E2E 行为验证 — 不可达 BACKEND_BASE 期望 test.skip 触发 |
| R11 | 缺失 case | 并发编辑 / 同 resume 两 tab / undo-redo | **部分接受** | 修订 #11: 新增 AC-20 (last-write-wins only); undo-redo 与已 PATCH 集成属 032 US17 + US10 hardening, US9 不锁 |
| R12 | scope creep vs 重复造轮子 | AC-01「13 test blocks」vs 15 dialog 不一致 | **接受** | 修订 #12: AC-01 改 `grep -c "^  test(" tests/e2e/034-v2-content-editing.spec.ts` == 15; CustomSection + CustomItem 独立 test |
| R13 | 不可测 AC | AC-08 icon picker 选 GitHub icon 无标识 | **接受** | 修订 #13: AC-08 加前置 `git grep -c 'profile-icon-' ProfileDialog.tsx` ≥ 15 hits; dev Phase 2 必加 |
| R14 | 缺失 case | CustomItemDialog add/edit/remove/reorder 漏列 | **接受** | 修订 #14: AC-16 拆 AC-16a (CustomSection create) + AC-16b (CustomItem add/edit/remove/reorder) |

**裁判总览**：14 反例全接受 (3 部分接受含范围 cast)，无驳回。**L007 token 风险 + US5/6/7/8 precedent → 跳过 dev round 2 文件修订直接锁定**，14 修订编码为 Phase 2 Implementation Spec 硬约束。

---

## Phase 2 Implementation Spec (dev 必须按此实施, locked)

> **dev Phase 2 实施 US9 时必须落实以下 14 修订**。每条对应原 AC 行号 + 修订动作。前置依赖 (DEFERRED cast) 在修订文本中显式列出；前置依赖未 ship 时 dev 必须先创建占位 TXXX 任务并显式标 DEFERRED。

### 修订 #1 (R1): AC-09~AC-15 改「前置依赖 cast」
- 原始 AC 写「dev Phase 2 必加 testid」→ 改为「前置依赖: TXXX (US5 testid hardening)」
- AC 验证方式只描述「假设 testid 存在时的 E2E 步骤」
- AC 表头加：`前置依赖: TXXX (US5 testid hardening) — 未完成则 AC 标记 DEFERRED, 不阻塞 US9 锁定`
- dev Phase 2 第一步必跑：`git grep -c 'data-testid' src/modules/resume/v2/editor/dialogs/sections/{language,interest,award,certification,publication,volunteer,reference}.tsx` 报告 7 文件 testid 命中数
- 命中 0 → 创建 TXXX 任务追踪，AC 标 DEFERRED，**不阻塞 US9 锁定**

### 修订 #2 (R2): AC-01 加 import 复用 cast
- AC-01 验证方式 (1) 加：`grep -c "import.*from.*032-v2-mvp" tests/e2e/034-v2-content-editing.spec.ts` 期望 ≥ 2 hits
- 强制 import 复用 helper (loginAsDemo / isBackendUp / dev-server skip), 禁止拷贝粘贴

### 修订 #3 (R3): AC-04 拆 AC-04a/04b
- AC-04a: role reorder (US2 already locked)
- AC-04b: experience items 拖拽 reorder — 新增
- AC-04b 前置依赖: US2 item-drag ship 状态 (dev Phase 2 grep `experience-item-reorder\|experience-section-drag` ≥ 4 hits)
- 未 ship → AC-04b 标 DEFERRED

### 修订 #4 (R4): AC-05/06/07 各加 sub-AC item reorder
- 各加 1 sub-AC: 创建 2 个 item → 拖第二个到第一个之前 → PATCH 200 + items 数组顺序反转
- 前置依赖: US3 item-drag ship 状态 (EducationSectionList / ProjectSectionList / SkillSectionList)
- 未 ship → sub-AC 标 DEFERRED

### 修订 #5 (R5): 新增 AC-19 (edge/negative)
- (a) save-without-required-field → inline error + dialog 不关闭 + 不发 PATCH
- (b) URL 字段输入 `javascript:alert(1)` → 表单拒绝或 sanitize
- (c) summary 字段 `<script>alert(1)</script>` + 2000 char → PATCH 200 + reload 后渲染无 script 执行 (`page.on('dialog')` 监听)
- 完整 XSS 渗透测属 US10 hardening, US9 仅基本 XSS

### 修订 #6 (R6): AC-16 items 模糊断言改具体
- `response.sections.custom[0].items.length == 2`
- `items[0].key == "TEST_KEY_1"`
- `items[0].value` 含输入字符串
- `items[0].id` 非空 UUID

### 修订 #7 (R7): AC-04~AC-16 第三步统一加 reload 持久化
- 末段统一加：`await page.reload() + waitForResponse(GET /api/v1/v2/resumes/{id}) + reopen dialog + 期望 input value == 上次填入值`

### 修订 #8 (R8): AC-02~AC-16 各加 sub-step store 实时刷新
- `save 后 expect(page.getByTestId('{section}-item-row-{n}')).toBeVisible() 不需 reload`
- 前置依赖: SectionItem 列表 testid ship (grep `data-testid.*item-row` in left/ 期望 ≥ 10 hits)
- 未 ship → sub-step 标 DEFERRED

### 修订 #9 (R9): AC-17 non-goals 改 grep 检查
- `grep -c "PDF\|tiptap\|drag" tests/e2e/034-v2-content-editing.spec.ts` 期望 0 hits
- `grep -c "describe.*TemplateGallery\|describe.*Export\|describe.*info-panel" tests/e2e/034-v2-content-editing.spec.ts` 期望 0 hits

### 修订 #10 (R10): AC-18 加 E2E 行为验证
- 新增 test: `dev-server skip pattern actually skips when backend down`
- `process.env.BACKEND_BASE = 'http://localhost:1'` (不可达)
- 期望 `test.info().status === 'skipped'`

### 修订 #11 (R11): 新增 AC-20 (last-write-wins only)
- (a) open resume in page1 + page2 → page1 dialog save → page2 reload → 期望 page2 显示 page1 新值 (last-write-wins) 或冲突提示
- undo-redo 与已 PATCH 集成属 032 US17 + US10 hardening, US9 **不锁**

### 修订 #12 (R12): AC-01 改精确 15 test 计数
- `grep -c "^  test(" tests/e2e/034-v2-content-editing.spec.ts` 期望 == 15
- CustomSectionDialog + CustomItemDialog 独立 test

### 修订 #13 (R13): AC-08 icon picker 加前置 testid grep
- `git grep -c 'profile-icon-' src/modules/resume/v2/editor/dialogs/ProfileDialog.tsx` 期望 ≥ 15 hits
- dev Phase 2 缺 → 创建 TXXX 任务追踪，AC 标 DEFERRED

### 修订 #14 (R14): AC-16 拆 AC-16a/16b
- AC-16a: CustomSectionDialog create
- AC-16b: CustomItemDialog add/edit/remove/reorder — 新增
- AC-16b 前置依赖: CustomItemDialog 拖拽 ship 状态

### 范围 cast 摘要 (locked)
- US9 = 1 个新 E2E spec 文件 `tests/e2e/034-v2-content-editing.spec.ts` (15 个独立 test)
- 不改 backend, 不改前端组件 (testid hardening 任务 dev Phase 2 必扫, 缺则创 TXXX 任务标 DEFERRED)
- 不重复 032-v2-mvp 路径 (login + create + select template + open builder)
- 复用 032-v2-mvp helper (loginAsDemo / isBackendUp / dev-server skip)
- 并发编辑仅 last-write-wins (AC-20a), undo-redo + PATCH 集成属 032/US10 范围
- XSS 完整渗透测属 US10 hardening, US9 仅基本 XSS + 2000 char

