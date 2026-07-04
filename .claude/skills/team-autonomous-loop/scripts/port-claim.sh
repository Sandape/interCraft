#!/usr/bin/env bash
# port-claim.sh — 为 team 预留 backend + frontend 端口
# 用法：port-claim.sh <team-id>
# 副作用：
#   - 写入 .claude/team-port-pool.json
#   - 写入 .claude/teams/<id>/ports.json
# 输出：JSON {backend, frontend, claimed_at, ttl_seconds}

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./lib.sh
source "$SCRIPT_DIR/lib.sh"

ensure_repo

TEAM_ID="${1:-}"
if [ -z "$TEAM_ID" ]; then
  die "usage: port-claim.sh <team-id>"
fi
if [ "$(is_valid_team_id "$TEAM_ID")" != "yes" ]; then
  die "invalid team-id: $TEAM_ID"
fi

# 先跑 TTL cleanup
bash "$SCRIPT_DIR/port-cleanup.sh" --quiet || true

PORTS_FILE="$(team_ports "$TEAM_ID")"

# 幂等：如果已分配且未过期，直接复用
if [ -f "$PORTS_FILE" ]; then
  CURRENT="$("$PYTHON_BIN" -c "
import json, sys, time
with open('$PORTS_FILE', 'r', encoding='utf-8') as fp:
    p = json.load(fp)
ts = p.get('claimed_at', 0)
ttl = p.get('ttl_seconds', $PORT_TTL_SECONDS)
if time.time() - ts < ttl and p.get('backend') and p.get('frontend'):
    print(json.dumps(p, ensure_ascii=False))
" 2>/dev/null || true)"
  if [ -n "$CURRENT" ]; then
    echo "$CURRENT"
    log "复用已分配端口：$(echo "$CURRENT" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(d['backend'], d['frontend'])")"
    exit 0
  fi
fi

# 写入 python 脚本到临时文件（避免嵌套 quoting 问题）
PY_SCRIPT="$(mktemp "$CLAUDE_DIR/.port-claim.XXXXXX.py")"
# 注：不用 EXIT trap —— with_lock 会覆盖 trap，改在脚本末尾显式清理

cat > "$PY_SCRIPT" <<EOF
import json, os, sys, time

POOL_FILE = "$PORT_POOL_FILE"
TEAM_ID = "$TEAM_ID"
BACKEND_MIN = $BACKEND_PORT_MIN
BACKEND_MAX = $BACKEND_PORT_MAX
FRONTEND_MIN = $FRONTEND_PORT_MIN
FRONTEND_MAX = $FRONTEND_PORT_MAX
TTL = $PORT_TTL_SECONDS

if os.path.exists(POOL_FILE):
    with open(POOL_FILE, 'r', encoding='utf-8') as fp:
        pool = json.load(fp)
else:
    pool = {'version': 1, 'teams': {}}
teams = pool.get('teams', {})

claimed_b = set()
claimed_f = set()
for tid, info in teams.items():
    if info.get('released_at'):
        continue
    ts = info.get('claimed_at', 0)
    if time.time() - ts > info.get('ttl_seconds', TTL):
        continue
    if 'backend' in info:
        claimed_b.add(info['backend'])
    if 'frontend' in info:
        claimed_f.add(info['frontend'])

def find_free(claimed, lo, hi):
    for p in range(lo, hi + 1):
        if p not in claimed:
            return p
    return None

b = find_free(claimed_b, BACKEND_MIN, BACKEND_MAX)
f = find_free(claimed_f, FRONTEND_MIN, FRONTEND_MAX)
if b is None or f is None:
    sys.stderr.write("POOL_EXHAUSTED")
    sys.exit(2)

info = {
    'backend': b,
    'frontend': f,
    'claimed_at': int(time.time()),
    'ttl_seconds': TTL,
}
teams[TEAM_ID] = info
pool['teams'] = teams
pool['updated_at'] = time.strftime('%y%m%d %H%M')

with open(POOL_FILE, 'w', encoding='utf-8') as fp:
    json.dump(pool, fp, ensure_ascii=False, indent=2)
print(json.dumps(info, ensure_ascii=False))
EOF

# 写 ports.json（atomic via python replace）— 必须在 with_lock 内执行，避免 TOCTOU 竞态
OUT_FILE="$(mktemp "$CLAUDE_DIR/.ports.XXXXXX.json")"
LOCK_ERR="$(mktemp "$CLAUDE_DIR/.port-claim.err.XXXXXX")"
if ! with_lock "$PORT_POOL_FILE.lock" "$PYTHON_BIN" "$PY_SCRIPT" > "$OUT_FILE" 2> "$LOCK_ERR"; then
  ERR="$(cat "$LOCK_ERR" 2>/dev/null || true)"
  rm -f "$OUT_FILE" "$LOCK_ERR"
  if [ "$ERR" = "POOL_EXHAUSTED" ]; then
    die "端口池耗尽（backend 剩 0 / frontend 剩 0）。请对 archived team 跑 cleanup 子命令释放。"
  fi
  die "port-claim 失败：$ERR"
fi
rm -f "$LOCK_ERR"

mkdir -p "$(dirname "$PORTS_FILE")"
"$PYTHON_BIN" -c "import os,sys; os.replace(sys.argv[1], sys.argv[2])" "$OUT_FILE" "$PORTS_FILE"
rm -f "$OUT_FILE.err"
# 显式清理临时文件（防止泄漏到 .claude/）
rm -f "$PY_SCRIPT" "$OUT_FILE" "$LOCK_ERR"

cat "$PORTS_FILE"
B="$("$PYTHON_BIN" -c "import json; print(json.load(open('$PORTS_FILE'))['backend'])")"
F="$("$PYTHON_BIN" -c "import json; print(json.load(open('$PORTS_FILE'))['frontend'])")"
log "分配端口 backend=$B frontend=$F 给 team=$TEAM_ID"