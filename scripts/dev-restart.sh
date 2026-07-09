#!/usr/bin/env bash
# dev-restart.sh — clean up the local dev stack (backend :8000 + frontend :5173)
# and re-launch it via scripts/dev-up.sh.
#
# 设计：
#   - L1 端口精准清理（netstat -ano 找 LISTENING PID → taskkill /T /F /PID）
#   - L2 命令行残留清理（tasklist /V 找 uvicorn / vite）
#   - L3 image-based 兜底（仅 --force 触发；默认 NO，避免误伤 LSP / pytest / 其他 node 工具）
#   - exec 进 dev-up.sh，不 fork（Ctrl-C 直传 trap）
#
# 退出码：
#   0 = 清理 + 启动成功 / dry-run 正常
#   1 = 通用错误（参数 / 环境）
#   2 = L1+L2 杀不干净，端口仍占用（用户需 --force）
#   3 = dev-up.sh 启动失败
#   4 = netstat / taskkill 不可用（环境降级失败）

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# ============ 常量 ============
BACKEND_PORT=8000
FRONTEND_PORT=5173
LOG_FILE="$ROOT/.claude/dev-restart.log"
SERVICES_JSON="$ROOT/.claude/teams/local/services.json"
LOCK_FILE="$ROOT/.claude/dev-restart.lock"
LIB_SH="$ROOT/.claude/skills/team-autonomous-loop/scripts/lib.sh"

# 复用 team-autonomous-loop 的 lib.sh
# shellcheck disable=SC1090
if [ -f "$LIB_SH" ]; then
  source "$LIB_SH"
else
  echo "[dev-restart] ERROR: lib.sh not found at $LIB_SH" >&2
  exit 1
fi

# ============ flag 默认值 ============
DRY_RUN=0
FORCE=0
ONLY_BACKEND=0
ONLY_FRONTEND=0

# ============ 输出样式 ============
c_red()    { printf -- '\033[0;31m%s\033[0m\n' "$*"; }
c_yellow() { printf -- '\033[0;33m%s\033[0m\n' "$*"; }
c_green()  { printf -- '\033[0;32m%s\033[0m\n' "$*"; }
c_cyan()   { printf -- '\033[0;36m%s\033[0m\n' "$*"; }

# ============ usage ============
usage() {
  cat <<'EOF'
用法: bash scripts/dev-restart.sh [选项]

选项:
  --dry-run            只打印要清理的 PID，不真杀；也不 exec dev-up.sh
  --force              L1+L2 失败时启用 image-based 强杀（taskkill /F /IM python.exe|node.exe）
                       默认 NO — 避免误伤 LSP / pytest / 其他无关进程
  --only-backend       仅清理 :8000 并启动 backend（frontend 不动）
  --only-frontend      仅清理 :5173 并启动 frontend（backend 不动）
  -h, --help           显示本帮助

退出码:
  0 成功    1 通用错误    2 端口仍占用（需 --force）
  3 dev-up.sh 失败    4 netstat/taskkill 不可用
EOF
}

# ============ parse_args ============
parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --dry-run)       DRY_RUN=1 ;;
      --force)         FORCE=1 ;;
      --only-backend)  ONLY_BACKEND=1 ;;
      --only-frontend) ONLY_FRONTEND=1 ;;
      -h|--help)       usage; exit 0 ;;
      *)               echo "[dev-restart] ERROR: unknown flag: $1" >&2; usage; exit 1 ;;
    esac
    shift
  done

  if [ "$ONLY_BACKEND" = "1" ] && [ "$ONLY_FRONTEND" = "1" ]; then
    echo "[dev-restart] ERROR: --only-backend and --only-frontend are mutually exclusive" >&2
    exit 1
  fi
}

# ============ detect_os ============
detect_os() {
  case "$(uname -s 2>/dev/null || echo Windows)" in
    MINGW*|MSYS*|CYGWIN*|Windows*) OS="windows" ;;
    Linux*)                         OS="linux" ;;
    Darwin*)                        OS="macos" ;;
    *)                              OS="unknown" ;;
  esac
  echo "[dev-restart] detected OS: $OS" >&2
}

# ============ preflight ============
preflight() {
  if ! command -v netstat >/dev/null 2>&1; then
    echo "[dev-restart] ERROR: netstat not found in PATH" >&2
    exit 4
  fi

  if [ "$OS" = "windows" ]; then
    if ! command -v taskkill >/dev/null 2>&1; then
      echo "[dev-restart] ERROR: taskkill not found (Windows expected)" >&2
      exit 4
    fi
    if ! command -v tasklist >/dev/null 2>&1; then
      echo "[dev-restart] ERROR: tasklist not found (Windows expected)" >&2
      exit 4
    fi
  else
    if ! command -v kill >/dev/null 2>&1; then
      echo "[dev-restart] ERROR: kill not found" >&2
      exit 4
    fi
  fi

  mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$SERVICES_JSON")"
}

# ============ pids_on_port（端口 → LISTENING PID 列表，去重） ============
# 用法: pids_on_port <port>
pids_on_port() {
  local port="$1"
  # 复用 team-svc.sh 同款正则：IPv4/IPv6 双栈都覆盖，sort -u 去重
  netstat -ano 2>/dev/null \
    | grep -E "[:.]${port}[[:space:]].*LISTENING" \
    | awk '{print $NF}' \
    | grep -E '^[0-9]+$' \
    | sort -u
}

# ============ kill_pid_tree（杀进程树；Windows 用 taskkill /T） ============
# 用法: kill_pid_tree <pid>
kill_pid_tree() {
  local pid="$1"
  if [ "$OS" = "windows" ]; then
    # //T = 整棵进程树；//F = 强制
    taskkill //T //F //PID "$pid" >/dev/null 2>&1 || true
  else
    # Unix: 先 TERM 一组（pgid），再 KILL
    local pgid
    pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
    if [ -n "$pgid" ] && [ "$pgid" != "0" ]; then
      kill -TERM "-$pgid" 2>/dev/null || true
      sleep 0.3
      kill -KILL "-$pgid" 2>/dev/null || true
    else
      kill -KILL "$pid" 2>/dev/null || true
    fi
  fi
}

# ============ alive_pid（PID 是否还活着） ============
# 用法: alive_pid <pid> → echo "yes"|"no"
alive_pid() {
  local pid="$1"
  if [ "$OS" = "windows" ]; then
    tasklist //FI "PID eq $pid" 2>/dev/null | grep -q "$pid" && echo "yes" || echo "no"
  else
    kill -0 "$pid" 2>/dev/null && echo "yes" || echo "no"
  fi
}

# ============ L1: clean_by_port ============
# 用法: clean_by_port <port> <label>  → echo 杀掉的 PID 数
clean_by_port() {
  local port="$1"
  local label="$2"
  local killed=0
  local pids
  pids="$(pids_on_port "$port" || true)"

  if [ -z "$pids" ]; then
    echo "[dev-restart] L1 $label (:$port): no LISTENING pid found" >&2
    echo 0
    return
  fi

  while IFS= read -r pid; do
    pid="${pid%$'\r'}"  # 剥 Windows CR（防御）
    [ -z "$pid" ] && continue
    if [ "$DRY_RUN" = "1" ]; then
      c_yellow "[dev-restart] L1 $label (:$port): DRY-RUN would kill pid=$pid" >&2
    else
      echo "[dev-restart] L1 $label (:$port): killing pid=$pid" >&2
      kill_pid_tree "$pid"
      killed=$((killed + 1))
    fi
  done <<< "$pids"

  # 仅返回数字到 stdout（提示都走 stderr）
  printf '%d\n' "$killed"
}

# ============ L2: clean_by_cmdline（按命令行匹配 uvicorn/vite 残留） ============
# 注意：仅对"端口已释放但进程仍在跑"的孤儿起作用；端口占着的 PID 已被 L1 处理
clean_by_cmdline() {
  local killed=0

  if [ "$OS" != "windows" ]; then
    # Unix 暂不实现 L2（项目主战场 Windows）
    printf '%d\n' 0
    return
  fi

  # 找 uvicorn + app.main（backend reloader/worker 残留）
  local be_pids
  be_pids="$(tasklist //V //FI "IMAGENAME eq python.exe" 2>/dev/null \
    | grep -E 'uvicorn|app\.main' \
    | awk '{print $2}' \
    | grep -E '^[0-9]+$' \
    | sort -u || true)"

  while IFS= read -r pid; do
    pid="${pid%$'\r'}"
    [ -z "$pid" ] && continue
    # 只杀 8000 端口关联（端口已释放才进 L2；双重过滤避免误伤其他 uvicorn 实例）
    local port_in_cmd
    port_in_cmd="$(tasklist //V //FI "PID eq $pid" 2>/dev/null | grep -E -- '--port[[:space:]]+8000' || true)"
    [ -z "$port_in_cmd" ] && continue

    if [ "$DRY_RUN" = "1" ]; then
      c_yellow "[dev-restart] L2 backend orphan: DRY-RUN would kill pid=$pid" >&2
    else
      echo "[dev-restart] L2 backend orphan: killing pid=$pid" >&2
      kill_pid_tree "$pid"
      killed=$((killed + 1))
    fi
  done <<< "$be_pids"

  # 找 vite（frontend 残留）
  local fe_pids
  fe_pids="$(tasklist //V //FI "IMAGENAME eq node.exe" 2>/dev/null \
    | grep -E 'vite' \
    | awk '{print $2}' \
    | grep -E '^[0-9]+$' \
    | sort -u || true)"

  while IFS= read -r pid; do
    pid="${pid%$'\r'}"
    [ -z "$pid" ] && continue
    if [ "$DRY_RUN" = "1" ]; then
      c_yellow "[dev-restart] L2 frontend orphan: DRY-RUN would kill pid=$pid" >&2
    else
      echo "[dev-restart] L2 frontend orphan: killing pid=$pid" >&2
      kill_pid_tree "$pid"
      killed=$((killed + 1))
    fi
  done <<< "$fe_pids"

  printf '%d\n' "$killed"
}

# ============ L3: image-based fallback（仅 --force 触发） ============
clean_by_image() {
  if [ "$DRY_RUN" = "1" ]; then
    c_yellow "[dev-restart] L3 image-based: DRY-RUN would taskkill /F /IM python.exe node.exe" >&2
    printf '%d\n' 0
    return
  fi

  c_yellow "[dev-restart] L3 FORCE: image-based kill (may affect other python/node processes)" >&2
  local killed=0

  # 仅杀 WINDOWTITLE 含 uvicorn / vite 的 python.exe，避免误伤 LSP
  taskkill //F //IM python.exe //FI "WINDOWTITLE eq *uvicorn*" >/dev/null 2>&1 && killed=$((killed + 1)) || true
  taskkill //F //IM uvicorn.exe >/dev/null 2>&1 && killed=$((killed + 1)) || true
  taskkill //F //IM node.exe //FI "WINDOWTITLE eq *vite*" >/dev/null 2>&1 && killed=$((killed + 1)) || true

  printf '%d\n' "$killed"
}

# ============ verify_port_released（端口释放确认） ============
verify_port_released() {
  local port="$1"
  local label="$2"
  local attempts=3
  local i
  for i in $(seq 1 $attempts); do
    if [ "$(is_port_in_use "$port")" = "no" ]; then
      echo "[dev-restart] verify $label (:$port): RELEASED" >&2
      return 0
    fi
    sleep 1
  done

  echo "[dev-restart] verify $label (:$port): STILL IN USE after $attempts s" >&2
  return 1
}

# ============ record_kill_log（写 .claude/dev-restart.log + services.json） ============
# 用法: record_kill_log <be_killed> <fe_killed> <be_pids_csv> <fe_pids_csv>
record_kill_log() {
  local be_killed="$1"
  local fe_killed="$2"
  local be_pids="$3"
  local fe_pids="$4"
  # 防御：若传入非数字（捕获 stdout 污染），强制归零
  be_killed="${be_killed//[!0-9]/}"
  fe_killed="${fe_killed//[!0-9]/}"
  [ -z "$be_killed" ] && be_killed=0
  [ -z "$fe_killed" ] && fe_killed=0
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  local mode
  mode="live"
  [ "$DRY_RUN" = "1" ] && mode="dry-run"

  # 人类可读日志（追加）
  printf '[%s] mode=%s killed backend=%d (%s) frontend=%d (%s) force=%d\n' \
    "$ts" "$mode" "$be_killed" "${be_pids:-none}" "$fe_killed" "${fe_pids:-none}" "$FORCE" \
    >> "$LOG_FILE"

  if [ "$DRY_RUN" = "1" ]; then
    return
  fi

  # 结构化 services.json（用 lib.sh 的 pyjson_update，写入时 with_lock）
  local now_iso
  now_iso="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  with_lock "$LOCK_FILE" pyjson_update "$SERVICES_JSON" "
import json
data.setdefault('version', 1)
data.setdefault('services', [])
data['services'].append({
    'name': 'dev-restart',
    'type': 'orchestrator',
    'killed_at': '$now_iso',
    'killed_by': 'dev-restart.sh',
    'mode': '$mode',
    'force': $FORCE,
    'pids': {
        'backend': [int(p) for p in '$be_pids'.split(',') if p.strip().isdigit()],
        'frontend': [int(p) for p in '$fe_pids'.split(',') if p.strip().isdigit()],
    },
    'log': '$LOG_FILE',
})
data['updated_at'] = '$now_iso'
"
}

# ============ main ============
main() {
  parse_args "$@"
  detect_os
  preflight

  c_cyan "[dev-restart] === InterCraft dev-restart ==="
  [ "$DRY_RUN" = "1" ] && c_yellow "[dev-restart] DRY-RUN mode: no processes will be killed"
  [ "$FORCE" = "1" ]   && c_yellow "[dev-restart] FORCE mode: image-based kill enabled on fallback"

  # 决定要清理的端口
  local ports_to_clean=()
  local labels=()
  if [ "$ONLY_FRONTEND" = "1" ]; then
    ports_to_clean=("$FRONTEND_PORT")
    labels=("frontend")
  elif [ "$ONLY_BACKEND" = "1" ]; then
    ports_to_clean=("$BACKEND_PORT")
    labels=("backend")
  else
    ports_to_clean=("$BACKEND_PORT" "$FRONTEND_PORT")
    labels=("backend" "frontend")
  fi

  # 先收集要杀的 PID（仅 L1 阶段，给日志用）
  local be_pids fe_pids
  be_pids="$(pids_on_port "$BACKEND_PORT" | tr '\n' ',' | sed 's/,$//')"
  fe_pids="$(pids_on_port "$FRONTEND_PORT" | tr '\n' ',' | sed 's/,$//')"

  # L1: 端口精准清理
  local total_be_killed=0
  local total_fe_killed=0
  for i in "${!ports_to_clean[@]}"; do
    local p="${ports_to_clean[$i]}"
    local lbl="${labels[$i]}"
    local n
    n="$(clean_by_port "$p" "$lbl")"
    if [ "$lbl" = "backend" ]; then
      total_be_killed="$n"
    else
      total_fe_killed="$n"
    fi
  done

  # L2: 命令行残留清理
  clean_by_cmdline >/dev/null

  # 验证端口释放
  local verify_ok=1
  if [ "$DRY_RUN" != "1" ]; then
    for i in "${!ports_to_clean[@]}"; do
      local p="${ports_to_clean[$i]}"
      local lbl="${labels[$i]}"
      if ! verify_port_released "$p" "$lbl"; then
        verify_ok=0
      fi
    done
  fi

  # L3 兜底
  if [ "$verify_ok" = "0" ] && [ "$DRY_RUN" != "1" ]; then
    if [ "$FORCE" = "1" ]; then
      c_yellow "[dev-restart] L1+L2 left ports in use; invoking FORCE image-based fallback"
      clean_by_image
      # 再验证一次
      verify_ok=1
      for i in "${!ports_to_clean[@]}"; do
        local p="${ports_to_clean[$i]}"
        local lbl="${labels[$i]}"
        if ! verify_port_released "$p" "$lbl"; then
          verify_ok=0
        fi
      done
    else
      c_red "[dev-restart] ERROR: ports still in use after L1+L2."
      c_red "  Re-run with --force to enable image-based fallback (may affect other processes)."
      record_kill_log "$total_be_killed" "$total_fe_killed" "$be_pids" "$fe_pids"
      exit 2
    fi
  fi

  if [ "$verify_ok" = "0" ]; then
    c_red "[dev-restart] ERROR: ports still occupied even after FORCE. Manual cleanup required."
    record_kill_log "$total_be_killed" "$total_fe_killed" "$be_pids" "$fe_pids"
    exit 2
  fi

  # 记录日志
  record_kill_log "$total_be_killed" "$total_fe_killed" "$be_pids" "$fe_pids"

  if [ "$DRY_RUN" = "1" ]; then
    c_green "[dev-restart] DRY-RUN done. No processes killed."
    exit 0
  fi

  # exec dev-up.sh（filter 本脚本私有 flag；透传其余参数）
  local launch_args=()
  for arg in "$@"; do
    case "$arg" in
      --dry-run|--force|--only-backend|--only-frontend|-h|--help) ;;
      *) launch_args+=("$arg") ;;
    esac
  done

  c_green "[dev-restart] cleanup done; launching dev-up.sh"
  exec bash "$ROOT/scripts/dev-up.sh" "${launch_args[@]}"
}

# dummy 占位已删除

main "$@"