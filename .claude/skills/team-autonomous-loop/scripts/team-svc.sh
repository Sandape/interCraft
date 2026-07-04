#!/usr/bin/env bash
# team-svc.sh — team 服务生命周期包装器（v3.1 强约束）
# 用法：
#   team-svc.sh start <team-id> <type> -- <cmd...>   # 启动并跟踪
#   team-svc.sh stop  <team-id> [name]               # 停一个或全部
#   team-svc.sh status <team-id>                     # 列出 tracked services
#   team-svc.sh list                                  # 列出所有 team 的服务
#   team-svc.sh kill-port <port>                     # 强制 kill 占用某端口的进程
#
# 跟踪文件：.claude/teams/<team-id>/services.json
# 设计：
#   - start：fork 出 cmd，记录 pid + ppid 到 services.json
#   - stop：先 taskkill /T /F 杀进程树，再从 services.json 移除
#   - 双重保险：cleanup.sh 末尾会按端口兜底再扫一次
#
# 平台支持：
#   - Windows (Git Bash)：taskkill /T /F /PID + netstat -ano
#   - Linux/macOS：kill -TERM -<pgid> / kill -9 -- -<pgid> + lsof -i :PORT

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

check_layout

cmd="${1:-}"
shift || true

# ============ helpers ============

# 平台检测
detect_os() {
  case "$(uname -s 2>/dev/null || echo Windows)" in
    Linux|Darwin) echo "unix" ;;
    *) echo "windows" ;;
  esac
}
OS="$(detect_os)"

# 强杀 PID（含子进程）
# 用法：force_kill_pid <pid>
force_kill_pid() {
  local pid="$1"
  [ -z "$pid" ] && return 0
  # 防御：pid 必须是数字
  if ! echo "$pid" | grep -qE '^[0-9]+$'; then
    log "skip non-numeric pid: $pid"
    return 0
  fi
  if [ "$OS" = "windows" ]; then
    taskkill //T //F //PID "$pid" 2>&1 | sed 's/^/[taskkill] /' || true
  else
    # 先 SIGTERM 进程组（如果是 job control），失败再 SIGKILL
    kill -TERM -- "-$pid" 2>/dev/null || true
    sleep 0.5
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  fi
}

# 找占用某 TCP 端口的 PID（可能多个）
# 用法：pids_on_port <port> → 输出多行 PID
pids_on_port() {
  local port="$1"
  if [ "$OS" = "windows" ]; then
    netstat -ano 2>/dev/null \
      | grep -E "[:.]${port}[[:space:]].*LISTENING" \
      | awk '{print $NF}' \
      | sort -u
  else
    # 优先 lsof
    if command -v lsof >/dev/null 2>&1; then
      lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null || true
    else
      # 兜底：fuser
      fuser "${port}/tcp" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' || true
    fi
  fi
}

# 验证 PID 是否仍在跑
is_pid_alive() {
  local pid="$1"
  [ -z "$pid" ] && return 1
  if ! echo "$pid" | grep -qE '^[0-9]+$'; then return 1; fi
  if [ "$OS" = "windows" ]; then
    tasklist //FI "PID eq $pid" 2>/dev/null | grep -q "$pid"
  else
    kill -0 "$pid" 2>/dev/null
  fi
}

# ============ subcommands ============

# --- start ---
cmd_start() {
  local team_id="${1:-}"
  local svc_type="${2:-}"
  shift 2 || true
  [ -z "$team_id" ] && die "usage: team-svc.sh start <team-id> <type> -- <cmd...>"
  [ -z "$svc_type" ] && die "missing service type (backend|frontend|other)"
  [ "$(is_valid_team_id "$team_id")" != "yes" ] && die "invalid team-id: $team_id"

  # 找 -- 分隔符
  local sep_found=0
  local args=()
  for arg in "$@"; do
    if [ "$arg" = "--" ]; then
      sep_found=1
      continue
    fi
    if [ "$sep_found" = "1" ]; then
      args+=("$arg")
    fi
  done
  [ "$sep_found" = "1" ] || die "missing -- separator before command"
  [ "${#args[@]}" -gt 0 ] || die "empty command after --"

  local team_dir
  team_dir="$(team_dir "$team_id")"
  [ -d "$team_dir" ] || die "team dir 不存在：$team_dir（先跑 preflight.sh）"
  local svc_file="$team_dir/services.json"

  # 生成服务名（自增 name 字段）
  local name
  name="$("$PYTHON_BIN" -c "
import json, os, sys
p = sys.argv[1]
if os.path.exists(p):
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {'version': 1, 'services': []}
n = 1
existing = {s.get('name','') for s in data.get('services', [])}
while f'{sys.argv[2]}-{n}' in existing:
    n += 1
print(f'{sys.argv[2]}-{n}')
" "$svc_file" "$svc_type")"

  local log_file="$team_dir/${name}.log"

  # 用 python 的 subprocess.Popen 启动（跨平台一致，避免 bash wrapper PID 失效）
  # Python Popen 直接拿到真正的子进程 PID
  local cmd_json
  cmd_json="$("$PYTHON_BIN" -c "
import subprocess, json, sys, os
cmd = sys.argv[1:]
log_file = sys.argv[-2]  # 第二个-to-last
# 实际上：把 args 全传进来
" "$@")"

  # 简化做法：直接调 python subprocess
  local spawn_pid
  spawn_pid="$("$PYTHON_BIN" -c "
import subprocess, sys, os
args = sys.argv[1:]
log_file = args[-1]
args = args[:-1]
# DETACHED_PROCESS on Windows: 脱离父进程组
if sys.platform == 'win32':
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    p = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=open(log_file, 'ab'),
        stderr=subprocess.STDOUT,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
else:
    p = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=open(log_file, 'ab'),
        stderr=subprocess.STDOUT,
        start_new_session=True,  # setsid
        close_fds=True,
    )
print(p.pid)
" "${args[@]}" "$log_file")"

  # spawn_pid 可能是空字符串或非数字
  if ! echo "$spawn_pid" | grep -qE '^[0-9]+$'; then
    die "failed to spawn service (got spawn_pid=$spawn_pid)"
  fi
  local pid="$spawn_pid"

  # 记录到 services.json
  "$PYTHON_BIN" -c "
import json, os, sys, time
p = sys.argv[1]
if os.path.exists(p):
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {'version': 1, 'services': []}
service_entry = {
    'name': sys.argv[2],
    'type': sys.argv[3],
    'pid': int(sys.argv[4]),
    'cmd': sys.argv[5],
    'log': sys.argv[6],
    'started_at': int(time.time()),
    'status': 'running',
}
data.setdefault('services', []).append(service_entry)
with open(p, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'tracked: {sys.argv[2]} pid={sys.argv[4]} log={sys.argv[6]}')
" "$svc_file" "$name" "$svc_type" "$pid" "${args[*]}" "$log_file"

  # 给调用方一个简短的 JSON（方便 agent 解析）
  cat <<EOF
{
  "team_id": "$team_id",
  "name": "$name",
  "type": "$svc_type",
  "pid": $pid,
  "log": "$log_file"
}
EOF
}

# --- stop ---
cmd_stop() {
  local team_id="${1:-}"
  local name_filter="${2:-}"
  shift 2 2>/dev/null || shift 1 2>/dev/null || true

  [ -z "$team_id" ] && die "usage: team-svc.sh stop <team-id> [name]"
  [ "$(is_valid_team_id "$team_id")" != "yes" ] && die "invalid team-id: $team_id"

  local svc_file
  svc_file="$(team_dir "$team_id")/services.json"
  [ -f "$svc_file" ] || { log "no services.json for team=$team_id（nothing to stop）"; exit 0; }

  # 读取 + kill + 写回
  "$PYTHON_BIN" -c "
import json, os, sys, subprocess, time
p = sys.argv[1]
name_filter = (sys.argv[2] if len(sys.argv) > 2 else '')
with open(p, 'r', encoding='utf-8') as f:
    data = json.load(f)
killed = []
remaining = []
for s in data.get('services', []):
    if name_filter and s.get('name') != name_filter:
        remaining.append(s); continue
    # 优先杀 children（真实 PID），回落到 pid
    targets = list(s.get('children', []))
    if s.get('pid') is not None:
        try:
            targets.append(int(s.get('pid')))
        except (TypeError, ValueError):
            pass
    seen = set()
    targets = [t for t in targets if not (t in seen or seen.add(t))]
    for t in targets:
        try:
            ti = int(t)
        except (TypeError, ValueError):
            continue
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(ti)],
                           capture_output=True, text=True)
        else:
            try:
                os.killpg(ti, 15)
            except (ProcessLookupError, PermissionError):
                pass
            time.sleep(0.2)
            try:
                os.killpg(ti, 9)
            except (ProcessLookupError, PermissionError):
                try:
                    os.kill(ti, 9)
                except (ProcessLookupError, PermissionError):
                    pass
    killed.append({
        'name': s.get('name'),
        'pid': s.get('pid'),
        'children': list(s.get('children', [])),
        'targets_killed': len(targets),
    })
data['services'] = remaining
with open(p, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(json.dumps({'killed': killed, 'remaining': len(remaining)}, ensure_ascii=False))
" "$svc_file" "$name_filter"
}

# --- status ---
cmd_status() {
  local team_id="${1:-}"
  [ -z "$team_id" ] && die "usage: team-svc.sh status <team-id>"
  local svc_file
  svc_file="$(team_dir "$team_id")/services.json"
  if [ ! -f "$svc_file" ]; then
    echo "[]"
    return 0
  fi
  # 用 python 检查每个 PID 是否还活着
  "$PYTHON_BIN" -c "
import json, os, sys, subprocess
p = sys.argv[1]
with open(p, 'r', encoding='utf-8') as f:
    data = json.load(f)
out = []
for s in data.get('services', []):
    pid = s.get('pid')
    alive = False
    try:
        pid_i = int(pid)
        if sys.platform == 'win32':
            r = subprocess.run(['tasklist', '/FI', f'PID eq {pid_i}'],
                               capture_output=True, text=True)
            alive = str(pid_i) in r.stdout
        else:
            try:
                os.kill(pid_i, 0); alive = True
            except ProcessLookupError:
                alive = False
    except (TypeError, ValueError):
        alive = False
    out.append({**s, 'alive': alive})
print(json.dumps(out, ensure_ascii=False, indent=2))
" "$svc_file"
}

# --- list ---
cmd_list() {
  "$PYTHON_BIN" -c "
import json, os
td = '$TEAMS_DIR'
rows = []
if os.path.isdir(td):
    for entry in sorted(os.listdir(td)):
        sf = os.path.join(td, entry, 'services.json')
        if not os.path.exists(sf): continue
        try:
            with open(sf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for s in data.get('services', []):
                rows.append({'team': entry, **s})
        except Exception as e:
            rows.append({'team': entry, 'error': str(e)})
print(json.dumps(rows, ensure_ascii=False, indent=2))
"
}

# --- kill-port (Layer 2 兜底) ---
cmd_kill_port() {
  local port="${1:-}"
  [ -z "$port" ] && die "usage: team-svc.sh kill-port <port>"
  if ! echo "$port" | grep -qE '^[0-9]+$'; then
    die "invalid port: $port"
  fi
  local pids
  pids="$(pids_on_port "$port")"
  if [ -z "$pids" ]; then
    log "port $port 没有 LISTENING 进程"
    exit 0
  fi
  log "port $port 被以下 PID 占用：$(echo "$pids" | tr '\n' ' ')"
  for p in $pids; do
    log "  强杀 PID=$p"
    force_kill_pid "$p"
  done
  # 二次验证
  sleep 0.5
  local pids2
  pids2="$(pids_on_port "$port")"
  if [ -n "$pids2" ]; then
    log "WARN: port $port 仍被占用：$(echo "$pids2" | tr '\n' ' ')"
    exit 1
  fi
  log "port $port 已释放"
}

# ============ dispatch ============
case "$cmd" in
  start)  cmd_start "$@" ;;
  stop)   cmd_stop "$@" ;;
  status) cmd_status "$@" ;;
  list)   cmd_list ;;
  kill-port) cmd_kill_port "$@" ;;
  *)
    cat <<EOF
team-svc.sh — team 服务生命周期包装器

用法：
  team-svc.sh start <team-id> <type> -- <cmd...>   启动并跟踪
  team-svc.sh stop  <team-id> [name]               停一个或全部
  team-svc.sh status <team-id>                     列出 tracked services
  team-svc.sh list                                  列出所有 team 的服务
  team-svc.sh kill-port <port>                     强杀占用某端口的进程（Layer 2 兜底）

type: backend | frontend | other
EOF
    exit 1 ;;
esac