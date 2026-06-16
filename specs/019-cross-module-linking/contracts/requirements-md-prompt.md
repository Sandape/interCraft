# Contract: question_gen Prompt Injection (requirements_md)

**Feature**: 019-cross-module-linking | **Date**: 2026-06-17

> 本文档定义 `LangGraph question_gen` 节点 prompt 注入 `requirements_md` 的契约。让 AI 出题时基于岗位招聘需求出针对性题目,提升模拟面试的真实度。

## 1. GraphState 扩展

```python
# backend/app/agents/interview/state.py
class InterviewGraphState(TypedDict):
    # Phase 4 既有字段(messages / current_question / questions / scores / ...)
    # ...

    # 019 新增
    requirements_md: str | None          # 来自 jobs.requirements_md
    requirements_provided: bool          # 是否成功注入
    requirements_truncated: bool         # 是否被截断
    requirements_original_chars: int     # 原始字符数(用于日志)
```

## 2. prompt 注入点

### 2.1 system message 扩展

```python
SYSTEM_PROMPT = """你是面试官,正在面试候选人。
岗位:{position}
公司:{company}
base 地:{base_location}

{requirements_md_block}

你的任务是根据上述岗位信息,出一道与该岗位招聘需求高度相关的面试题。
"""
```

### 2.2 requirements_md_block 构造

```python
def build_requirements_block(requirements_md: str | None) -> tuple[str, bool, bool, int]:
    """返回 (block_text, requirements_provided, requirements_truncated, original_chars)"""
    if not requirements_md or not requirements_md.strip():
        return "", False, False, 0

    original_chars = len(requirements_md)
    # tiktoken 截断
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4")  # DeepSeek 兼容
    tokens = enc.encode(requirements_md)

    if len(tokens) <= MAX_REQUIREMENTS_TOKENS:  # 1500
        return (
            f"## 岗位招聘需求\n{requirements_md}",
            True, False, original_chars
        )

    truncated_tokens = tokens[:MAX_REQUIREMENTS_TOKENS]
    truncated_text = enc.decode(truncated_tokens)
    return (
        f"## 岗位招聘需求(已截断到前 {MAX_REQUIREMENTS_TOKENS} token)\n{truncated_text}",
        True, True, original_chars
    )
```

### 2.3 截断日志

```python
logger.info(
    "requirements_md_truncated" if truncated else "requirements_md_injected",
    session_id=session_id,
    original_chars=original_chars,
    truncated_to_tokens=MAX_REQUIREMENTS_TOKENS if truncated else len(tokens),
    ratio=len(tokens) / MAX_REQUIREMENTS_TOKENS if truncated else 1.0,
)
```

## 3. MAX_REQUIREMENTS_TOKENS 常量

```python
# backend/app/agents/interview/graph.py
MAX_REQUIREMENTS_TOKENS = 1500
```

**理由**:
- DeepSeek V4 Pro 上下文窗 32K,1500 token 占 4.7%,安全裕度充足
- 题目生成 prompt 本身需 ~500 token(question + answer)
- 5 轮对话历史 messages 累计 ~3K token
- 用户简历内容 ~1K token
- 招聘需求 1500 token → 总计 ~6K token,远低于 32K

## 4. requirements_md 来源

### 4.1 服务端注入(Phase 4 intake 节点)

`intake` 节点在 GraphState 初始化时:
```python
async def intake_node(state: InterviewGraphState) -> InterviewGraphState:
    # Phase 4 既有:读取 position / company / branch_id
    # ...

    # 019 新增:读取 job_id → jobs.requirements_md
    if state.get("job_id"):
        job = await job_repository.get(state["job_id"], state["user_id"])
        if job and job.requirements_md:
            state["requirements_md"] = job.requirements_md
            state["requirements_original_chars"] = len(job.requirements_md)
    # ...
```

### 4.2 前端 Intake 阶段回显

前端 Intake 表单从 `GET /jobs/{job_id}` 取 `requirements_md`,以折叠卡片形式展示(只读),用户可参考但不强制改写(详见 interview-job-id.md §8)。

## 5. report 节点输出

```python
async def report_node(state: InterviewGraphState) -> InterviewGraphState:
    # Phase 4 既有:生成 summary_md / strengths / improvements
    # ...

    # 019 新增:在 report 中追加"招聘需求摘要"段
    if state.get("requirements_provided"):
        req = state["requirements_md"]
        truncated = req[:500] + ("..." if len(req) > 500 else "")  # 前 500 字符
        state["report"]["requirements_summary"] = (
            f"## 该面试基于以下招聘需求(摘要)\n{truncated}"
        )
    # ...
```

## 6. 兼容性

- GraphState 是 TypedDict,新增字段对 Phase 4 既有 checkpoint 恢复无影响(老 state 没有该字段,默认 None)。
- prompt template 用 Jinja2 占位符 `{{requirements_md_block}}`,Phase 4 既有测试可 mock 该变量为空字符串(行为退化)。
- `intake` 节点读取 `job_id` 是新增逻辑;若 `job_id` 为 None,跳过需求注入,行为与 Phase 4 一致。

## 7. 验证场景

### 7.1 单测:`build_requirements_block`

```python
def test_build_requirements_block_empty():
    text, provided, truncated, chars = build_requirements_block(None)
    assert text == ""
    assert provided is False
    assert truncated is False
    assert chars == 0

def test_build_requirements_block_short():
    md = "## 要求\n- 3年 React 经验"
    text, provided, truncated, chars = build_requirements_block(md)
    assert provided is True
    assert truncated is False
    assert "## 岗位招聘需求" in text
    assert md in text
    assert chars == len(md)

def test_build_requirements_block_long():
    md = "x" * 50000  # 假设编码后 > 1500 token
    text, provided, truncated, chars = build_requirements_block(md)
    assert provided is True
    assert truncated is True
    assert "已截断到前 1500 token" in text
    assert chars == 50000
```

### 7.2 单测:report 节点输出

```python
async def test_report_with_requirements():
    state = {
        "requirements_md": "## 要求\n- React",
        "requirements_provided": True,
        # ...
    }
    report = await report_node(state)
    assert "requirements_summary" in report["report"]
    assert "## 该面试基于以下招聘需求" in report["report"]["requirements_summary"]

async def test_report_without_requirements():
    state = {
        "requirements_md": None,
        "requirements_provided": False,
        # ...
    }
    report = await report_node(state)
    assert "requirements_summary" not in report["report"]
```

### 7.3 集成测试:从 Job 开面试的端到端

```python
async def test_interview_with_job_uses_requirements():
    # 创建 job 带 requirements_md
    job = await create_job(..., requirements_md="## 要求\n- Rust 后端 3 年")

    # 从 job 开面试
    session = await create_interview_session(job_id=job.id, branch_id=job.branch_id)

    # 跑 1 轮 question_gen,捕获 prompt
    state = await run_intake(session.id)
    prompt = build_question_gen_prompt(state)
    assert "Rust 后端 3 年" in prompt
    assert state["requirements_provided"] is True
```
