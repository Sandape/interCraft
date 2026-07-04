#!/usr/bin/env bash
# team-autonomous-loop v3.0 — common library for scripts/*.sh
# Source this from each script: source "$(dirname "$0")/lib.sh"
#
# 设计原则：
#   - 无 jq 依赖（Windows bash 环境） → JSON 操作走 python
#   - 幂等：每个 helper 都可重复调用
#   - 错误即终止：set -euo pipefail

# ============ 常量 ============
# scripts/ 在 .claude/skills/team-autonomous-loop/scripts/ → 上溯 4 级 = REPO_ROOT
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd 2>/dev/null || true)"
# 兜底：检查是否进错了一级（被 source 时 $0 相对路径变了）
if [ -z "$REPO_ROOT" ] || [ ! -d "$REPO_ROOT/.claude" ]; then
  # 尝试 git 推断
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi
if [ -z "$REPO_ROOT" ] || [ ! -d "$REPO_ROOT/.claude" ]; then
  REPO_ROOT="$(pwd)"
fi

CLAUDE_DIR="$REPO_ROOT/.claude"
TEAMS_DIR="$CLAUDE_DIR/teams"
WORKTREES_DIR="$REPO_ROOT/.worktrees"
REGISTRY_FILE="$CLAUDE_DIR/team-registry.json"
PORT_POOL_FILE="$CLAUDE_DIR/team-port-pool.json"
LESSONS_SHARED_FILE="$CLAUDE_DIR/lessons-shared.json"

# 端口池边界
BACKEND_PORT_MIN=8201
BACKEND_PORT_MAX=8299
FRONTEND_PORT_MIN=5301
FRONTEND_PORT_MAX=5399
PORT_TTL_SECONDS=86400  # 24h

PYTHON_BIN="${PYTHON_BIN:-python}"

# ============ Logging ============
log() { echo "[$(date '+%H:%M:%S')] [team-lib] $*" >&2; }
err() { echo "[$(date '+%H:%M:%S')] [team-lib] ERROR: $*" >&2; }
die() { err "$@"; exit 1; }

# ============ JSON helpers (via python) ============
# pyjson_read <file> — read JSON file, output to stdout; missing file → empty object
pyjson_read() {
  local f="$1"
  if [ ! -f "$f" ]; then
    echo "{}"
    return 0
  fi
  "$PYTHON_BIN" -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1])), ensure_ascii=False))" "$f"
}

# pyjson_write <file> <json-string> — atomic write (write to tmp + rename)
pyjson_write() {
  local f="$1"
  local content="$2"
  local dir
  dir="$(dirname "$f")"
  mkdir -p "$dir"
  local tmp
  tmp="$(mktemp "$dir/.json.XXXXXX")"
  echo "$content" > "$tmp"
  # Use python for atomic rename (cross-platform)
  "$PYTHON_BIN" -c "import os,sys; os.replace(sys.argv[1], sys.argv[2])" "$tmp" "$f"
}

# pyjson_update <file> <python-expr> — load file, mutate via python, save
# 使用：pyjson_update "$f" "data['x'] = 'y'; data['z'] = 1"
pyjson_update() {
  local f="$1"
  local expr="$2"
  if [ ! -f "$f" ] || [ ! -s "$f" ]; then
    echo "{}" > "$f"
  fi
  "$PYTHON_BIN" -c "
import json, sys, time
path = sys.argv[1]
expr = sys.argv[2]
with open(path, 'r', encoding='utf-8') as fp:
    data = json.load(fp)
$expr
with open(path, 'w', encoding='utf-8') as fp:
    json.dump(data, fp, ensure_ascii=False, indent=2)
" "$f" "$expr"
}

# ============ 路径工具 ============
team_dir() { echo "$TEAMS_DIR/$1"; }       # .claude/teams/<id>/
team_state() { echo "$TEAMS_DIR/$1/state.json"; }
team_log() { echo "$TEAMS_DIR/$1/main-log.md"; }
team_ports() { echo "$TEAMS_DIR/$1/ports.json"; }

worktree_path() { echo "$WORKTREES_DIR/$1"; }
worktree_branch() { echo "team/$1/master"; }

# ============ Team ID 校验 ============
# is_valid_team_id <id> → echo "yes"|"no"
is_valid_team_id() {
  local id="$1"
  if [ -z "$id" ]; then echo "no"; return; fi
  # 规则：仅允许 [a-z0-9-]，长度 3-32
  if echo "$id" | grep -qE '^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$'; then
    echo "yes"
  else
    echo "no"
  fi
}

# ============ 时间戳 ============
now_ts() { date +%s; }
now_yymmdd() { date '+%y%m%d'; }

# ============ 端口工具 ============
# is_port_in_use <port> — TCP probe (best-effort on Git Bash)
is_port_in_use() {
  local port="$1"
  # 优先用 netstat（Windows bash 自带）
  if netstat -an 2>/dev/null | grep -qE "[:.]${port}[[:space:]].*LISTENING"; then
    echo "yes"; return
  fi
  # 兜底：尝试 /dev/tcp
  if (echo >/dev/tcp/127.0.0.1/$port) 2>/dev/null; then
    echo "yes"; return
  fi
  echo "no"
}

# ============ 初始化检查 ============
ensure_repo() {
  if [ ! -d "$REPO_ROOT/.git" ] && [ ! -f "$REPO_ROOT/.git" ]; then
    die "REPO_ROOT=$REPO_ROOT 不是 git 仓库"
  fi
}

# ============ atomic lock (no flock) ============
# 用 mkdir 实现 advisory lock（不强制，适合单机多进程）
# 用法：with_lock "/tmp/foo.lock" "command..."
# 注意：会临时设置 EXIT trap 释放锁，调用前若有 trap 会保存并在返回时恢复
with_lock() {
  local lockfile="$1"
  shift
  local dir
  dir="$(dirname "$lockfile")"
  mkdir -p "$dir"
  # 最多尝试 30 次（每次 sleep 1s）
  local i=0
  while ! mkdir "$lockfile.lock" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
      die "acquire lock timeout: $lockfile"
    fi
    sleep 1
  done
  # 保存先前 trap（如果有），执行后恢复 —— 防止 with_lock 覆盖调用方的 EXIT trap
  local prev_trap
  prev_trap="$(trap -p EXIT | sed -e "s/^trap -- '//" -e "s/'$//")"
  trap "rmdir '$lockfile.lock' 2>/dev/null || true; $prev_trap" EXIT
  "$@"
  local rc=$?
  rmdir "$lockfile.lock" 2>/dev/null || true
  # 恢复调用方之前的 trap（如果有）
  if [ -n "$prev_trap" ]; then
    trap "$prev_trap" EXIT
  fi
  return $rc
}

# ============ registry helpers ============
registry_upsert_team() {
  local id="$1"
  local json_str="$2"
  pyjson_update "$REGISTRY_FILE" "
teams = data.setdefault('teams', {})
import json
new_team = json.loads('''$json_str''')
teams['$id'] = new_team
data['updated_at'] = '$(date '+%y%m%d %H%M')'
"
}

registry_remove_team() {
  local id="$1"
  pyjson_update "$REGISTRY_FILE" "
teams = data.get('teams', {})
teams.pop('$id', None)
data['updated_at'] = '$(date '+%y%m%d %H%M')'
"
}

# ============ 校验：所有路径依赖存在 ============
check_layout() {
  for d in "$CLAUDE_DIR" "$TEAMS_DIR" "$WORKTREES_DIR"; do
    mkdir -p "$d"
  done
}