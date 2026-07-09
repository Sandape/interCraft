"""Prompt A vs B for REQ-053 interview-research report generation.

PROMPT_A: verbatim copy of `app.modules.research.report_generator.SYSTEM_PROMPT`
          at the time of the A/B experiment (2026-07-09). Acts as the control.
PROMPT_B: an optimized variant that adds three explicit improvements over A:
          (1) strict 2000-3000 character window
          (2) strict interview-question format ("题目:" ... "答案方向:")
          (3) weakness section must include dimension key + score + actionable tip
          (4) explicit hint to output a markdown table for history comparison
              (the code layer still appends its own table, but asking the LLM
              to emit one too increases the chance of human-readable output).

The winner (based on the analyzer metrics in `analyze_prompt_ab.py`) is later
copied into `report_generator.py` as the new default `SYSTEM_PROMPT`.
"""
from __future__ import annotations

# --- Verbatim copy of the current SYSTEM_PROMPT (the control) -------------

PROMPT_A = """你是一位资深的求职面试准备助手，专精于为中国求职者生成面试前的研究报告。

你的任务是基于提供的公司、岗位、面试时间和搜索结果，生成一份 2000-3000 字的简体中文面试备战报告。

报告必须严格按照以下 6 个章节结构输出，使用 Markdown 格式：

## 📋 面试概览
包含：公司名称、岗位名称、面试时间（北京时间）、面试轮次、距离面试的倒计时。

## 🏢 公司与产品速览
公司核心业务简介，列出与岗位方向直接相关的具体产品/服务名称。

## 📝 面经汇总
从搜索结果中提炼 3-8 道具体面试题，每道题包含：题目本身 + 简要答案方向。题目要真实、具体、可操作，不要泛泛而谈。

## 🎯 高频考察点
按重要性排列该岗位方向的 5-10 个核心知识点，每个知识点一行，说明考察方式和重要性。

## ⚠️ 你的薄弱环节
基于用户的能力画像（最低 2 个维度的实际得分）和错题本数据，识别 2-3 个具体的薄弱主题，每个主题给出：
- 主题名称（如"RAG 工程化"）
- 关联的能力维度名称和得分
- 一条可立即执行的速成建议

如果用户没有能力画像数据（首次模拟面试），本章填写"你还没有足够的面试数据，完成一次模拟面试后可生成个性化薄弱点分析"。

## 💡 最后建议
3 条面试前可立即执行的行动建议（如"复习 XX 知识点"、"准备好 1 分钟自我介绍"、"了解公司 YY 产品最新版本"）。

## 📊 历史对比（可选）
如果用户过去 7 天有同公司的面试报告，对比上次面试前的薄弱点与本次的变化（进步/退步/持平）。

要求：
- 字数 2000-3000（中文字符计 1，英文字母计 0.5）
- 不得编造未经验证的信息——只使用提供的搜索结果和数据
- 章节顺序固定，使用二级标题（##）作为章节分隔
- 信息量少的面经如实说明，不以编造或过度泛化的内容填充
"""


# --- Optimized variant ---------------------------------------------------

PROMPT_B = """你是一位资深的求职面试准备助手，专精于为中国求职者生成面试前的研究报告。

【硬性指标】
- 输出总字数必须严格落在 **2000-3000 字符**之间（中文字符计 1，ASCII 计 0.5）。
- 章节顺序固定为 6 个二级标题（##），顺序不可调换：
  📋 面试概览 → 🏢 公司与产品速览 → 📝 面经汇总 → 🎯 高频考察点 → ⚠️ 你的薄弱环节 → 💡 最后建议
  （📊 历史对比章节在用户有同公司历史报告时才需要，代码层会追加表格。）

## 📋 面试概览
4-5 行，包含：公司名称、岗位名称、面试时间（北京时间精确到分钟）、面试轮次、距面试的实时倒计时。

## 🏢 公司与产品速览
2-3 段，公司核心业务简介 + 与岗位方向直接相关的 **3-5 个具体产品/服务名称**（必须含产品名而非泛称"产品"）。

## 📝 面经汇总（最关键章节）
- 必须给出 **3-8 道具体面试题**。
- **每道题必须严格遵循以下格式**：
  题目：<完整题干>
  答案方向：<2-3 句要点方向，含考察意图>
- 题目要真实可操作，不要泛泛而谈。

## 🎯 高频考察点
5-10 个核心知识点，每个一行，格式：
  - <知识点名称> | <考察方式> | <重要性(高/中/低)>

## ⚠️ 你的薄弱环节
基于用户的能力画像（最低 2 个维度的实际得分），识别 **2-3 个薄弱主题**。
**每个主题必须包含以下三个要素**（缺一不可）：
  1. 主题名称（如 RAG 工程化）
  2. 关联的能力维度 key 与得分（如 tech_depth 得分 65）
  3. 一条可立即执行的速成建议（≤ 50 字，含具体动作）
如果用户无能力画像数据，填写：
  "你还没有足够的面试数据，完成一次模拟面试后可生成个性化薄弱点分析"。

## 💡 最后建议
**恰好 3 条** 面试前 24h 内可立即执行的行动建议，每条以动词开头。

【风格约束】
- 简体中文，专精于中文求职场景；
- 不得编造未经验证的信息——只使用提供的搜索结果与画像数据；
- 信息量不足时如实说明，禁止占位符/模板化内容；
- 6 个 emoji 必须按上述顺序出现，不要增删。
"""


# --- Fixtures (simulated search results for 5 real-world scenarios) -----

AB_FIXTURES: list[dict] = [
    {
        "name": "字节跳动 AI 应用工程师",
        "company": "字节跳动",
        "position": "AI 应用工程师",
        "interview_time_iso": "2026-07-15T14:00:00+08:00",
        "interview_round": "一面（1 轮）",
        "search_results": {
            "interview_experience": [
                {"title": "字节 AI 应用工程师 一面面经", "url": "https://example.com/1",
                 "content": "问了 transformer 原理、RAG pipeline、prompt engineering 案例，要求手写 self-attention。"},
                {"title": "字节 AI 工程师 面试真题", "url": "https://example.com/2",
                 "content": "问了 LangChain vs LlamaIndex，向量数据库选型，Milvus vs Pinecone。"},
            ],
            "company_product": [
                {"title": "字节扣子 Coze 产品介绍", "url": "https://example.com/3",
                 "content": "扣子是字节的 AI Agent 平台，对标 GPTs，已上线 Web + 插件市场。"},
                {"title": "字节豆包 模型能力", "url": "https://example.com/4",
                 "content": "豆包大模型 1.5 Pro 支持 128k context，多模态理解，推理速度快。"},
            ],
            "exam_points": [
                {"title": "AI 应用工程师 面试考点", "url": "https://example.com/5",
                 "content": "Transformer/LLM 基础、RAG 架构、Agent 设计、向量检索、推理优化。"},
            ],
        },
        "user_weakness": {
            "dimensions": [
                {"key": "tech_depth", "score": 65.0,
                 "improvements": ["Transformer 细节", "Self-attention 手写"]},
                {"key": "architecture", "score": 60.0,
                 "improvements": ["RAG pipeline 拆解", "Agent 工具编排"]},
            ],
            "error_question_tags": ["self-attention", "RAG", "vector db"],
            "has_ability_data": True,
        },
    },
    {
        "name": "阿里云后端开发",
        "company": "阿里云",
        "position": "后端开发工程师",
        "interview_time_iso": "2026-07-12T10:30:00+08:00",
        "interview_round": "二面（2 轮）",
        "search_results": {
            "interview_experience": [
                {"title": "阿里云后端 二面", "url": "https://example.com/6",
                 "content": "问了高并发、分布式锁、MySQL 索引、Redis 集群，要求设计秒杀系统。"},
            ],
            "company_product": [
                {"title": "阿里云 ECS 弹性计算", "url": "https://example.com/7",
                 "content": "ECS 提供弹性计算服务，支持秒级交付，多 AZ 部署。"},
                {"title": "阿里云 OSS 对象存储", "url": "https://example.com/8",
                 "content": "OSS 是阿里云海量、安全、低成本的对象存储服务，11 个 9 持久性。"},
            ],
            "exam_points": [
                {"title": "后端工程师 面试考察点", "url": "https://example.com/9",
                 "content": "分布式、高并发、数据库、缓存、消息队列、系统设计。"},
            ],
        },
        "user_weakness": {
            "dimensions": [
                {"key": "tech_depth", "score": 70.0, "improvements": ["Redis 集群"]},
                {"key": "engineering_practice", "score": 55.0,
                 "improvements": ["秒杀系统设计", "MySQL 索引调优"]},
            ],
            "error_question_tags": ["Redis cluster", "秒杀"],
            "has_ability_data": True,
        },
    },
    {
        "name": "腾讯前端高级工程师",
        "company": "腾讯",
        "position": "前端高级工程师",
        "interview_time_iso": "2026-07-18T15:00:00+08:00",
        "interview_round": "三面（3 轮）",
        "search_results": {
            "interview_experience": [
                {"title": "腾讯前端 三面 总监面", "url": "https://example.com/10",
                 "content": "问了 React 18 concurrent、虚拟 DOM diff、微前端、监控体系建设。"},
            ],
            "company_product": [
                {"title": "微信视频号", "url": "https://example.com/11",
                 "content": "视频号是腾讯的短视频产品，DAU 已突破 8 亿。"},
            ],
            "exam_points": [
                {"title": "高级前端 面试考点", "url": "https://example.com/12",
                 "content": "框架原理、性能优化、工程化、监控、跨端方案。"},
            ],
        },
        "user_weakness": {
            "dimensions": [
                {"key": "tech_depth", "score": 72.0, "improvements": ["React concurrent"]},
                {"key": "architecture", "score": 50.0, "improvements": ["微前端架构"]},
            ],
            "error_question_tags": ["React Fiber", "微前端"],
            "has_ability_data": True,
        },
    },
    {
        "name": "美团数据分析师",
        "company": "美团",
        "position": "数据分析师",
        "interview_time_iso": "2026-07-11T11:00:00+08:00",
        "interview_round": "一面（1 轮）",
        "search_results": {
            "interview_experience": [
                {"title": "美团 DA 面经", "url": "https://example.com/13",
                 "content": "问了 SQL 窗口函数、AB 实验、留存模型、业务指标拆解。"},
            ],
            "company_product": [
                {"title": "美团到店业务", "url": "https://example.com/14",
                 "content": "到店业务涵盖餐饮、医美、教育，是美团核心利润来源。"},
            ],
            "exam_points": [
                {"title": "数据分析师 考点", "url": "https://example.com/15",
                 "content": "SQL、Python、AB 实验、因果推断、指标体系。"},
            ],
        },
        "user_weakness": {
            "dimensions": [
                {"key": "business", "score": 58.0, "improvements": ["外卖业务理解"]},
                {"key": "engineering_practice", "score": 62.0, "improvements": ["AB 实验设计"]},
            ],
            "error_question_tags": ["AB 实验", "留存"],
            "has_ability_data": True,
        },
    },
    {
        "name": "小米算法工程师 (应届)",
        "company": "小米",
        "position": "算法工程师",
        "interview_time_iso": "2026-07-20T09:30:00+08:00",
        "interview_round": "笔试",
        "search_results": {
            "interview_experience": [
                {"title": "小米算法 笔试", "url": "https://example.com/16",
                 "content": "三道编程：链表反转 + 二分搜索 + DP；附加卷面是机器学习推导。"},
            ],
            "company_product": [
                {"title": "小米汽车 SU7", "url": "https://example.com/17",
                 "content": "小米 SU7 首款轿车，2024 年发布，主打智能驾驶 + 智能座舱。"},
            ],
            "exam_points": [
                {"title": "算法工程师 应届考点", "url": "https://example.com/18",
                 "content": "数据结构、机器学习、深度学习、CV/NLP 基础。"},
            ],
        },
        "user_weakness": {
            "dimensions": [
                {"key": "algorithm", "score": 68.0, "improvements": ["DP 题型"]},
                {"key": "tech_depth", "score": 60.0, "improvements": ["CNN 推导"]},
            ],
            "error_question_tags": ["动态规划", "反向传播"],
            "has_ability_data": True,
        },
    },
]


__all__ = ["AB_FIXTURES", "PROMPT_A", "PROMPT_B"]
