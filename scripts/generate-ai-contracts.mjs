/**
 * generate-ai-contracts.mjs — Generate TypeScript types from REQ-061 OpenAPI YAML specs.
 *
 * Usage:
 *   node scripts/generate-ai-contracts.mjs          # write committed outputs
 *   node scripts/generate-ai-contracts.mjs --check  # fail if outputs differ from committed files
 *
 * Both modes first generate ALL contracts into an isolated temp directory.
 * Normal mode only publishes committed outputs once every generation succeeds,
 * so an OpenAPI generation failure can never leave a half-generated committed set.
 */
import { spawn } from 'node:child_process'
import { mkdirSync, existsSync, readFileSync, writeFileSync, copyFileSync, rmSync, mkdtempSync } from 'node:fs'
import { dirname, resolve, join, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const CHECK = process.argv.includes('--check')

const CONTRACTS = [
  {
    label: 'ai-runtime',
    input: resolve(ROOT, 'specs/061-ai-agent-production/contracts/ai-runtime.openapi.yaml'),
    output: resolve(ROOT, 'src/types/generated/ai-runtime.ts'),
  },
  {
    label: 'ai-metering',
    input: resolve(ROOT, 'specs/061-ai-agent-production/contracts/ai-metering.openapi.yaml'),
    output: resolve(ROOT, 'src/types/generated/ai-metering.ts'),
  },
  {
    label: 'ai-operations',
    input: resolve(ROOT, 'specs/061-ai-agent-production/contracts/ai-operations.openapi.yaml'),
    output: resolve(ROOT, 'src/types/generated/ai-operations.ts'),
  },
]

const openapiTsCli = resolve(ROOT, 'node_modules', 'openapi-typescript', 'bin', 'cli.js')

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function preflightInputs() {
  const missing = []
  for (const { label, input } of CONTRACTS) {
    if (!existsSync(input)) {
      missing.push(`  ${label}: ${input}`)
    }
  }
  if (missing.length > 0) {
    throw new Error(
      `missing OpenAPI spec(s) — cannot generate contracts:\n${missing.join('\n')}`,
    )
  }
}

function runOpenapiTypeScript(inputPath, outputPath) {
  return new Promise((resolvePromise, reject) => {
    const proc = spawn(process.execPath, [openapiTsCli, inputPath, '--output', outputPath], {
      stdio: 'inherit',
    })
    proc.on('error', reject)
    proc.on('exit', (code) => {
      if (code === 0) resolvePromise()
      else reject(new Error(`openapi-typescript exited ${code} for ${basename(inputPath)}`))
    })
  })
}

async function generateContract({ label, input, output }) {
  mkdirSync(dirname(output), { recursive: true })
  console.log(`[gen:ai-contracts] ${label}: ${input}`)
  await runOpenapiTypeScript(input, output)
  console.log(`[gen:ai-contracts]  -> ${output}`)
}

function filesEqual(a, b) {
  if (!existsSync(a) || !existsSync(b)) return false
  return readFileSync(a, 'utf8') === readFileSync(b, 'utf8')
}

/**
 * Detect the line-ending convention of an existing file.
 * Returns '\r\n' if the file contains any CRLF, otherwise '\n'.
 * If the file does not exist, defaults to '\n' (LF).
 */
function detectEOL(filePath) {
  if (!existsSync(filePath)) return '\n'
  return readFileSync(filePath, 'utf8').includes('\r\n') ? '\r\n' : '\n'
}

/**
 * Overwrite `filePath` so its line endings match `targetEOL`.
 * Preserves UTF-8 and the final newline (or lack thereof).
 */
function normalizeEOL(filePath, targetEOL) {
  let content = readFileSync(filePath, 'utf8')
  // Collapse all CRLF → LF
  content = content.replace(/\r\n/g, '\n')
  // Re-expand to CRLF if the target uses CRLF
  if (targetEOL === '\r\n') {
    content = content.replace(/\n/g, '\r\n')
  }
  writeFileSync(filePath, content, 'utf8')
}

/**
 * Generate every contract into `outputRoot/src/types/generated/<label>.ts`.
 */
async function generateToDirectory(outputRoot) {
  for (const contract of CONTRACTS) {
    const output = join(outputRoot, 'src/types/generated', `${contract.label}.ts`)
    await generateContract({ ...contract, output })
  }
}

/* ------------------------------------------------------------------ */
/*  Check mode                                                        */
/* ------------------------------------------------------------------ */

async function checkCommittedOutputs() {
  const tempRoot = mkdtempSync(join(tmpdir(), 'ai-contracts-check-'))
  console.log(`[gen:ai-contracts] check mode: regenerating to ${tempRoot}`)

  const failures = []
  try {
    await generateToDirectory(tempRoot)

    for (const { label, output } of CONTRACTS) {
      const generated = join(tempRoot, 'src/types/generated', `${label}.ts`)
      if (!existsSync(output)) {
        failures.push(`missing committed output: ${output}`)
        continue
      }
      const targetEOL = detectEOL(output)
      normalizeEOL(generated, targetEOL)
      if (!filesEqual(output, generated)) {
        failures.push(`drift detected: ${output}`)
      } else {
        console.log(`[gen:ai-contracts] ok ${label}`)
      }
    }
  } finally {
    rmSync(tempRoot, { recursive: true, force: true })
  }

  if (failures.length > 0) {
    for (const f of failures) {
      console.error(`[gen:ai-contracts] ${f}`)
    }
    console.error(
      '[gen:ai-contracts] run `npm run gen:ai-contracts` and commit the updated files',
    )
    throw new Error('contract type drift detected — regenerate and commit')
  }
  console.log('[gen:ai-contracts] all committed contract types are up to date')
}

/* ------------------------------------------------------------------ */
/*  Normal (generate) mode                                            */
/* ------------------------------------------------------------------ */

async function generateToCommitted() {
  const tempRoot = mkdtempSync(join(tmpdir(), 'ai-contracts-gen-'))
  console.log(`[gen:ai-contracts] generating to temp: ${tempRoot}`)

  try {
    await generateToDirectory(tempRoot)

    // Every OpenAPI generation completed successfully — now publish to committed locations
    for (const { label, output } of CONTRACTS) {
      const generated = join(tempRoot, 'src/types/generated', `${label}.ts`)
      mkdirSync(dirname(output), { recursive: true })
      const targetEOL = detectEOL(output)
      normalizeEOL(generated, targetEOL)
      copyFileSync(generated, output)
      console.log(`[gen:ai-contracts] wrote ${output}`)
    }
  } finally {
    rmSync(tempRoot, { recursive: true, force: true })
  }

  console.log('[gen:ai-contracts] done')
}

/* ------------------------------------------------------------------ */
/*  Entry point                                                       */
/* ------------------------------------------------------------------ */

async function main() {
  // Preflight — fail early if any input spec is missing
  preflightInputs()

  if (!existsSync(openapiTsCli)) {
    throw new Error('openapi-typescript is not installed. Run `npm install`.')
  }

  console.log(
    `[gen:ai-contracts] ${CHECK ? 'check' : 'generate'} mode (${CONTRACTS.length} contracts)`,
  )

  if (CHECK) {
    await checkCommittedOutputs()
    return
  }

  await generateToCommitted()
}

main().catch((err) => {
  console.error(`[gen:ai-contracts] ${err.message}`)
  process.exit(1)
})
