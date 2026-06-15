# M08 · 错题本

> 状态: draft · 所属领域: C · 优先级: P1
> 引用原文档: §3.2 (error_questions), §7.5

## 1. 需求摘要

落地错题本:面试中答错的题目自动入库,支持分类(category)/ 难度(difficulty)/ 频次(frequency)/ 最近错次时间 / 提示词字段;支持手动添加;支持按类别 / 难度 / 频次筛选。本模块**只做 CRUD**,错题强化训练由 M17 实现。

## 2. 验收标准

- [ ] `GET /api/v1/error-questions` 列表(支持 category / difficulty / sort by frequency desc / last_missed_at desc)
- [ ] `POST /api/v1/error-questions` 手动新建
- [ ] `PATCH /api/v1/error-questions/{id}` 部分更新(主要是 frequency 与 last_missed_at)
- [ ] `DELETE /api/v1/error-questions/{id}` 软删除
- [ ] `POST /api/v1/error-questions/{id}/recall` 上报「答对一次」→ frequency--,frequency=0 自动归档(或保留观察)
- [ ] 面试结束时(M15 调用)→ 自动写入答错的题目,frequency++

## 3. 依赖与被依赖关系

**强依赖**: M02(表)、M05(RLS)
**弱依赖**: 无
**被以下模块依赖**: M15(Interview 子图写入)、M17(Error Coach 子图读)、M23(前端错题本页)
**外部依赖**: 无

## 4. 数据模型

**`error_questions` 表**:
```
id UUID PK
user_id UUID NOT NULL (Mixin)
question TEXT NOT NULL  -- 题目原文
question_hash CHAR(64) NOT NULL  -- sha256(question),去重用
category TEXT NOT NULL  -- 系统设计 / 算法 / 行为 / ...
difficulty TEXT NOT NULL  -- easy / medium / hard
frequency INT NOT NULL DEFAULT 1  -- 累计错题次数
last_missed_at TIMESTAMPTZ NOT NULL DEFAULT now()
hint TEXT NULL  -- 答题提示
source_interview_id UUID NULL FK(interview_sessions.id)  -- 首次出现的面试
created_at / updated_at / deleted_at
```

**约束**:
- `(user_id, question_hash)` 唯一(同一用户同一题目去重)

**索引**:
- `(user_id, last_missed_at DESC)`
- `(user_id, frequency DESC)`
- `(user_id, category)`

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/error-questions` | 列表(filter / sort / cursor) |
| POST | `/api/v1/error-questions` | 手动新建 |
| GET | `/api/v1/error-questions/{id}` | 详情 |
| PATCH | `/api/v1/error-questions/{id}` | 更新 hint / category / difficulty |
| DELETE | `/api/v1/error-questions/{id}` | 软删除 |
| POST | `/api/v1/error-questions/{id}/recall` | 上报「答对了」,frequency-- |

**Service 接口**(供 M15 调用):
```python
async def record_missed(user_id, question, category, difficulty, hint, source_interview_id):
    """面试错题入库,基于 question_hash upsert,frequency++"""
```

**工具**(LangGraph,见 M14):
- `query_error_book(user_id, category, limit) → list[ErrorQOut]` 供 M17 用

## 6. 关键设计点

- **去重 upsert**:同一题目重复入库时 frequency++,而非新建
- **hint 字段来源**:① 用户编辑 ② AI 在 Error Coach 子图(M17)中生成
- **难度自动评估**:可基于 LLM 评估(M15 中评估时附带);M08 阶段允许用户手动选
- **归档而非物理删**:frequency=0 后不删除,改 `archived_at` 字段(M08 不实现,M20 生命周期处理)

## 7. 待澄清

- 题目相似但不完全相同时是否合并(NLP 语义去重 vs 严格 hash):MVP 用严格 hash;v1.1 引入 embedding 相似度
- 错题分类的标准化:列举固定 categories(算法 / 系统设计 / OOP / 数据库 / 网络 / 行为 / ...)还是自由文本?MVP 用受控词表 + 自由文本兜底

## 8. 实现提示

- 文件: `backend/app/api/v1/error_questions.py`、`backend/app/services/error_question_service.py`、`backend/app/repositories/error_repo.py`
- 复用: 无
- 与 mockData 关系: `mockData.ts:276-323` `ErrorQuestion` → 直接落地;`lastMissed` 是相对时间字符串("3 天前"),后端存 `last_missed_at timestamptz`,前端格式化
