#!/usr/bin/env tsx
/**
 * CLI: render Markdown to HTML using the unified engine.
 * Used for E2E test fixtures and local debugging.
 *
 * Usage:
 *   npx tsx src/lib/resume-renderer/cli.ts --input foo.md --output foo.html
 *   npx tsx src/lib/resume-renderer/cli.ts --markdown "# Hello" --color '#2563eb'
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { renderMarkdown, sanitizeHtml } from './index'

interface Args {
  input?: string
  output?: string
  markdown?: string
  color?: string
}

function parseArgs(argv: string[]): Args {
  const args: Args = {}
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i]
    const next = argv[i + 1]
    if (arg === '--input' || arg === '-i') args.input = next
    else if (arg === '--output' || arg === '-o') args.output = next
    else if (arg === '--markdown' || arg === '-m') args.markdown = next
    else if (arg === '--color' || arg === '-c') args.color = next
    else if (arg === '--help' || arg === '-h') {
      console.log('Usage: cli.ts --input foo.md [--output foo.html] [--color "#2563eb"] [--markdown "# Hello"]')
      process.exit(0)
    }
  }
  return args
}

function main(): void {
  const args = parseArgs(process.argv)
  let markdown = args.markdown ?? ''
  if (args.input) {
    markdown = readFileSync(args.input, 'utf-8')
  }
  if (!markdown) {
    console.error('Error: provide --input <file> or --markdown <string>')
    process.exit(1)
  }
  const { html } = renderMarkdown(markdown, { accentColor: args.color })
  const safe = sanitizeHtml(html)
  if (args.output) {
    writeFileSync(args.output, safe, 'utf-8')
    console.log(`Wrote ${args.output} (${safe.length} bytes)`)
  } else {
    console.log(safe)
  }
}

main()
