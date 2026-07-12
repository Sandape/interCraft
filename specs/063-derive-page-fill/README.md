# REQ-063 — 派生简历满页校准与真实页数一致

| Field | Value |
|---|---|
| Requirement ID | REQ-063 |
| Spec directory | `specs/063-derive-page-fill` |
| Status | planned (tasks ready; implement pending) |
| Spec | [spec.md](./spec.md) |
| Plan | [plan.md](./plan.md) |
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Quickstart | [quickstart.md](./quickstart.md) |
| Contracts | [contracts/](./contracts/) |
| Tasks | [tasks.md](./tasks.md) |
| Quality checklist | [checklists/requirements.md](./checklists/requirements.md) |

## Summary

纠正派生「实际页数」失真，使目标 N 页的派生稿在成功态下为内容充实的 N 页：真实分页测量 + 末页填充率决策（先调行距，再 Agent 剪枝/扩写）+ 保存回写 + PDF 终裁。

## Note on numbering

User initially asked for REQ-062; that ID is reserved for commercial payment (`specs/062-commercial-payment`). This feature is REQ-063.

## Next

1. `/speckit-implement`（建议从 US1 MVP：T001–T029）
2. Optional: `/speckit-checklist` / `/speckit-analyze`
