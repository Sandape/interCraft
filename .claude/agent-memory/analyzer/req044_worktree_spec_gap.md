---
name: req044-worktree-spec-gap
description: req044 worktree base_commit predates specs/044 directory creation; spec lives in main as untracked, must be synced before any REQ-044 work
metadata:
  project
---

req044 team worktree at `D:/Project/eGGG/.worktrees/req044` was created from base_commit `5669c7d3` (5669c7d), but `specs/044-admin-console-redesign/` was added AFTER — currently exists only in main repo (`D:/Project/eGGG/specs/044-admin-console-redesign/{spec.md,requirements-status.md,checklists/,README.md}`) as **untracked**.

**Why:** 主 Agent 开工前 044 spec 必须从主仓同步进 worktree（cp -r 或 git add + cherry-pick），否则 executor 读不到 spec.md。

**How to apply:** When pool entry references `specs/044-admin-console-redesign/spec.md`, 主 Agent 必须先 verify 该路径在 worktree 存在。analyzer 在后续 incremental scan 时也要先 `ls specs/044-*-admin*` 确认。`.specify/feature.json` 仍指着 `specs/044-admin-console-redesign` 需要 checkout 时重写或 rsync。
