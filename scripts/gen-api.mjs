/**
 * gen-api.mjs — fetch the OpenAPI schema from the running backend and
 * generate TypeScript types. Output: `src/api/schema.d.ts` (gitignored).
 *
 * Usage: `npm run gen:api` (requires the backend at $VITE_API_BASE_URL).
 */
import { spawn } from 'node:child_process'
import { writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const BASE = process.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const OUT = resolve(__dirname, '..', 'src', 'api', 'schema.d.ts')

if (!existsSync(dirname(OUT))) {
  mkdirSync(dirname(OUT), { recursive: true })
}

const url = `${BASE}/api/v1/openapi.json`
console.log(`[gen-api] fetching ${url}`)

const res = await fetch(url)
if (!res.ok) {
  console.error(`[gen-api] backend not reachable at ${url} (${res.status})`)
  console.error('[gen-api] start the backend first: `cd backend && uv run uvicorn app.main:app`')
  process.exit(1)
}
const schema = await res.json()

const openapiTs = resolve(__dirname, '..', 'node_modules', '.bin', 'openapi-typescript')
if (!existsSync(openapiTs)) {
  console.error('[gen-api] openapi-typescript is not installed. Run `npm install`.')
  process.exit(1)
}

const tmpFile = resolve(__dirname, '_openapi.json')
writeFileSync(tmpFile, JSON.stringify(schema, null, 2))

await new Promise((resolve, reject) => {
  const proc = spawn(openapiTs, [tmpFile, '--output', OUT], { stdio: 'inherit' })
  proc.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`openapi-typescript exited ${code}`))))
})

console.log(`[gen-api] wrote ${OUT}`)
