#!/usr/bin/env bash
# port-cleanup.sh — TTL 超时端口自动回收
# 用法：port-cleanup.sh [--quiet]
# 副作用：扫描 .claude/team-port-pool.json，
#        将 claimed_at + ttl < now() 的条目标记 released_at
# 幂等：可重复执行
#
# 该脚本：
#   - 在 preflight.sh 启动时自动调用
#   - 用户也可以手动调用清理陈旧条目
#   - 不删除端口历史，仅标记释放时间（审计）

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

QUIET="false"
for arg in "$@"; do
  case "$arg" in
    --quiet|-q) QUIET="true" ;;
    *) err "unknown arg: $arg"; exit 1 ;;
  esac
done

if [ ! -f "$PORT_POOL_FILE" ]; then
  [ "$QUIET" = "true" ] || log "port-pool 不存在，跳过"
  exit 0
fi

COUNT="$(with_lock "$PORT_POOL_FILE.lock" "$PYTHON_BIN" -c "
import json, time, sys
path = '$PORT_POOL_FILE'
with open(path, 'r', encoding='utf-8') as fp:
    pool = json.load(fp)
teams = pool.get('teams', {})
now = int(time.time())
ttl = $PORT_TTL_SECONDS
recycled = 0
for tid, info in teams.items():
    if info.get('released_at'):
        continue
    ts = info.get('claimed_at', 0)
    if now - ts > ttl:
        info['released_at'] = now
        info['recycled_reason'] = 'ttl_expired'
        recycled += 1
if recycled > 0:
    pool['updated_at'] = time.strftime('%y%m%d %H%M')
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(pool, fp, ensure_ascii=False, indent=2)
print(recycled)
")"

[ "$QUIET" = "true" ] || log "TTL 回收：$COUNT 个端口"
exit 0