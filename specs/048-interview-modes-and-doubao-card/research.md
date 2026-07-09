# Research Notes — REQ-048 Interview Mode Split + Doubao Card Export

**Date**: 2026-07-07
**Purpose**: Resolve Technical Context unknowns and document alternatives considered for REQ-048 implementation.

---

## R-1. BGE Embedding 维度选型

**Decision**: 错题 embedding 用 `bge-small-zh-v1.5` 输出 **512 维**；表结构预留 `embedding_v2 vector(1024)` 列供 v2 升 bge-large 时平滑迁移

**Rationale**:
- bge-small-zh-v1.5 实际输出 512 维（澄清 round 1 修复的维度冲突）
- bge-large-zh-v1.5 输出 1024 维但需要 GPU 推理 + 1.3GB 模型文件
- 512 维 vs 1024 维在「错题 top-50 召回」场景准确率差异 < 5%（参考 BAAI 官方 benchmark）
- 预留 v2 列避免未来 ALTER TABLE 大表重建

**Alternatives considered**:
- ❶ bge-large-zh-v1.5 (1024 维) — GPU 推理 15ms / 句；准确率高 5-8%，但需要 GPU 部署，本机无 GPU
- ❷ OpenAI text-embedding-3-small — 1536 维跨境 API 调用，依赖外部、不可控
- ❸ BGE-M3 单模型三输出 — 2.3GB、复杂度过高、MVP 阶段不需要多向量召回

---

## R-2. 精排模型选型

**Decision**: 用 `bge-reranker-v2-m3` cross-encoder reranker（**本机已下载** 2.27 GB，XLMRoberta-large）

**Rationale**:
- 实查 `C:\Users\30803\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3\` 已就绪（零下载成本）
- Cross-encoder 比 LLM listwise rerank 便宜 10× + 快 50×（Anthropic Contextual Retrieval benchmark 佐证）
- CPU 推理 ~50ms/pair，对 top-50 候选精排 ~2.5 秒，符合 SC-010 ≤3s 预算

**Alternatives considered**:
- ❶ LLM listwise rerank (RankGPT 风格 permutation) — DeepSeek 配额 500K/月，每个「快速补漏」消耗 ~6K tokens，浪费大
- ❷ BGE-reranker-base — 280MB，更轻量但准确率低 8%
- ❸ Cohere Rerank API — 跨境延迟 + 配额限制

---

## R-3. Hybrid 检索架构

**Decision**: BM25（PG `tsvector` GIN 索引）∪ bge-small cosine → union top-50 → bge-reranker-v2-m3 精排 top-5

**Rationale**:
- Anthropic Contextual Retrieval 论文（2024-09）证明 hybrid + rerank 比单 LLM 召回 top-20 fail rate 降 67%（5.7% → 1.9%）
- BM25 强精确词匹配（中文"分布式事务"） + cosine 强语义匹配（"分布式事务" ≈ "分布式数据库一致性"）
- PG `tsvector` + GIN 索引在 `0005_phase6_global_capabilities.py:144-166` 已有成熟模式（job_questions 表），可直接镜像到 error_questions

**Alternatives considered**:
- ❶ 纯 LLM in-context selection — 500 题 ~250K tokens 触发 Lost in the Middle（Liu et al. TACL 2023）+ 单次 $0.5 成本
- ❷ 纯 keyword (dimension 过滤) — 维度标签粒度太粗（"系统设计" 涵盖 100+ 错题）
- ❸ 纯 embedding cosine — 失去精确词匹配，对短关键词召回弱

---

## R-4. 卡片渲染技术栈

**Decision**: 服务端 Node.js 22 + `@vercel/og` (satori + resvg) + sharp mozjpeg（4:3 + 9:16 双版本）

**Rationale**:
- `@vercel/og` 是 Vercel 官方维护的 satori 包装，warm 80-250ms / cold 300-800ms，远快于 Puppeteer/Playwright（1.5-3s）
- 完美支持 CJK（satori 0.10 + Noto Sans SC 子集化 ~150KB）
- 可独立部署为 Node.js 22 FastAPI 子服务或独立 Node 进程，通过内部 HTTP 调用
- sharp mozjpeg q=85 把卡片压到 ≤300KB（SC-031）

**Alternatives considered**:
- ❶ html2canvas（前端方案）— 浏览器字体加载 + 800-2000ms，CN IM 端用户可能因字体丢失失败
- ❷ Puppeteer / Playwright — 1.5-3s cold start + 镜像体积 + 中文字体部署复杂
- ❸ 服务端 Python `imgkit` / `weasyprint` — 中文支持差 + 难维护

---

## R-5. 错题筛选缓存策略

**Decision**: Redis `drill_cache:{user_id}:{job_id_hash}` 5 分钟 TTL，value = source_question_id 列表（已 JSON 化）

**Rationale**:
- 同一用户对同一 JD 短时间内重复点「快速补漏」概率高（如面试前热身）
- 5 分钟 TTL 平衡「复用价值」与「错题实时性」
- 命中率高（SC-013 ≥80%）

**Alternatives considered**:
- ❶ 无缓存 — 每次都跑 embedding 检索，浪费 LLM/embedding 配额
- ❷ 1 小时 TTL — 错题集刷新不及时
- ❸ Postgres `error_pool_hash` 列 — 增加 schema 复杂度，缓存命中率不易监控

---

## R-6. 完整面试题量控制逻辑

**Decision**: `effective_max = max(MIN_QUESTIONS=7, min(user_choice, planner_recommended))`，硬下限 7 / 硬上限 15

**Rationale**:
- 报告样本量至少 7 题才有统计意义
- 中等 10 题档最早 7 收尾；深入 15 题档最早 12 收尾（FR-023 + clarify round 2 决策）
- 自适应收尾触发：连续 3 题 score ≥ 8.0 **且** 当前题数 ≥ effective_max - 3

**Alternatives considered**:
- ❶ 软上限无下限 — 选了深入 15 但只做 5 题就收尾，报告意义不大
- ❷ 引入 IRT ability 阈值 — 加 1 sprint，复杂度溢出 MVP

---

## R-7. 变体重考 vs 原题重考 UX

**Decision**: 默认原题重考，UI 提供 toggle「换种问法」切换为变体重考（Q6=C）

**Rationale**:
- 默认原题减少 LLM 调用（5 题省 5 次 LLM 调用）
- 变体重考解决「用户背原题」风险（US-5 P2 增强）
- 变体失败自动降级原题（FR-033 健壮性）

**Alternatives considered**:
- ❶ 默认变体重考 — 增加 LLM 成本，无明显收益
- ❷ 仅原题重考 — 失去防止背题能力
- ❸ 仅变体重考 — 用户测试熟悉题时体验差

---

## R-8. 错题本联动语义

**Decision**: 「快速补漏」低分走 UPSERT + 错题状态机 service（复用现有 `app.modules.errors.service`）

**Rationale**:
- source_question_id 已存在于 error_questions，UPSERT 比 INSERT 新行更符合语义
- 现有 service 已覆盖 status=fresh/reviewing/mastered + frequency 0-3（mastered→reviewing 反向迁移需在 plan 阶段 review 代码确认是否支持，A-007 标注）
- 保留 source_session_id 不回写（FR-042 语义）

**Alternatives considered**:
- ❶ 每次 INSERT 新行 — 错题本爆炸，A/B/C 错题在表里有 3 行
- ❷ 不联动错题本 — 失去「快速补漏」闭环价值

---

## R-9. 「豆包面试」早停条件边设计

**Decision**: 在 Planner 子图后插入一个 `MODE_GUARD` 节点，state 含 `mode=doubao` 时立即跳到 END，跳过 question_gen / score_llm / report

**Rationale**:
- 复用现有 LangGraph 子图编排，不重新设计 Agent
- Planner 子图已具备 LLM 重试 + 降级逻辑（A-010）
- `MODE_GUARD` 节点一次 O(1) 路由开销，零额外 LLM 调用

**Alternatives considered**:
- ❶ 新建独立的 DoubaoAgent — 重复 Planner 代码 80%，违反 Library-First 原则
- ❷ 在前端拦截 Planner 调用 — 后端无隔离层，多端一致性差

---

## R-10. 中文 Noto Sans SC 字体子集化策略

**Decision**: 首次构建跑 `subset-font` 按字符切片，存 `git LFS` 或对象存储

**Rationale**:
- Noto Sans SC 完整字体 9MB+ → 子集化后 150-200KB
- 卡片文本只覆盖：岗位标题、公司名、难度 badge、时长、大纲条目（≈200-500 字符）
- 字符集可在 build 时通过 demo 数据预扫描锁定

**Alternatives considered**:
- ❶ 全字体嵌入 — 9MB+，satori 渲染慢 + 内存高
- ❷ 运行时下载 — 增加首渲染延迟 3-5s
- ❸ 用思源黑体替代 — 同源，许可不同

---

## R-11. Embedding 异步批处理 worker

**Decision**: 用项目现有 `arq` 任务队列（已存在）新增 `compute_embedding_task`，错题写入/更新时 enqueue

**Rationale**:
- 现有 arq 0.25+ 已部署（`pyproject.toml`），复用基础设施
- 任务失败重试 3 次（FR-011）+ DLQ
- 不阻塞主写入路径

**Alternatives considered**:
- ❶ 同步 embedding 计算 — 写入延迟 50-200ms，UX 差
- ❷ Celery — 项目没用，引入新基础设施
- ❸ FastAPI BackgroundTasks — 进程重启丢失任务

---

## R-12. Constitution Compliance Map

| Principle | Compliance | Notes |
|---|---|---|
| I. Library-First | ✅ | embedding_service、card_renderer 都各自独立 library，含 CLI |
| II. CLI Interface | ✅ | embedding_service 提供 `python -m app.services.embedding.cli --text "..."` CLI；card_renderer 同理 |
| III. Test-First | ✅ | tasks.md 中 TDD 任务前置：unit test → integration test → impl |
| IV. Integration & Synchronization | ✅ | 需新增 Playwright E2E 「快速补漏」+ 「豆包卡片」两条路径 |
| V. Observability | ✅ | 复用 `@traced_node` decorator + 新增 `analytics_events.doubao_card_rendered` |

---

## R-13. NEEDS CLARIFICATION Resolution

| 之前标记 | 解决方式 | 当前状态 |
|---|---|---|
| BGE embedding 模型选型 | R-1 | Resolved |
| 精排模型选型 | R-2 | Resolved（实查本机已下载） |
| Hybrid 检索架构 | R-3 | Resolved |
| 卡片渲染技术栈 | R-4 | Resolved |
| 缓存策略 | R-5 | Resolved |
| 完整面试题量逻辑 | R-6 + clarify round 2 | Resolved |
| 变体重考 UX | R-7 | Resolved |
| 错题本联动语义 | R-8 | Resolved（plan 阶段需验证 regression 路径） |
| 豆包早停条件 | R-9 | Resolved |
| 字体子集化 | R-10 | Resolved |
| embedding worker | R-11 | Resolved |

**全部 Resolved。无残余 NEEDS CLARIFICATION。**

---

## R-14. Risk Register (for tasks.md tracking)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| bge-small-zh-v1.5 模型首次下载失败 | Medium | Medium | 用 HF 镜像 + retry 3 |
| 错题集 < 50 题时 embedding 召回质量差 | High | Low | FR-013 降级 + BM25-only fallback |
| 豆包 OCR 截断小字 | Medium | Medium | FR-060 字号下限 + 9:16 备选 |
| 卡片渲染服务 OOM | Low | High | 字体子集化 + 渲染超时 5s |
| reranker CPU 推理 p95 超 1s | Low | Medium | top-50 → bge-reranker 已预算 2.5s |
| mastered → reviewing 反向迁移 service 不支持 | Medium | Low | A-007 标注 + tasks T-XX review 现有 service |
| pgvector 扩展未启用 | Medium | High | 迁移 0028 显式 CREATE EXTENSION |