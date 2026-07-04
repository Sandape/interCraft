#!/usr/bin/env bash
# merge.sh — 合并 team 分支回 master（§6 Phase 3 v3）
# 用法：merge.sh <team-id>
# 流程：
#   1. cd 主 repo（仅做 merge 接驳）
#   2. 切到 team/<id> worktree（在 worktree 内 rebase）
#   3. git fetch origin master + git rebase origin/master
#   4. 切回主 repo
#   5. git merge --no-ff team/<id>/master（持全局 merge-lock 串行化）
#   6. 更新 state.json (terminal_status=merged)
# 幂等：已 merged 状态直接跳过

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_repo

TEAM_ID="${1:-}"
if [ -z "$TEAM_ID" ]; then
  die "usage: merge.sh <team-id>"
fi
if [ "$(is_valid_team_id "$TEAM_ID")" != "yes" ]; then
  die "invalid team-id: $TEAM_ID"
fi

STATE_FILE="$(team_state "$TEAM_ID")"
WT_BRANCH="$(worktree_branch "$TEAM_ID")"
WT_PATH="$(worktree_path "$TEAM_ID")"

# ============ 幂等检查 ============
if [ -f "$STATE_FILE" ]; then
  TERMINAL="$("$PYTHON_BIN" -c "
import json
with open('$STATE_FILE', 'r', encoding='utf-8') as fp:
    s = json.load(fp)
print(s.get('terminal_status') or '')
")"
  case "$TERMINAL" in
    merged)
      log "team=$TEAM_ID 已 merged，跳过"
      exit 0 ;;
    cleaned)
      log "team=$TEAM_ID 已 cleaned，跳过"
      exit 0 ;;
  esac
fi

# ============ 前置检查 ============
if [ ! -d "$WT_PATH" ]; then
  die "worktree 不存在：$WT_PATH（先跑 preflight.sh）"
fi
if ! git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$WT_BRANCH"; then
  die "分支 $WT_BRANCH 不存在"
fi

# ============ 全局 merge lock（关键）============
#   多个并发 merge.sh 会对同一个 .git/HEAD 写竞争（git 自身无法处理）
#   用 mkdir-based advisory lock 串行化所有 merge
MERGE_LOCK="$CLAUDE_DIR/.merge-global.lock"

with_merge_lock() {
  local i=0
  while ! mkdir "$MERGE_LOCK" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 60 ]; then
      die "等待 merge lock 超时（60s）"
    fi
    sleep 1
  done
  trap "rmdir '$MERGE_LOCK' 2>/dev/null || true" EXIT
}

log "等待全局 merge lock @ $MERGE_LOCK"
with_merge_lock
log "获取 merge lock，进入临界区"

# ============ 1. fetch ============
log "git fetch origin master"
git -C "$REPO_ROOT" fetch origin master 2>&1 | sed 's/^/[fetch] /' || log "fetch 失败（offline？继续）"

# ============ 2. 清理陈旧的 MERGE_HEAD / REBASE_HEAD（防御性）============
#   上次 merge 中途失败可能留下 MERGE_HEAD，导致后续 merge 全部 bail
log "检查陈旧 MERGE_HEAD / REBASE_HEAD"
cd "$REPO_ROOT"
if [ -f .git/MERGE_HEAD ] || [ -f .git/REBASE_HEAD ]; then
  log "检测到陈旧 merge/rebase 状态，abort 中"
  git merge --abort 2>&1 | sed 's/^/[merge-abort] /' || true
  git rebase --abort 2>&1 | sed 's/^/[rebase-abort] /' || true
  # 兜底：手工清残留文件
  rm -f .git/MERGE_HEAD .git/MERGE_MSG .git/MERGE_MODE .git/REBASE_HEAD .git/REBASE_DIR
fi

# ============ 3. 在 worktree 内 rebase ============
#   不能在主 repo 切到 team 分支（已被 worktree 占用）
log "cd $WT_PATH rebase onto origin/master"
cd "$WT_PATH"
if ! git rebase origin/master 2>&1 | sed 's/^/[rebase] /'; then
  log "rebase 冲突！abort 中"
  git rebase --abort 2>&1 | sed 's/^/[abort] /' || true
  die "merge 失败：rebase 冲突。请人工裁决后重新跑 merge.sh"
fi

# ============ 4. 切回主 repo 做 merge ============
cd "$REPO_ROOT"
log "cd $REPO_ROOT + git merge --no-ff $WT_BRANCH"

# ============ 4a. Layer 3: pre-merge 服务存活守卫 ============
#   即使没跑 cleanup.sh，merge 前也要确认端口空闲；占用就 Layer 2 兜底
if [ -f "$(team_ports "$TEAM_ID")" ]; then
  log "Layer 3: pre-merge 端口存活检查"
  PORTS_JSON="$(cat "$(team_ports "$TEAM_ID")")"
  # Python 输出在 Windows 上带 \r，bash for 会把 \r 保留 — 改用 mapfile + 手动 trim
  while IFS= read -r p; do
    p="${p%$'\r'}"  # 去掉 Windows \r
    [ -z "$p" ] && continue
    if [ "$(is_port_in_use "$p")" = "yes" ]; then
      log "WARN: port $p 仍被占用（merge 前清理）"
      bash "$SCRIPT_DIR/team-svc.sh" kill-port "$p" 2>&1 | sed 's/^/[merge-kill-port] /' || log "kill-port $p 失败"
    fi
  done < <(echo "$PORTS_JSON" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(d.get('backend','')); print(d.get('frontend',''))" 2>/dev/null)
fi

if ! git merge --no-ff "$WT_BRANCH" -m "merge team=$TEAM_ID branch=$WT_BRANCH into master" 2>&1 | sed 's/^/[merge] /'; then
  log "merge 失败，清理 MERGE_HEAD 残留"
  git merge --abort 2>&1 | sed 's/^/[merge-abort] /' || true
  rm -f .git/MERGE_HEAD .git/MERGE_MSG .git/MERGE_MODE
  die "merge 失败（冲突或 fast-forward 拒绝）"
fi

# ============ 4. state.json 标记 merged ============
"$PYTHON_BIN" -c "
import json, time
with open('$STATE_FILE', 'r', encoding='utf-8') as fp:
    s = json.load(fp)
s['terminal_status'] = 'merged'
s['merged_at'] = time.strftime('%y%m%d %H%M')
s['merged_commit'] = '$(git -C "$REPO_ROOT" rev-parse HEAD)'
s['updated_at'] = time.strftime('%y%m%d %H%M')
with open('$STATE_FILE', 'w', encoding='utf-8') as fp:
    json.dump(s, fp, ensure_ascii=False, indent=2)
"

# ============ 5. registry 更新 ============
pyjson_update "$REGISTRY_FILE" "
if 'teams' in data and '$TEAM_ID' in data['teams']:
    data['teams']['$TEAM_ID']['status'] = 'merged'
    data['teams']['$TEAM_ID']['updated_at'] = time.strftime('%y%m%d %H%M')
data['updated_at'] = time.strftime('%y%m%d %H%M')
"

log "[TEAM=$TEAM_ID] merge 完成（commit=$(git -C "$REPO_ROOT" rev-parse --short HEAD)）"