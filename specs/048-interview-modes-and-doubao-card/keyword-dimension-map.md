# JD Keyword → Dimension Map (REQ-048 AC-04b)

> **Generated**: 2026-07-07
> **Purpose**: Ground-truth fixture for `tests/integration/test_us2_drill_e2e.py` (AC-04b).
> **Coverage**: 10 关键词 → dimension 映射 (inline fallback).
> **Owner**: REQ-048 T094 (dev Batch E)

This file backs the AC-04b keyword→dimension mapping fixture. When
T094 outputs are unavailable (CI cold start, no `drill-eval-set.md`),
the test suite falls back to this 5-case inline fixture (AC-04c).

---

## Mapping Table

| Keyword (zh-CN) | Dimension | Scenario bucket |
|---|---|---|
| 分布式事务 | distributed_systems | distributed-systems-jd |
| 微服务 | architecture | architecture-jd |
| RAG | tech_depth | tech-depth-jd |
| 分布式锁 | distributed_systems | distributed-systems-jd |
| 服务降级 | architecture | architecture-jd |
| 一致性 | distributed_systems | distributed-systems-jd |
| Transformer | tech_depth | tech-depth-jd |
| 监控 | engineering_practice | engineering-practice-jd |
| 性能调优 | engineering_practice | engineering-practice-jd |
| 排序算法 | algorithm_design | algorithm-design-jd |

---

## Inline 5-case Fallback (AC-04c)

```python
INLINE_KEYWORD_DIMENSION_FIXTURE = [
    ("分布式事务", "distributed_systems"),
    ("微服务", "architecture"),
    ("RAG", "tech_depth"),
    ("分布式锁", "distributed_systems"),
    ("服务降级", "architecture"),
]
```

This is the hard-coded fallback used by
`tests/integration/test_us2_drill_e2e.py::test_inline_keyword_dimension_fixture`
when `docs/evidence/048-interview-modes-and-doubao-card/drill-eval-set.md`
is missing.

---

## Dimensions Reference

| Key | Display (zh-CN) | Description |
|---|---|---|
| `distributed_systems` | 分布式系统 | 分布式事务 / 一致性 / CAP / 锁 |
| `architecture` | 架构设计 | 微服务 / 服务降级 / 拆分 |
| `tech_depth` | 技术深度 | RAG / LLM / Transformer / 底层原理 |
| `engineering_practice` | 工程实践 | CI/CD / 监控 / 测试 / 性能调优 |
| `algorithm_design` | 算法设计 | 数据结构 / 复杂度 / 排序 / 搜索 |

---

## Test Usage

```bash
# AC-04b test invocation (when drill-eval-set.md is present):
cd backend && uv run pytest -q tests/integration/test_us2_drill_e2e.py::test_keyword_dimension_map -v

# AC-04c inline fixture test (always runs):
cd backend && uv run pytest -q tests/integration/test_us2_drill_e2e.py::test_inline_keyword_dimension_fixture -v
```

---

**Revision History**

| Date | Author | Change |
|---|---|---|
| 2026-07-07 | dev (REQ-048 Batch E T094) | Initial 10-keyword map + 5-case inline fallback (AC-04c contract) |