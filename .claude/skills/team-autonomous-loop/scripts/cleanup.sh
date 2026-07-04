#!/usr/bin/env bash
# cleanup.sh — 释放端口 + git push 分支（保留 worktree）
# 用法：cleanup.sh <team-id> [--aggressive]
#   --aggressive : 同时 git worktree remove + git branch -D
# 副作用：
#   - 调 port-release.sh
#   - git push origin team/<id>/master (若本地有新 commit)
#   - 更新 state.json (terminal_status=cleaned)
# 幂等：可重复执行

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_repo

TEAM_ID="${1:-}"
AGGRESSIVE="false"
for arg in "$@"; do
  case "$arg" in
    --aggressive|-a) AGGRESSIVE="true" ;;
    *) [ -z "$TEAM_ID" ] && TEAM_ID="$arg" ;;
  esac
done

if [ -z "$TEAM_ID" ]; then
  die "usage: cleanup.sh <team-id> [--aggressive]"
fi
if [ "$(is_valid_team_id "$TEAM_ID")" != "yes" ]; then
  die "invalid team-id: $TEAM_ID"
fi

STATE_FILE="$(team_state "$TEAM_ID")"
WT_PATH="$(worktree_path "$TEAM_ID")"
WT_BRANCH="$(worktree_branch "$TEAM_ID")"

# ============ 幂等检查 ============
if [ -f "$STATE_FILE" ]; then
  TERMINAL="$("$PYTHON_BIN" -c "
import json
with open('$STATE_FILE', 'r', encoding='utf-8') as fp:
    s = json.load(fp)
print(s.get('terminal_status') or '')
")"
  case "$TERMINAL" in
    cleaned|merged)
      log "team=$TEAM_ID 已 $TERMINAL，跳过 cleanup（仍可继续 aggressive 路径）"
      if [ "$AGGRESSIVE" != "true" ]; then
        exit 0
      fi ;;
  esac
fi

# ============ 1. 强杀服务（Layer 1: PID tracking）============
# 先按 tracked services.json 里的 PID taskkill /T /F
if [ -f "$(team_dir "$TEAM_ID")/services.json" ]; then
  log "Layer 1: 杀 tracked services (services.json)"
  bash "$SCRIPT_DIR/team-svc.sh" stop "$TEAM_ID" 2>&1 | sed 's/^/[svc-stop] /' || log "service stop 失败，继续"
else
  log "Layer 1: 无 services.json，跳过 tracked kill"
fi

# ============ 1b. 端口级兜底（Layer 2: netstat 强杀）============
# 即便 Layer 1 漏了（裸 uvicorn / 手动启动的），也按端口再扫一遍
if [ -f "$(team_ports "$TEAM_ID")" ]; then
  PORTS_JSON="$(cat "$(team_ports "$TEAM_ID")")"
  while IFS= read -r p; do
    p="${p%$'\r'}"  # 去 Windows \r
    [ -z "$p" ] && continue
    bash "$SCRIPT_DIR/team-svc.sh" kill-port "$p" 2>&1 | sed 's/^/[kill-port] /' || true
  done < <(echo "$PORTS_JSON" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(d.get('backend','')); print(d.get('frontend',''))" 2>/dev/null)
fi

# ============ 2. 释放端口池标记 ============
log "释放端口池标记"
bash "$SCRIPT_DIR/port-release.sh" "$TEAM_ID"

# ============ 2. push 分支（best-effort）============
cd "$REPO_ROOT"
if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$WT_BRANCH"; then
  # 检查本地相对 remote 是否有新 commit
  git fetch origin "$WT_BRANCH" 2>/dev/null || true
  AHEAD="$(git rev-list --count "origin/$WT_BRANCH..$WT_BRANCH" 2>/dev/null || echo "0")"
  if [ "$AHEAD" -gt 0 ]; then
    log "本地领先 origin $AHEAD 个 commit，push"
    if ! git push origin "$WT_BRANCH" 2>&1 | sed 's/^/[push] /'; then
      log "push 失败（offline 或权限）。继续 cleanup，不阻塞"
    fi
  else
    log "无新 commit，跳过 push"
  fi
else
  log "分支 $WT_BRANCH 不存在本地，跳过 push"
fi

# ============ 3. aggressive：删 worktree + branch ============
if [ "$AGGRESSIVE" = "true" ]; then
  if [ -d "$WT_PATH" ]; then
    log "--aggressive: 删除 worktree $WT_PATH"
    git -C "$REPO_ROOT" worktree remove --force "$WT_PATH" 2>&1 | sed 's/^/[wt-rm] /' \
      || log "worktree remove 失败（可能分支已 checkout 在别处）"
  fi
  if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$WT_BRANCH"; then
    log "--aggressive: 删除分支 $WT_BRANCH"
    git -C "$REPO_ROOT" branch -D "$WT_BRANCH" 2>&1 | sed 's/^/[br-del] /' || true
  fi
fi

# ============ 4. state.json + registry 标记 ============
if [ -f "$STATE_FILE" ]; then
  "$PYTHON_BIN" -c "
import json, time
with open('$STATE_FILE', 'r', encoding='utf-8') as fp:
    s = json.load(fp)
s['terminal_status'] = 'cleaned'
s['cleaned_at'] = time.strftime('%y%m%d %H%M')
s['updated_at'] = time.strftime('%y%m%d %H%M')
if '$AGGRESSIVE' == 'true':
    s['worktree_removed'] = True
    s['branch_removed'] = True
with open('$STATE_FILE', 'w', encoding='utf-8') as fp:
    json.dump(s, fp, ensure_ascii=False, indent=2)
"
fi

"$PYTHON_BIN" -c "
import json, time, os
if os.path.exists('$REGISTRY_FILE'):
    with open('$REGISTRY_FILE', 'r', encoding='utf-8') as fp:
        reg = json.load(fp)
    if 'teams' in reg and '$TEAM_ID' in reg['teams']:
        reg['teams']['$TEAM_ID']['status'] = 'cleaned' if '$AGGRESSIVE' != 'true' else 'archived'
        reg['teams']['$TEAM_ID']['updated_at'] = time.strftime('%y%m%d %H%M')
    reg['updated_at'] = time.strftime('%y%m%d %H%M')
    with open('$REGISTRY_FILE', 'w', encoding='utf-8') as fp:
        json.dump(reg, fp, ensure_ascii=False, indent=2)
"

log "[TEAM=$TEAM_ID] cleanup 完成 (aggressive=$AGGRESSIVE)"