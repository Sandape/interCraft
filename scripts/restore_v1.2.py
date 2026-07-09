#!/usr/bin/env python
"""Restore v1.2 baseline from v1.3 by inverting the 3 v1.3 additions.

Inverts:
1. Frontmatter: version 1.3.0 -> 1.2.0, drop v1.3 description
2. SKILL.md: remove 'Init scope detection' and 'Lesson memory subsystem' sections
3. SKILL.md: re-add bilingual headers to 2 references and 2 new files (init-scope-detection.md, self-iteration.md) - delete them from snapshot
4. Working directory: remove lessons/, init_report.md
5. Lessons files: delete
6. detect_completed_reqs.sh: delete
7. state.json: revert to v1.2 schema (no init_scope, update_scope, lesson_version)
"""
import os, shutil

ROOT = 'D:/Project/eGGG/.claude/skills/test-acceptance-workspace/skill-snapshot-v1.2'

# 1. SKILL.md -> v1.2 (rewrite minimal v1.2)
SKILL_V12 = '''---
name: test-acceptance
description: >
  Acceptance testing automation skill. 4 commands: init (full test plan generation), update (incremental test plan), full run (full regression execution), deltarun (incremental execution).
  MUST USE when the user mentions acceptance test / regression / full run / delta run / init test / E2E full run / speckit 验收/验收报告/测试计划. Also applicable to any automated acceptance testing scenario.
  Depends on /speckit-specify output spec.md, and Playwright MCP for browser automation.
  [MANDATORY] init phase auto-detects browser MCP and database MCP, fail-fast if required MCP is missing.
triggers:
  - acceptance: acceptance test / full run / delta run / init test / regression test
  - test: test plan / test execution / acceptance report
  - speckit: speckit 验收/speckit 测试/验收需求
  - mcp: detect MCP / check MCP / install MCP
metadata:
  version: 1.2.0
---

# test-acceptance — 验收测试自动化技能 (v1.2 BASELINE)

## 设计原则

- **项目无关**：通过 `.test-acceptance/config.yaml` 注入项目上下文，不绑定 InterCraft 或任何特定项目。
- **4 命令闭环**：`init`（全量方案）→ `update`（增量方案）→ `full run`（全量执行）→ `deltarun`（增量执行）。
- **MCP 探活为先**：init 阶段必检浏览器 + 数据库 MCP，缺则 fail-fast + 给安装指引。
- **5 agent + main-agent 混合编排**：main-agent 拆任务→planner→redteam→re-verifier→tester→healer（v1.1 新增 healer + re-verifier）。
- **严格 + 宽松双轨 AC 验证**：strict grep / pytest 双通道（REQ-038 L031 模式）。
- **确定性门控**：每次 sub-agent 调用前执行 7 门控检查（GATE1-7），AI 只做翻译不做验证（v1.1 新增）。
- **自愈机制**：TC 失败后 healer agent 按 severity gate 决定 auto-fix（选择器/等待）或 escalate（复杂故障报用户）（v1.1 新增）。
- **独立重验证**：planner 产出后独立 agent 重新探索 app 验证覆盖率（v1.1 新增）。
- **Seed test 模式**：`seed.spec.ts` 提供预初始化 page 上下文（v1.1 新增）。
- **Flaky 分析**：Wilson score 置信区间 + JSON 存储 + quarantine 自动跳过（v1.2 新增）。
- **视觉回归混合策略**：SHA256 → pixelmatch → 多模态 AI 3 层降级（v1.2 新增）。
- **CI/CD 集成**：GitHub Actions composite action + quality gate（v1.2 新增）。
- **历史趋势**：state.json run_history + trend_report（v1.2 新增）。
- **中英双语报告**：所有报告同时输出中文 + 英文。
- **依赖 `/speckit-specify`**：读 `specs/NNN-{slug}/spec.md` 作为需求真相。

## init 流程 (v1.2)

1. **MCP 探活** — 浏览器 + DB
2. **项目类型识别**
3. **DB 类型映射**
4. **生成 config.yaml**
5. **读 specs/** — 扫描全部 `specs/NNN-{slug}/spec.md` (无 completed 检测)
6. **Spawn planner** — 每个 feature 1 个 planner agent
7. **Spawn redteam** — 3 轮迭代
8. **独立重验证** — re-verifier agent
9. **写全局资产** — spec_snapshots = content hash
10. **Lock + finalize**

> v1.2 缺陷: spec `**Status**` 字段 100% stale，无法区分 completed vs active REQ。
> v1.2 缺陷: 无 lesson memory 子系统，错过 BUG 后无 prevention 机制。

## update 流程 (v1.2)

1. 读 `state.json.spec_snapshots`
2. 重扫 specs/ + plan.md + tasks.md
3. 差集算法: spec.md hash 变 -> 重新 plan; 仅 src 变 -> 不触发
4. 增量 planner + redteam

## full run 流程 (v1.2)

[standard 15-step flow, runs all active TC]

## deltarun 流程 (v1.2)

[standard 8-step flow, runs changed-feature TC only]
'''
with open(f'{ROOT}/SKILL.md', 'w', encoding='utf-8') as f:
    f.write(SKILL_V12)
print('Wrote v1.2 SKILL.md')

# 2. Delete v1.3 new files from snapshot
for f in [
    f'{ROOT}/references/init-scope-detection.md',
    f'{ROOT}/references/self-iteration.md',
    f'{ROOT}/scripts/detect_completed_reqs.sh',
]:
    if os.path.exists(f):
        os.remove(f)
        print(f'Removed: {f}')

# 3. Delete lessons/ subdir if present
lessons_dir = f'{ROOT}/lessons'
if os.path.exists(lessons_dir):
    shutil.rmtree(lessons_dir)
    print(f'Removed dir: {lessons_dir}')

print('v1.2 snapshot restored.')
