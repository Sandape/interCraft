"""Phase 6 — Content seed data: resources and FAQ."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import HelpFAQ, Resource


RESOURCES = [
    {
        "title": "技术面试准备指南",
        "summary": "系统设计、算法、行为面试的全面准备方法",
        "category": "tech_prep",
        "tags": ["技术面试", "系统设计", "算法"],
        "content": """# 技术面试准备指南

## 核心框架

技术面试通常包含以下环节：

1. **算法与数据结构** — LeetCode Medium/Hard 难度
2. **系统设计** — 面向高级职位
3. **行为面试** — STAR 法则回答
4. **项目深挖** — 简历上的重点项目

## 算法准备

- 重点题型：数组、字符串、树、图、动态规划
- 推荐练习：每日 2-3 题，保持手感
- 面试时先确认输入输出边界条件

## 系统设计

- 掌握 CAP 定理、一致性哈希、分布式缓存
- 练习设计：短 URL、聊天系统、Feed 流
- 面试时注意：先明确需求，再画架构图
""",
        "content_type": "article",
        "read_time_minutes": 15,
        "sort_order": 1,
    },
    {
        "title": "简历优化完全手册",
        "summary": "从排版到内容，让你的简历脱颖而出",
        "category": "resume_guide",
        "tags": ["简历", "排版", "STAR"],
        "content": """# 简历优化完全手册

## 排版原则

- 一页为佳，不超过两页
- 使用一致的字体和字号
- 留白合理，避免拥挤

## 内容撰写

- 每段经历使用 STAR 法则
- 用量化数据说话（"提升 30% 性能"）
- 针对岗位定制关键词

## 常见误区

- 不要使用过于花哨的模板
- 不要包含个人照片（国内部分公司偏好除外）
- 不要有语法或拼写错误
""",
        "content_type": "article",
        "read_time_minutes": 10,
        "sort_order": 1,
    },
    {
        "title": "模拟面试最佳实践",
        "summary": "如何最大化模拟面试的价值",
        "category": "interview_tips",
        "tags": ["模拟面试", "练习", "反馈"],
        "content": """# 模拟面试最佳实践

## 准备工作

- 选择与你目标岗位匹配的面试类型
- 准备一个安静、网络稳定的环境
- 提前测试麦克风和摄像头

## 面试中

- 先思考再回答，不需要立即给出答案
- 遇到不会的问题诚实地说明
- 注意语速和表达清晰度

## 面试后

- 仔细阅读评分反馈
- 将错题加入错题本
- 针对薄弱环节反复练习
""",
        "content_type": "article",
        "read_time_minutes": 8,
        "sort_order": 1,
    },
    {
        "title": "行为面试 STAR 法则详解",
        "summary": "用 STAR 法则组织你的经历，让面试官印象深刻",
        "category": "interview_tips",
        "tags": ["行为面试", "STAR", "沟通"],
        "content": """# 行为面试 STAR 法则详解

STAR 是 Situation（情境）、Task（任务）、Action（行动）、Result（结果）的缩写。

## Situation

描述当时的背景。例如："在上一个项目中，我们团队需要在 3 个月内交付一个新功能。"

## Task

明确你的任务。例如："我负责设计并实现后端 API。"

## Action

说明你采取的具体行动。例如："我使用了微服务架构，将系统拆分为 3 个独立服务。"

## Result

量化结果。例如："系统性能提升 40%，按时交付。"

## 准备方法

- 准备 5-7 个核心经历
- 每个经历用 STAR 框架组织
- 练习时录音回听
""",
        "content_type": "article",
        "read_time_minutes": 12,
        "sort_order": 2,
    },
    {
        "title": "常见算法题模板",
        "summary": "覆盖面试最高频的算法题型和解题模板",
        "category": "tech_prep",
        "tags": ["算法", "模板", "LeetCode"],
        "content": """# 常见算法题模板

## 二分搜索

```python
def binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
```

## DFS

```python
def dfs(node, visited):
    visited.add(node)
    for neighbor in node.neighbors:
        if neighbor not in visited:
            dfs(neighbor, visited)
```
""",
        "content_type": "article",
        "read_time_minutes": 20,
        "sort_order": 2,
    },
    {
        "title": "面试自我介绍模板",
        "summary": "简洁有力的自我介绍框架",
        "category": "interview_tips",
        "tags": ["自我介绍", "开场"],
        "content": """# 面试自我介绍模板

## 结构

1. 你是谁（教育背景/当前职位）
2. 你的核心优势（2-3 点）
3. 为什么对这个岗位感兴趣

## 示例

"面试官好，我是张三，目前在某公司担任高级后端工程师。我有 5 年分布式系统开发经验，擅长微服务架构和性能优化。我对贵公司的技术栈和业务方向非常感兴趣，尤其是在大规模系统设计方面。"
""",
        "content_type": "template",
        "read_time_minutes": 5,
        "sort_order": 3,
    },
]

FAQ = [
    {
        "question": "如何注销账号?",
        "answer": "前往 **Settings → 安全** 点击「注销账号」，经过 7 天冷静期后，系统将在 90 天后自动清除您的数据。冷静期内可随时取消。",
        "category": "account",
        "sort_order": 1,
    },
    {
        "question": "注销后数据如何处理?",
        "answer": "发起注销后 90 天物理清除所有数据，包括简历、面试记录、错题本、能力画像等。不可恢复。",
        "category": "account",
        "sort_order": 2,
    },
    {
        "question": "如何取消注销?",
        "answer": "在 7 天冷静期内，前往 Settings → 安全 或直接访问账号状态页面，点击「取消注销」即可。冷静期过后无法取消。",
        "category": "account",
        "sort_order": 3,
    },
    {
        "question": "如何开始模拟面试?",
        "answer": "在 Dashboard 或面试页面点击「开始面试」，选择面试类型（技术/行为/系统设计）后即可开始。每次面试包含 5 道题目。",
        "category": "interview",
        "sort_order": 1,
    },
    {
        "question": "面试成绩如何计算?",
        "answer": "每道题 AI 会从正确性、完整性、表达清晰度等维度评分，总分 100 分。面试结束后生成详细的能力报告。",
        "category": "interview",
        "sort_order": 2,
    },
    {
        "question": "如何创建简历分支?",
        "answer": "在简历列表页面点击「新建分支」，可从主分支或已有分支创建。不同分支可以针对不同岗位定制。",
        "category": "resume",
        "sort_order": 1,
    },
    {
        "question": "免费版和 Pro 版的区别?",
        "answer": "免费版每月 500,000 token 配额，Pro 版 5,000,000 token + 优先支持。Enterprise 版支持自定义配额。",
        "category": "subscription",
        "sort_order": 1,
    },
    {
        "question": "如何查看剩余配额?",
        "answer": "前往 Settings → 订阅与计费，页面顶部显示本月用量和剩余配额。",
        "category": "subscription",
        "sort_order": 2,
    },
    {
        "question": "网站加载缓慢怎么办?",
        "answer": "请检查网络连接，尝试刷新页面。如持续有问题，可查看我们的系统状态页面或联系技术支持。",
        "category": "technical",
        "sort_order": 1,
    },
]


async def seed_content(db: AsyncSession) -> dict:
    """Seed resources and FAQ data. Returns counts of seeded items."""
    # Check if data exists
    from sqlalchemy import select, func
    count_result = await db.execute(select(func.count()).select_from(Resource))
    existing_resources = count_result.scalar() or 0

    seeded_resources = 0
    seeded_faq = 0

    if existing_resources == 0:
        for item in RESOURCES:
            resource = Resource(**item)
            db.add(resource)
            seeded_resources += 1

    count_result = await db.execute(select(func.count()).select_from(HelpFAQ))
    existing_faq = count_result.scalar() or 0

    if existing_faq == 0:
        for item in FAQ:
            faq = HelpFAQ(**item)
            db.add(faq)
            seeded_faq += 1

    if seeded_resources > 0 or seeded_faq > 0:
        await db.flush()

    return {"seeded_resources": seeded_resources, "seeded_faq": seeded_faq}
