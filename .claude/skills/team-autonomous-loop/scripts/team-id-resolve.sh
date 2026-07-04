#!/usr/bin/env bash
# team-id-resolve.sh — 解析或生成 team-id
# 用法：
#   team-id-resolve.sh --team=<id>          # 显式指定
#   team-id-resolve.sh --latest-active       # 取最近 active team
#   team-id-resolve.sh                       # 自动生成
#
# 输出：resolved team-id (stdout)
# 退出码：
#   0 = 成功
#   1 = 无效 id 或冲突
#   2 = registry 损坏

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_repo
check_layout

EXPLICIT_ID=""
MODE="auto"  # auto | latest

for arg in "$@"; do
  case "$arg" in
    --team=*)    EXPLICIT_ID="${arg#--team=}" ;;
    --latest-active) MODE="latest" ;;
    --help|-h)
      sed -n '2,12p' "$0" | sed 's/^# //'
      exit 0 ;;
    *) err "unknown arg: $arg"; exit 1 ;;
  esac
done

# ============ 路径 1：显式 id ============
if [ -n "$EXPLICIT_ID" ]; then
  if [ "$(is_valid_team_id "$EXPLICIT_ID")" != "yes" ]; then
    die "invalid team id: '$EXPLICIT_ID' (允许 [a-z0-9-]，长度 3-32)"
  fi
  echo "$EXPLICIT_ID"
  exit 0
fi

# ============ 路径 2：latest active ============
if [ "$MODE" = "latest" ]; then
  if [ ! -f "$REGISTRY_FILE" ]; then
    die "registry 不存在：$REGISTRY_FILE"
  fi
  "$PYTHON_BIN" -c "
import json, sys
with open('$REGISTRY_FILE', 'r', encoding='utf-8') as fp:
    reg = json.load(fp)
teams = reg.get('teams', {})
candidates = []
for tid, t in teams.items():
    status = t.get('status', '')
    if status not in ('done', 'cleaned', 'merged'):
        candidates.append((t.get('updated_at', ''), tid))
if not candidates:
    sys.exit(1)
candidates.sort(reverse=True)
print(candidates[0][1])
" || die "no active team found"
  exit 0
fi

# ============ 路径 3：自动生成（防碰撞）============
gen_team_id() {
  local yymmdd
  yymmdd="$(now_yymmdd)"
  local attempt=0
  while [ "$attempt" -lt 5 ]; do
    # 用 $RANDOM + yymmdd 做 hash，再截取
    local hash
    hash="$(printf '%s%s' "$yymmdd" "$RANDOM" | "$PYTHON_BIN" -c "
import sys, hashlib
s = sys.stdin.read()
print(hashlib.sha1(s.encode()).hexdigest()[:6])
")"
    local candidate="team-${yymmdd}-${hash}"
    # 查重
    if [ ! -d "$TEAMS_DIR/$candidate" ]; then
      echo "$candidate"
      return 0
    fi
    attempt=$((attempt + 1))
  done
  die "无法生成唯一 team-id（5 次尝试后仍冲突）"
}

gen_team_id