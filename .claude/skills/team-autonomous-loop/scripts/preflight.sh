#!/usr/bin/env bash
# preflight.sh — Phase -1 一键初始化（§6 v3 工作流第 1 步）
# 用法：preflight.sh [--team=<id>] [--base=<commit>]
# 副作用：
#   - 调用 port-cleanup.sh（TTL 回收）
#   - 调用 worktree-create.sh（建/复用 worktree）
#   - 调用 port-claim.sh（分端口）
#   - 创建 .claude/teams/<id>/{state.json, main-log.md, ports.json}
#   - 更新 .claude/team-registry.json
# 幂等：可重复执行（state.json 已存在则跳过初始化）
# 输出：JSON 单行 {team_id, worktree_path, branch, backend, frontend, fresh}

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_repo
check_layout

# ============ 参数解析 ============
TEAM_ID=""
BASE_COMMIT=""
for arg in "$@"; do
  case "$arg" in
    --team=*)  TEAM_ID="${arg#--team=}" ;;
    --base=*)  BASE_COMMIT="${arg#--base=}" ;;
    --help|-h)
      sed -n '2,10p' "$0" | sed 's/^# //'
      exit 0 ;;
    *) err "unknown arg: $arg"; exit 1 ;;
  esac
done

# ============ Team ID 解析 ============
if [ -z "$TEAM_ID" ]; then
  TEAM_ID="$(bash "$SCRIPT_DIR/team-id-resolve.sh")" \
    || die "无法解析 team-id"
fi
if [ "$(is_valid_team_id "$TEAM_ID")" != "yes" ]; then
  die "invalid team-id: $TEAM_ID"
fi

STATE_FILE="$(team_state "$TEAM_ID")"
LOG_FILE="$(team_log "$TEAM_ID")"
PORTS_FILE="$(team_ports "$TEAM_ID")"
TEAM_DIR_PATH="$(team_dir "$TEAM_ID")"
WT_PATH="$(worktree_path "$TEAM_ID")"
WT_BRANCH="$(worktree_branch "$TEAM_ID")"
FRESH="false"

# ============ Phase 1：TTL 清理 ============
log "preflight: TTL 端口清理"
bash "$SCRIPT_DIR/port-cleanup.sh" --quiet

# ============ Phase 2：worktree ============
log "preflight: 创建/复用 worktree @ $WT_PATH"
WT_PATH_OUT="$(bash "$SCRIPT_DIR/worktree-create.sh" "$TEAM_ID" "$BASE_COMMIT")"
WT_PATH="$WT_PATH_OUT"

# ============ Phase 3：端口分配 ============
log "preflight: 端口分配"
PORTS_JSON="$(bash "$SCRIPT_DIR/port-claim.sh" "$TEAM_ID")"
BACKEND_PORT="$(echo "$PORTS_JSON" | "$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['backend'])")"
FRONTEND_PORT="$(echo "$PORTS_JSON" | "$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['frontend'])")"

# ============ Phase 4：team dir + state/log 初始化 ============
mkdir -p "$TEAM_DIR_PATH/test-reports" "$TEAM_DIR_PATH/bug-tickets" "$TEAM_DIR_PATH/ac-matrix"

if [ ! -f "$STATE_FILE" ]; then
  FRESH="true"
  BASE_COMMIT_RESOLVED="${BASE_COMMIT:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
  "$PYTHON_BIN" -c "
import json, time
state = {
    'version': 3,
    'team_id': '$TEAM_ID',
    'mode': 'B',
    'batch_size': 1,
    'started_at': time.strftime('%y%m%d %H%M'),
    'updated_at': time.strftime('%y%m%d %H%M'),
    'paused_at': None,
    'worktree': {
        'path': '$WT_PATH',
        'branch': '$WT_BRANCH',
        'base_commit': '$BASE_COMMIT_RESOLVED',
        'created_at': time.strftime('%y%m%d %H%M'),
    },
    'ports': {
        'backend': $BACKEND_PORT,
        'frontend': $FRONTEND_PORT,
        'claimed_at': int(time.time()),
        'ttl_seconds': $PORT_TTL_SECONDS,
    },
    'ship_ready_smokes': [],
    'pool': [],
    'in_flight': [],
    'history': [],
    'terminal_status': None,
}
with open('$STATE_FILE', 'w', encoding='utf-8') as fp:
    json.dump(state, fp, ensure_ascii=False, indent=2)
"
  log "state.json 初始化完成：$STATE_FILE"
fi

# ============ main-log.md（首次创建骨架）============
if [ ! -f "$LOG_FILE" ]; then
  cat > "$LOG_FILE" <<EOF
# TEAM-$TEAM_ID main-log

> 工作目录：$WT_PATH
> 分支：$WT_BRANCH
> 后端端口：$BACKEND_PORT / 前端端口：$FRONTEND_PORT
> 创建时间：$(date '+%y%m%d %H%M')

---

EOF
fi

# ============ team-registry.json 更新（仅首次）============
#   幂等原则：preflight 不修改现有 team entry（避免 updated_at 漂移）
#   仅在 fresh=true（新建 state.json）时写一次
if [ "$FRESH" = "true" ]; then
  "$PYTHON_BIN" -c "
import json, time, os
path = '$REGISTRY_FILE'
if os.path.exists(path) and os.path.getsize(path) > 0:
    with open(path, 'r', encoding='utf-8') as fp:
        reg = json.load(fp)
else:
    reg = {'version': 1, 'teams': {}, 'updated_at': ''}
reg.setdefault('teams', {})
existing = reg['teams'].get('$TEAM_ID', {})
reg['teams']['$TEAM_ID'] = {
    **existing,
    'team_id': '$TEAM_ID',
    'worktree': '$WT_PATH',
    'branch': '$WT_BRANCH',
    'ports': {'backend': $BACKEND_PORT, 'frontend': $FRONTEND_PORT},
    'status': existing.get('status', 'active'),
    'created_at': existing.get('created_at', time.strftime('%y%m%d %H%M')),
    'updated_at': time.strftime('%y%m%d %H%M'),
}
reg['updated_at'] = time.strftime('%y%m%d %H%M')
with open(path, 'w', encoding='utf-8') as fp:
    json.dump(reg, fp, ensure_ascii=False, indent=2)
"
fi

# ============ 输出 ============
"$PYTHON_BIN" -c "
import json
print(json.dumps({
    'team_id': '$TEAM_ID',
    'worktree_path': '$WT_PATH',
    'branch': '$WT_BRANCH',
    'backend': $BACKEND_PORT,
    'frontend': $FRONTEND_PORT,
    'fresh': '$FRESH',
    'state_file': '$STATE_FILE',
}, ensure_ascii=False))
"

log "[TEAM=$TEAM_ID] preflight OK (worktree=$WT_PATH, ports=$BACKEND_PORT/$FRONTEND_PORT)"