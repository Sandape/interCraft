#!/usr/bin/env bash
# status.sh — 列出 team 状态
# 用法：
#   status.sh                       # 默认：最近活跃 team
#   status.sh <team-id>             # 指定 team
#   status.sh --all                 # 全部 teams
#   status.sh --json                # JSON 输出
# 输出：表格 / JSON

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_repo

MODE="default"
TEAM_ID=""
JSON_OUT="false"
for arg in "$@"; do
  case "$arg" in
    --all)       MODE="all" ;;
    --json)      JSON_OUT="true" ;;
    --help|-h)
      sed -n '2,12p' "$0" | sed 's/^# //'
      exit 0 ;;
    *) TEAM_ID="$arg" ;;
  esac
done

# registry 不存在
if [ ! -f "$REGISTRY_FILE" ]; then
  if [ "$JSON_OUT" = "true" ]; then
    echo '{"teams":[]}'
  else
    echo "no teams yet (registry missing: $REGISTRY_FILE)"
  fi
  exit 0
fi

# 解析 mode
case "$MODE" in
  default)
    if [ -n "$TEAM_ID" ]; then
      :  # 指定 team
    else
      # 取最近 updated 的 active team
      TEAM_ID="$(bash "$SCRIPT_DIR/team-id-resolve.sh" --latest-active 2>/dev/null || echo "")"
      if [ -z "$TEAM_ID" ]; then
        if [ "$JSON_OUT" = "true" ]; then
          echo '{"teams":[],"note":"no active team"}'
        else
          echo "no active team"
        fi
        exit 0
      fi
    fi
    ;;
  all) ;;
esac

# 读 registry 并格式化
if [ "$JSON_OUT" = "true" ]; then
  "$PYTHON_BIN" -c "
import json, sys
with open('$REGISTRY_FILE', 'r', encoding='utf-8') as fp:
    reg = json.load(fp)
teams = reg.get('teams', {})
if '$MODE' == 'default':
    tid = '$TEAM_ID'
    if tid in teams:
        print(json.dumps({'teams': [teams[tid]]}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({'teams': [], 'note': f'team {tid!r} not found'}, ensure_ascii=False, indent=2))
else:
    rows = []
    for tid in sorted(teams.keys()):
        rows.append(teams[tid])
    print(json.dumps({'teams': rows}, ensure_ascii=False, indent=2))
"
else
  # 表格输出
  "$PYTHON_BIN" -c "
import json, os, sys
with open('$REGISTRY_FILE', 'r', encoding='utf-8') as fp:
    reg = json.load(fp)
teams = reg.get('teams', {})
if '$MODE' == 'default':
    tid = '$TEAM_ID'
    if tid not in teams:
        print(f'team {tid!r} not found')
        sys.exit(1)
    rows = [(tid, teams[tid])]
else:
    rows = sorted(teams.items())

print(f'{\"team\":<14} {\"worktree\":<24} {\"branch\":<24} {\"ports\":<12} {\"status\":<14} {\"updated\"}')
print('-' * 110)
for tid, t in rows:
    wt = t.get('worktree', '?')
    wt_short = wt.replace('$REPO_ROOT/', '').replace('$REPO_ROOT\\\\\\\\', '')
    if len(wt_short) > 22:
        wt_short = '...' + wt_short[-19:]
    br = t.get('branch', '?')
    p = t.get('ports', {})
    ports = f\"{p.get('backend', '?')}/{p.get('frontend', '?')}\"
    st = t.get('status', '?')
    up = t.get('updated_at', '?')
    print(f'{tid:<14} {wt_short:<24} {br:<24} {ports:<12} {st:<14} {up}')
"
fi