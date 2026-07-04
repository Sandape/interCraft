#!/usr/bin/env bash
# worktree-create.sh — 创建或复用 git worktree
# 用法：worktree-create.sh <team-id> [base-commit]
#   base-commit 默认 = HEAD
# 副作用：
#   - 在 <repo>/.worktrees/<team-id>/ 创建 worktree
#   - 分支 team/<team-id>/master
# 幂等：如果 worktree 已存在且分支匹配，直接复用
# 输出：worktree path (stdout)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_repo

TEAM_ID="${1:-}"
BASE_COMMIT="${2:-}"

if [ -z "$TEAM_ID" ]; then
  die "usage: worktree-create.sh <team-id> [base-commit]"
fi
if [ "$(is_valid_team_id "$TEAM_ID")" != "yes" ]; then
  die "invalid team-id: $TEAM_ID"
fi

WT_PATH="$(worktree_path "$TEAM_ID")"
WT_BRANCH="$(worktree_branch "$TEAM_ID")"

# 兜底：如果不在主仓库里，切回去（用户/前置调用可能 cd 进去了）
CURRENT_TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$CURRENT_TOPLEVEL" ] && [ "$CURRENT_TOPLEVEL" != "$REPO_ROOT" ]; then
  log "检测到当前目录在 worktree 内，切回主 repo: $REPO_ROOT"
  cd "$REPO_ROOT"
fi

# 幂等：如果 worktree 已存在
if [ -d "$WT_PATH" ]; then
  if [ -d "$WT_PATH/.git" ] || [ -f "$WT_PATH/.git" ]; then
    # 检查分支是否匹配
    EXISTING_BRANCH="$(git -C "$WT_PATH" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
    if [ "$EXISTING_BRANCH" = "$WT_BRANCH" ]; then
      log "worktree 已存在且分支匹配，复用：$WT_PATH"
      echo "$WT_PATH"
      exit 0
    fi
    die "worktree $WT_PATH 已存在但分支是 '$EXISTING_BRANCH'（期望 '$WT_BRANCH'）。请用不同 team-id 或先清理。"
  fi
  die "worktree 路径 $WT_PATH 存在但不是 git worktree。请手动删除或改名。"
fi

# 检查分支是否已存在（可能别的 team 同名）
if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$WT_BRANCH"; then
  log "分支 $WT_BRANCH 已存在，复用到该分支"
  git -C "$REPO_ROOT" worktree add "$WT_PATH" "$WT_BRANCH" >&2
  echo "$WT_PATH"
  exit 0
fi

# 默认 base = HEAD
if [ -z "$BASE_COMMIT" ]; then
  BASE_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
fi

# 创建
mkdir -p "$(dirname "$WT_PATH")"
git -C "$REPO_ROOT" worktree add -b "$WT_BRANCH" "$WT_PATH" "$BASE_COMMIT" >&2 \
  || die "git worktree add 失败（分支已存在？磁盘满？）"

log "worktree 创建成功：$WT_PATH @ $WT_BRANCH (base=$BASE_COMMIT)"
echo "$WT_PATH"