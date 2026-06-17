/**
 * Round-1 DB helper: wraps dbq.py for assertions during tests.
 *
 * The actual DB inspection runs out-of-process via
 *   `uv run python -m scripts.dbq --user-id <uuid> sql "..."`
 * so tests do not need asyncpg in the Node process. The helper
 * formats the SQL into a shell-safe command and returns the stdout.
 *
 * dbq.py natively supports --user-id (sets `app.user_id` GUC inside a
 * transaction with SET LOCAL before SELECTs), which is the canonical
 * way to query user-scoped / RLS-protected tables.
 */
import { execSync } from 'node:child_process'

const REPO_ROOT = process.env.E2E_REPO_ROOT ?? 'D:/Project/eGGG'

export interface DbResult {
  rows: Array<Record<string, unknown>>
  raw: string
}

interface DbQueryOpts {
  /** UUID of the user to set as app.user_id for RLS bypass */
  userId?: string
}

export function dbQuery(sql: string, opts: DbQueryOpts = {}): DbResult {
  if (!opts.userId) {
    throw new Error(
      'dbQuery requires opts.userId — without it, RLS hides all user-scoped rows. ' +
        'Pass the user_id from the registered test user.',
    )
  }
  // Validate UUID-ish format
  if (!/^[0-9a-fA-F-]{32,36}$/.test(opts.userId)) {
    throw new Error(`dbQuery: invalid userId ${opts.userId!}`)
  }
  const escapedSql = sql.replace(/"/g, '\\"')
  // Force UTF-8 stdout so non-ASCII values (e.g. base_location='上海')
  // are not mojibake'd by the Windows default codepage.
  // We do NOT use `env VAR=val` because execSync on Windows spawns
  // cmd.exe, not bash, and `env` is not a recognized command there.
  // Instead, PYTHONIOENCODING is set in the env option below.
  const cmd =
    `cd "${REPO_ROOT}/backend" && uv run python -m scripts.dbq ` +
    `--user-id ${opts.userId} sql "${escapedSql}" --json --quiet`
  let stdout = ''
  try {
    stdout = execSync(cmd, {
      encoding: 'utf-8',
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      // Use bash shell on Windows so the `&&` chain and quoting work
      shell: process.platform === 'win32' ? 'D:/Develop/Git/bin/bash.exe' : '/bin/bash',
    })
  } catch (e: any) {
    const stderr = e?.stderr?.toString?.() ?? ''
    throw new Error(`dbq failed: ${stderr || e?.message}`)
  }
  const lines = stdout
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.startsWith('{'))
  return { rows: lines.map((l) => JSON.parse(l)), raw: stdout }
}

export function dbCount(table: string, where = '1=1', opts: DbQueryOpts = {}): number {
  const result = dbQuery(`SELECT COUNT(*)::int AS cnt FROM "${table}" WHERE ${where}`, opts)
  const row = result.rows[0]
  if (!row) return 0
  return Number((row as any).cnt)
}

export function dbScalar(sql: string, opts: DbQueryOpts = {}): unknown {
  const result = dbQuery(sql, opts)
  const row = result.rows[0]
  if (!row) return null
  return Object.values(row)[0]
}