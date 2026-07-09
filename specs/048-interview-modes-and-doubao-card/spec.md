# Feature Specification: Interview Mode Split + Doubao Card Export (REQ-048)

**Feature Branch**: `[048-interview-modes-and-doubao-card]`
**Created**: 2026-07-07
**Status**: Draft
**Input**: User description: "针对模拟面试流程的两点需求：1) 题量不再固定 5 题，支持用户选择「快速补漏（基于错题集+JD 选 5 道最匹配题）」或「完整面试（10-15 题 Agent 自控）」；错题筛选需引入向量检索（Hybrid: BGE embedding + BM25 + LLM rerank）；2) 面试前入口让用户选择「在线面试 / 豆包面试」；选豆包则只跑 Planner，把 JD+计划渲染成 4:3 卡片供截图给豆包。"

## Clarifications

### Session 2026-07-07

- Q: BGE embedding 模型维度冲突（spec 原写 1024 维，bge-small-zh-v1.5 实际 512 维，bge-large-zh-v1.5 才是 1024 维）→ A: 改用 **bge-small-zh-v1.5 (512 维)** — CPU 可跑，模型 ~93MB，对「快速补漏 top-5」场景精度足够；保留 vector(1024) 字段为 v2 升级预留
- Q: 「快速补漏」入口是「在线 AI 面试」下的二级选项，还是与「豆包面试」并列平级？→ A: **二级**（顶层「在线 AI 面试」/「豆包面试」两个并列入口，「快速补漏」与「完整面试」并列于「在线 AI 面试」下）
- Q: BGE 模型部署位置 → A: **本地独立 Python 进程（CPU 跑 bge-small-zh-v1.5 + bge-reranker-v2-m3）**，通过内部 HTTP 被 FastAPI 调用；模型文件存 git LFS；与现有 `app.agents.llm_client` 架构并列但独立部署（不挤占 LLM 配额）。⚠️ **澄清（2026-07-07 实查）**：
  - 本机 `C:\Users\30803\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3` **已下载**（2.27 GB，commit `953dc6f6`），是 **cross-encoder reranker**（XLMRoberta-large 24 层，hidden_size=1024，输入 (query, doc) 输出 1 维 logits）—— 用作精排阶段
  - bge-small-zh-v1.5（embedding 召回）本机**尚未下载**，需补（~93 MB，CPU 可跑）
  - **Hybrid 架构**：BM25（PG `tsvector` GIN 索引，沿用 `0005_phase6_global_capabilities.py` 模式）∪ bge-small-zh-v1.5 cosine top-30 → union 去重 top-50 → **bge-reranker-v2-m3 cross-encoder 精排 top-5**（不调 LLM rerank）
  - **取消原 spec 中 LLM listwise rerank** —— 调研报告已明确 cross-encoder 比 LLM rerank 便宜 10× + 快 50×，且用户已下好可直接用

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Choose Interview Mode at Start (Priority: P1)

用户在新建面试时，先完成岗位参数（position/company/branch_id/job_id）选择，然后在「接下来怎么面试？」步骤看到两个顶层并列选项：「在线 AI 面试」/「豆包面试」。选择「在线 AI 面试」后展开二级选项「快速补漏」与「完整面试」；选择「豆包面试」直接进入 Planner 出卡片。

**Why this priority**: 这是整个 REQ-048 的入口决策点，所有后续 US 都依赖它；不实现此 US，整个特性没有用户入口。

**Independent Test**: 登录 demo 账号 → 进入「新建面试」→ 完成岗位参数 → 看到「接下来怎么面试？」两选项卡 → 任选一项 → 看到对应分支的下一屏。

**Acceptance Scenarios**:
1. **Given** 用户已完成岗位参数选择, **When** 进入「面试方式」选择页, **Then** 同时显示「在线 AI 面试」与「豆包面试」两个大卡片入口，每个带说明文案与配图
2. **Given** 用户错题集为空（<5 道且 status=fresh/reviewing 状态）, **When** 看到「在线 AI 面试」下二级选项, **Then** 「快速补漏」入口显示但置灰，hover 提示「先做完一次面试，错题集有题才能补漏」（US-3 依赖）
3. **Given** 用户在「面试方式」选择页, **When** 返回上一步修改岗位参数, **Then** 重新进入模式选择时之前的选择被清空

---

### User Story 2 — Quick Drill Mode: Hybrid Error-Question Selection (Priority: P1)

用户错题集 ≥ 5 道且当前选了岗位/JD 时，点「快速补漏」按钮：系统基于错题集 + 当前 JD 用 Hybrid (BM25 + BGE embedding + bge-reranker-v2-m3 cross-encoder 精排) 选出 5 道最匹配的错题启动面试。

**Why this priority**: 这是产品的核心差异化价值（错题驱动），技术上是 REQ-048 中风险最高的部分（向量检索基础设施 + pgvector 迁移），独立可测。

**Independent Test**: 给测试账号预置 50+ 道错题（涵盖多种 dimension）→ 进入面试方式选择 → 选「在线面试 + 快速补漏」 → 验证系统返回 5 道题，每题可在 error_questions 表追溯到原 source_question_id，且 top-5 的 dimension 分布与 JD 关键词强相关。

**Acceptance Scenarios**:
1. **Given** user_id 已有 ≥5 道 status≠mastered 的错题, **And** 已选定岗位 JD, **When** 用户点「快速补漏」, **Then** 系统用 Hybrid (BM25 ∪ bge-small-zh-v1.5 cosine → union 50 → bge-reranker-v2-m3 cross-encoder 精排 top-5) 在 ≤3 秒内返回 5 道题作为面试题
2. **Given** JD 关键词为「分布式事务 / 微服务 / RAG」, **When** 错题筛选完成, **Then** 选出的 5 题的 dimension 分布与 JD 关键词对齐（至少有 3 题命中 JD 关键词之一）
3. **Given** 错题库中某题已有 embedding, **When** 用户重复点「快速补漏」同岗位, **Then** 5 分钟内复用相同 5 题（缓存命中）；5 分钟后重新跑检索

---

### User Story 3 — Full Interview Mode: 10-15 Questions with Agent-Controlled Depth (Priority: P1)

用户选择「完整面试」时，可指定软区间「中等（10题）/ 深入（15题）」，Planner 据此控制维度覆盖深度，question_gen 按规划生成题目，途中由 Agent 根据答案质量自适应收尾。

**Why this priority**: 这是现有面试的主路径改造（5 → 10-15），影响所有现有面试用户；必须先实现此 US 才不影响主流程。

**Independent Test**: demo 账号选「在线面试 + 完整面试（中等 10 题）」 → 完成全部 10 题 → 验证 report.per_question_score 长度为 10，维度分布不重复 ≥3 个不同 dimension。

**Acceptance Scenarios**:
1. **Given** 用户选「中等（10 题）」, **When** 面试启动, **Then** Planner 在 focus_areas 中选 2-3 个重点维度，每维度 3-5 题，最终产出 10 题
2. **Given** 用户选「深入（15 题）」, **When** 面试进行到第 12 题且近 3 题 score ≥ 8.0, **Then** Agent 可提前收尾生成报告（不再追加题目；最早收尾边界 12 = 15 - 3，硬下限 7 题永远不会被破）
3. **Given** 用户选「完整面试」, **When** 答到第 N 题且 score < 6, **Then** 仍走原 sink_error 路径（与现状一致）

---

### User Story 4 — Doubao Card Generation & Export (Priority: P1)

用户选择「豆包面试」时，系统只跑 Planner 子图（intake → planner_context → planner_search → planner_generate），生成 InterviewPlan 后立即停止，不进入 question_gen / score_llm / report 节点。前端拿到 InterviewPlan + requirements_md 后请求后端渲染一张 4:3 (1080×810) JPG 卡片，同时支持 9:16 (1080×1920) 切换。

**Why this priority**: 这是 REQ-048 的产品创新点，独立可测；技术上涉及新的 SSR 渲染服务，与 US-1/2/3 无强耦合。

**Independent Test**: demo 账号选岗位 + 「豆包面试」 → 等待 Planner 完成 → 看到 4:3 卡片预览 → 点「下载 JPG」拿到 1080×810 图片；切到「9:16」看到竖版；点「复制大纲文本」拿到 Markdown。

**Acceptance Scenarios**:
1. **Given** Planner 已生成 InterviewPlan, **When** 前端调「生成卡片」接口, **Then** 5 秒内返回 JPG 字节流（≤300KB），卡片包含岗位标题、公司名、难度 badge、时长、5-8 条大纲、InterCraft 品牌水印
2. **Given** 卡片已渲染, **When** 用户点「切换为 9:16」, **Then** 系统复用同一 InterviewPlan 渲染 1080×1920 竖版（含分段标题分隔）
3. **Given** 卡片已生成, **When** 系统记录埋点, **Then** analytics 表新增 1 行（user_id + plan_id + rendered_at + size_variant），无任何对话内容
4. **Given** 用户点「复制大纲文本」, **Then** 剪贴板复制 Markdown：「# 面试大纲\n## 公司: ...\n## 岗位: ...\n## 大纲: 1. ... 2. ...」

---

### User Story 5 — Drill Mode Question Variant Toggle (Priority: P2)

「快速补漏」默认原题重考（直接用错题的 question_text），但用户可在「快速补漏」启动前手动切换为「变体重考」（同考点/同 dimension、不同表面）。变体重考需要在 question_gen 前增加「变体生成」节点，用 LLM 基于错题 question_text + expected_points 生成新问法。

**Why this priority**: 解决「用户背原题答案」的风险，是产品的健壮性增强；不是 MVP 必须，但有 v2 价值。

**Independent Test**: 错题原题「请描述 Redis 持久化机制」+ expected_points: [「RDB」「AOF」「混合持久化」] → 变体节点输出：「Redis 在重启时如何保证数据不丢？请分别讨论快照与追加日志两种方案」。

**Acceptance Scenarios**:
1. **Given** 用户选「快速补漏 + 原题重考」, **When** 面试开始, **Then** question_gen 节点跳过，直接把错题 question_text 注入 questions 列表，dimension 沿用原错题的 dimension
2. **Given** 用户选「快速补漏 + 变体重考」, **When** 面试开始, **Then** 新增「变体生成」节点对每道错题调 LLM 一次，生成新 question_text，原 expected_points + dimension 保留
3. **Given** 变体生成失败（LLM 异常）, **When** 节点降级, **Then** 回退为原题重考并在 analytics 记一次降级事件

---

### User Story 6 — Error Re-Sink on Low Score in Drill Mode (Priority: P2)

「快速补漏」答题过程中，raw_score < 6 仍走原 sink_error 节点（与「完整面试」一致），但 sink_error 走「错题本 UPSERT + frequency 状态机调整」语义（而非 INSERT 新行），调用现有的错题状态机 service。

**Why this priority**: 与错题本联动是「快速补漏」的核心闭环；不实现此 US，补漏只是单次模拟，没法让用户看到「错题掌握度提升」。

**Independent Test**: 准备 5 道错题 source_question_id=A/B/C/D/E → 启动快速补漏 → 答对 3 题错 2 题 → 检查 error_questions 表：A/B/E 这 3 题 last_practiced_at 已更新 + status 按状态机迁移（如 fresh→reviewing）。

**Acceptance Scenarios**:
1. **Given** 错题 source_question_id=A 的 status=fresh, **When** 用户重考后 raw_score=4, **Then** sink_error 调现有错题状态机 service 把它迁移至 status=reviewing + frequency=2，updated_at + last_practiced_at 刷新
2. **Given** 错题 source_question_id=A 的 status=mastered, **When** 用户重考后 raw_score=4, **Then** 状态机反向迁移 mastered→reviewing（用户退步），并记一次「regression」事件
3. **Given** 错题 source_question_id=A 已有 source_session_id=S1, **When** 快速补漏 session_id=S2 完成重考, **Then** 错题本行 source_session_id 字段保持 S1（不回写），last_practiced_at 更新

### Edge Cases

- **错题集 < 5 道**：US-1 已定义「快速补漏」置灰 + hover 提示。如果用户在置灰状态下强行通过 URL 直接进入，US-2 接口返回 422 + 错误码 `INSUFFICIENT_ERROR_POOL`，前端引导回模式选择页
- **Embedding 模型服务不可用**：Hybrid 检索降级为「BM25 top-50 → bge-reranker-v2-m3 精排 top-5」，UI 顶部 toast 提示「错题匹配精度下降」
- **bge-reranker-v2-m3 服务不可用**：重试 1 次（与现有 retry_graph_op 一致），二次失败降级为「BM25 top-5 ∪ bge-small cosine top-5 → LLM listwise rerank top-5」（仅 reranker 全故障才回退到 LLM）
- **Embedding + Reranker 同时不可用**：完全降级为「BM25 top-5」直接返回（无任何精排），UI 顶部 toast 提示「错题匹配回退到基础模式」
- **JD 为空（用户没选岗位）**：错题筛选退化为「按 frequency 倒序取 5 道」+ 提示用户「未指定岗位，已选错题练习」
- **Planner 子图超时（豆包面试）**：超过 30s 强制中止并返回「Planner 生成失败，请重试」+ 一键回模式选择
- **卡片渲染服务故障**：前端显示「卡片生成失败」+ 「复制大纲文本」按钮仍可用
- **用户切换浏览器/刷新页面**：所有模式选择状态丢失，需要从「新建面试」入口重新开始（无状态持久化）
- **豆包 OCR 截断**：属用户/豆包侧问题，不在产品责任范围；产品侧通过字号下限（≥24px）+ 9:16 备选版缓解

## Requirements *(mandatory)*

### Functional Requirements

#### 模式选择与入口
- **FR-001**: System MUST 在「新建面试」流程的「面试方式」选择页提供「在线 AI 面试」与「豆包面试」两个并列入口（Q2=D 决策：分步引导，选完岗位后询问）
- **FR-002**: System MUST 在「在线 AI 面试」下提供「快速补漏」与「完整面试」二级选项；「快速补漏」在错题数 < 5 时置灰且 hover 提示（Q7=B 决策）
- **FR-003**: System MUST 在「完整面试」下提供软区间「中等（10 题）/ 深入（15 题）」两个选项（Q5=B 决策），Agent 在区间内自适应收尾
- **FR-004**: System MUST 在「豆包面试」入口下隐藏「快速补漏」/「完整面试」选项（豆包面试只有一种模式：跑 Planner 出卡片）
- **FR-005**: System MUST 在「面试方式」返回修改岗位参数时清空模式选择状态

#### 错题筛选（Hybrid RAG）
- **FR-010**: System MUST 在 error_questions 表新增 `embedding vector(512)` 字段 + pgvector HNSW 索引（用 `bge-small-zh-v1.5` 模型编码，512 维；预留 `embedding_v2 vector(1024)` 列供 v2 升级 bge-large 时平滑迁移）
- **FR-011**: System MUST 在错题写入/更新时异步触发 embedding 计算（避免写入阻塞 + 重试 3 次）
- **FR-012**: System MUST 在「快速补漏」触发时执行 Hybrid 检索：`BM25(PG tsvector ∪ bge-small-zh-v1.5 cosine JD→错题) → union top-50 → bge-reranker-v2-m3 cross-encoder 精排 top-5`（**已用本机已下载的 reranker，不调 LLM rerank**）
- **FR-013**: System MUST 在 embedding 服务不可用时降级为 `BM25 top-50 → bge-reranker-v2-m3 精排 top-5`，UI 顶部 toast 提示「错题匹配精度下降」
- **FR-014**: System MUST 在 bge-reranker 服务不可用时降级为 `BM25 top-5 ∪ bge-small cosine top-5 → LLM rerank top-5`（仅 reranker 故障才退回 LLM）
- **FR-015**: System MUST 对 5 分钟内同 (user_id, job_id) 的「快速补漏」请求复用同一组 5 道题（缓存 key = hash(JD + error_pool_hash)）

#### 完整面试改造
- **FR-020**: System MUST 把当前 MAX_QUESTIONS=5 改为软上限 10-15，由 Planner 根据用户选择档位 + focus_areas 数量计算实际题数；硬下限为 7（保证报告样本量），硬上限为 15
- **FR-021**: System MUST 在 question_gen 中支持 Agent 自适应收尾：连续 3 题 score ≥ 8.0 时，且当前题数 ≥ `effective_max - 3`（即软上限减 3），可提前生成报告。中等 10 题档最早 7 题收尾；深入 15 题档最早 12 题收尾
- **FR-022**: System MUST 在 score_llm 路由保持兼容：当 `current_question >= effective_max` 时路由到 report，否则继续 question_gen；自适应收尾的"提前"指 effective_max - 3 题这个边界，不是 hard 边界
- **FR-023**: System MUST 在 question_gen 节点前新增 `effective_max` 计算逻辑：`effective_max = max(MIN_QUESTIONS=7, min(user_choice, planner_recommended))`，其中 user_choice=10 或 15，planner_recommended 由 focus_areas 数量 × 每维度 3-5 题动态算出

#### 错题驱动面试流程
- **FR-030**: System MUST 在「快速补漏」启动时，把错题 source_question_id 列表写入 state，作为 question_gen 的输入源（替代 Planner 生成的 suggested_questions）
- **FR-031**: System MUST 在「原题重考」模式下：question_gen 节点跳过生成，直接把错题 question_text 注入 questions，dimension 沿用原错题
- **FR-032**: System MUST 在「变体重考」模式下：新增「错题变体生成」节点，对每道错题调 LLM 一次生成新 question_text，原 expected_points + dimension 保留
- **FR-033**: System MUST 在变体生成失败时降级为原题重考，并在 analytics 记一次降级事件

#### 错题本联动（US-6）
- **FR-040**: System MUST 在「快速补漏」+ raw_score < 6 时复用现有 sink_error 节点，但改写为「按 source_question_id UPSERT + frequency 状态机迁移」（Q8=A 决策）
- **FR-041**: System MUST 复用现有错题状态机 service（`app.modules.errors.service`）做 status/frequency 迁移，包括 mastered → reviewing 的反向迁移（regression 检测）
- **FR-042**: System MUST 在每次重考更新 last_practiced_at = now()，但保留原 source_session_id 不回写

#### 豆包卡片渲染
- **FR-050**: System MUST 在「豆包面试」模式只跑 Planner 子图（intake → planner_context → planner_search → planner_generate），完成 InterviewPlan 后立即停止，不进入 question_gen/score_llm/report（Q4=B 决策：仅埋点事件，不持久化对话）
- **FR-051**: System MUST 在 InterviewPlan 生成后由后端调用 `@vercel/og` (satori + resvg) + sharp mozjpeg 渲染 4:3 (1080×810) JPG q=85
- **FR-052**: System MUST 同时支持 9:16 (1080×1920) 竖版（Q3=A 决策），前端提供切换按钮复用同一 InterviewPlan 重渲染
- **FR-053**: System MUST 在卡片上至少包含：岗位标题、公司名、难度 badge（易/中/难）、预计时长、5-8 条大纲条目、InterCraft 品牌水印
- **FR-054**: System MUST 提供「下载 JPG」「复制大纲 Markdown」两个 CTA；不强制分享链接
- **FR-055**: System MUST 在卡片渲染成功时记录埋点事件（user_id, plan_id, rendered_at, size_variant），不存任何对话内容（Q4=B 决策）
- **FR-056**: System MUST 在 Planner 超时（>30s）或渲染失败时返回明确错误码 + 一键回退到「面试方式」选择

#### 卡片字段（与调研结论对齐）
- **FR-060**: System MUST 把卡片文字字号下限设为 ≥24px，关键标题 ≥64px（避免豆包 OCR 截断）
- **FR-061**: System MUST 把卡片背景设为不透明（微信/豆包端 PNG 透明会变白底导致文字丢失）
- **FR-062**: System MUST 把卡片文件大小控制在 ≤300KB（4:3 JPG q=85）；9:16 同标准
- **FR-063**: System MUST 缓存卡片输出（hash(JD + plan fields) → 7d TTL），避免重复生成

### Key Entities *(include if feature involves data)*

- **InterviewSession**: 现有 `interview_sessions` 表，新增字段 `mode` (`quick_drill` / `full` / `doubao`) + `max_questions` (10 或 15) + `error_question_ids` (JSONB，仅 quick_drill 模式使用，存 source_question_id 列表)
- **InterviewPlan (Pydantic)**: 现有 `schemas.InterviewPlan`，不变；豆包面试时序列化入卡片
- **ErrorQuestion.embedding**: 现有 `error_questions` 表，新增 `embedding vector(512)` 列（pgvector 迁移，bge-small-zh-v1.5 输出），由后台 worker 异步计算；预留 `embedding_v2 vector(1024)` 列供 v2 升级
- **DoubaoCardRenderEvent**: 新增埋点表 `analytics_events`，type=`doubao_card_rendered`，字段 (user_id, plan_id, size_variant, rendered_at, duration_ms)
- **DrillCacheEntry**: 新增 Redis 缓存 key `drill_cache:{user_id}:{job_id_hash}`，TTL 5 分钟，value = 错题 source_question_id 列表

## Success Criteria *(mandatory)*

### Measurable Outcomes

#### 模式选择可用性
- **SC-001**: 用户从「岗位选择完成」到「模式选择完成」步骤耗时中位数 ≤30 秒
- **SC-002**: 错题数 < 5 的用户点「快速补漏」时的引导成功率（点 hover 后返回模式选择）≥90%

#### 错题筛选质量
- **SC-010**: 「快速补漏」从用户点击到拿到 5 道题的端到端耗时 p95 ≤3 秒（含 embedding 检索 + bge-reranker-v2-m3 cross-encoder 精排）
- **SC-011**: 「快速补漏」选出的 5 道题中，至少 3 题的 dimension 与 JD 关键词命中（基于人工标注的 20 组测试集）
- **SC-012**: 在 100 道错题 / 500 道错题场景下，Hybrid 检索的 top-5 准确率（与人工标注 ground truth 重合度）均 ≥70%
- **SC-013**: 5 分钟内同 (user, job) 二次进入「快速补漏」复用缓存的命中率 ≥80%

#### 完整面试体验
- **SC-020**: 「中等（10 题）」模式下，90% 的面试实际生成 9-11 题（±1 的浮动）
- **SC-021**: 「深入（15 题）」模式下，90% 的面试实际生成 13-15 题
- **SC-022**: 「自适应收尾」触发率：在 score ≥ 8.0 连续 3 题时，提前收尾触发率 ≥60%（即不是 100% 触发，因为也有用户想全做完）

#### 豆包卡片质量
- **SC-030**: 4:3 卡片生成端到端耗时 p95 ≤5 秒（含 Planner + 渲染）
- **SC-031**: 卡片文件大小 ≤300KB（4:3 + 9:16 同时满足）
- **SC-032**: 卡片文字字号下限 ≥24px（自动化脚本校验）
- **SC-033**: 「豆包面试」埋点事件触发成功率 ≥99%（失败回退到错误页时也记）
- **SC-034**: 用户点「复制大纲文本」后剪贴板内容可被 OCR / 文本识别工具完整还原（无截断）

#### 错题本联动
- **SC-040**: 「快速补漏」低分（<6）触发 sink_error 时，错题本 UPSERT 成功率 ≥99%（重试机制保证）
- **SC-041**: 错题 status 状态机迁移准确率 100%（基于现有 service 单元测试，不引入新 bug）

## Assumptions

- **A-001**: InterCraft 已部署 PostgreSQL + pgvector 扩展（参考现有 agent_memory 模块的 embedding 用法）；如未部署，需在迁移 0028 中创建扩展
- **A-002**: BAAI/bge-small-zh-v1.5（embedding 召回，512 维，~93MB）+ BAAI/bge-reranker-v2-m3（cross-encoder 精排，2.27 GB，**已下载**）部署在独立 Python 进程（CPU 跑 small + reranker-m3 均可；reranker-m3 在 CPU 上 ~50ms/pair），通过内部 HTTP 端点被 FastAPI 调用；模型文件存 git LFS 或运行时从 HuggingFace 缓存拉取；与现有 `app.agents.llm_client` 架构并列但独立部署（不挤占 DeepSeek 配额）。**实查结果（2026-07-07）**：
  - 本机已下好 `bge-reranker-v2-m3`（HF Hub cache: `C:\Users\30803\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3\snapshots\953dc6f6\`）—— 精排阶段**零下载成本**
  - bge-small-zh-v1.5（embedding 阶段）需补下，~93 MB
  - pyproject/uv.lock 仍**无相关依赖**（FlagEmbedding / sentence-transformers / transformers），`.env` 无 `EMBEDDING_SERVICE_URL` 等字段，`core/config.py` 无 Settings 字段 —— REQ-048 是项目**首次引入 BGE** 的特性，plan 阶段需落实：`pyproject.toml` 新增 `FlagEmbedding>=1.2`（embedding 端）+ `transformers>=4.38`（reranker 端），`.env.example` 新增 `EMBEDDING_SERVICE_URL` / `EMBEDDING_MODEL_NAME` / `RERANKER_SERVICE_URL` / `RERANKER_MODEL_NAME` 字段，`core/config.py` 新增对应 Settings 字段，独立 embedding + reranker worker 进程（可合并到同一 service 暴露 `/embed` + `/rerank` 两个 endpoint）
  - 已有基础设施复用：`backend/migrations/versions/0005_phase6_global_capabilities.py:144-166` 已有 `to_tsvector` + GIN 索引模式（job_questions 表），可镜像建错题 BM25 索引
- **A-003**: `error_questions` 表每日新增 < 100 行/用户，embedding 离线批处理延迟 < 1h 可接受
- **A-004**: 错题集里 question_text 平均 ≤ 500 token（参考调研 e 字段推荐 chunk 设计）；超长文本需先截断到 1500 token 再 encode
- **A-005**: 豆包 OCR 对中文卡片文字的最小可识别字号为 24px（在调研中假设，需豆包真机实测验证；如不满足，4:3 横版可能有截断风险）
- **A-006**: 用户错题集增长到 500+ 道是 6-12 个月长期目标，短期（3 个月内）绝大多数用户 < 100 道
- **A-007**: 现有的「错题状态机 service」（`app.modules.errors.service`）覆盖 status=fresh/reviewing/mastered 三态 + frequency 0-3 范围，状态迁移规则稳定可用；**mastered → reviewing 反向迁移（regression 检测）** 需在 plan 阶段先 review 现有 service 代码确认是否原生支持，如不支持需补 1 个 PR（约 20 行）
- **A-008**: `@vercel/og` (satori + resvg) 在 Node.js 22 环境下能正常工作（与项目现有 Node 版本兼容）
- **A-009**: 卡片渲染不需要 SSR 服务（可放在 FastAPI 后端的独立 worker 进程中，不强求 Edge Function）
- **A-010**: 现有 Planner 子图（context/search/generate）的 LLM 调用失败时已具备重试 + 降级逻辑，本次豆包面试模式可复用
- **A-011**: 中文 Noto Sans SC 字体子集化在首次构建时跑一次（≈10 分钟），子集字体文件存对象存储 / git LFS
- **A-012**: 「豆包面试」场景下用户错题集不参与（错题筛选仅适用于「在线面试 + 快速补漏」）

## Out of Scope

- 豆包对话内容回填/上传归档（Q4=B：仅埋点，不持久化对话）
- 跨 session 错题本合并（如用户在多设备累积错题，本次不处理）
- 错题本的人工 review / 编辑界面（属于错题本现有功能，不在 REQ-048 范围）
- 多语言卡片（仅中文）
- 卡片动画 / 视频预览
- 候选人个人信息嵌入卡片（隐私风险；除非用户主动授权）
- 雷达图 / 数据可视化元素（OCR 后丢失风险大）
- 错题集的自动归类 / 标签优化（属于错题本能力）
- 豆包侧对话的 AI 评估（豆包返回内容不进入 InterCraft 评分）
- 离线模式（所有功能均需联网）
- 错题集手动管理 UI 改进（属于错题本功能）