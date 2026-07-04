#!/usr/bin/env bash
# port-release.sh — 释放 team 的端口
# 用法：port-release.sh <team-id>
# 副作用：
#   - 从 .claude/team-port-pool.json 标记 released_at
#   - 保留 .claude/teams/<id>/ports.json（审计）
# 幂等：可重复执行

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

TEAM_ID="${1:-}"
if [ -z "$TEAM_ID" ]; then
  die "usage: port-release.sh <team-id>"
fi

if [ ! -f "$PORT_POOL_FILE" ]; then
  log "port-pool 不存在，跳过"
  exit 0
fi

with_lock "$PORT_POOL_FILE.lock" "$PYTHON_BIN" -c "
import json, time
path = '$PORT_POOL_FILE'
with open(path, 'r', encoding='utf-8') as fp:
    pool = json.load(fp)
teams = pool.get('teams', {})
info = teams.get('$TEAM_ID')
if not info:
    pass  # 已释放，幂等
elif info.get('released_at'):
    pass  # 已标 released，幂等
else:
    info['released_at'] = int(time.time())
    pool['updated_at'] = time.strftime('%y%m%d %H%M')
with open(path, 'w', encoding='utf-8') as fp:
    json.dump(pool, fp, ensure_ascii=False, indent=2)
print('released')
"

log "端口已释放（标记 released_at）：team=$TEAM_ID"