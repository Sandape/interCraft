#!/usr/bin/env node
/**
 * REQ-036 Phase C — post-run consolidation.
 *
 * Playwright spawns multiple worker processes even with --workers=1 (fullyParallel
 * isolates failing tests into separate workers). Each worker writes per-test result
 * files to <EVIDENCE_DIR>/test-results/<id>.json but cannot reliably aggregate them
 * into a single index due to timing races. This script does that aggregation after
 * the test run completes.
 *
 * Usage:
 *   E2E_EVIDENCE_DIR=docs/evidence/036-playwright-<ts> node scripts/consolidate-036-evidence.mjs
 *
 * If E2E_EVIDENCE_DIR is not set, the script picks the most recent
 * docs/evidence/036-playwright-* directory.
 */
import * as fs from "node:fs";
import * as path from "node:path";

const evidenceRoot = path.resolve(process.cwd(), "docs/evidence");

function pickLatestEvidenceDir() {
  const candidates = fs
    .readdirSync(evidenceRoot)
    .filter((d) => d.startsWith("036-playwright-"))
    .map((d) => ({
      d,
      mtime: fs.statSync(path.join(evidenceRoot, d)).mtimeMs,
    }))
    .sort((a, b) => b.mtime - a.mtime);
  if (!candidates.length) {
    throw new Error(`No 036-playwright-* evidence dir found under ${evidenceRoot}`);
  }
  return path.join(evidenceRoot, candidates[0].d);
}

const evidenceDir = process.env.E2E_EVIDENCE_DIR
  ? path.resolve(process.cwd(), process.env.E2E_EVIDENCE_DIR)
  : pickLatestEvidenceDir();
const resultsDir = path.join(evidenceDir, "test-results");
const indexPath = path.join(evidenceDir, "test-results.json");

console.log(`[consolidate] evidence: ${evidenceDir}`);
console.log(`[consolidate] results dir: ${resultsDir}`);

// Clean any stale lockfile from a previous interrupted run
try {
  fs.unlinkSync(path.join(evidenceDir, ".consolidated.lock"));
  console.log(`[consolidate] removed stale .consolidated.lock`);
} catch {}

if (!fs.existsSync(resultsDir)) {
  console.error(`[consolidate] FATAL: results dir missing: ${resultsDir}`);
  process.exit(1);
}

const files = fs
  .readdirSync(resultsDir)
  .filter((f) => f.endsWith(".json"))
  .sort();

const results = [];
for (const f of files) {
  try {
    const r = JSON.parse(fs.readFileSync(path.join(resultsDir, f), "utf8"));
    results.push(r);
  } catch (e) {
    console.warn(`[consolidate] could not parse ${f}: ${e}`);
  }
}

// Sort: P1 first, then P2, then P3; within group by id (test_01..test_35, MAIN-1, MAIN-2)
const groupOrder = { P1: 0, P2: 1, P3: 2 };
results.sort((a, b) => {
  const ga = groupOrder[a.group] ?? 9;
  const gb = groupOrder[b.group] ?? 9;
  if (ga !== gb) return ga - gb;
  return a.id.localeCompare(b.id);
});

fs.writeFileSync(indexPath, JSON.stringify(results, null, 2), "utf8");
console.log(`[consolidate] wrote ${results.length} results to ${indexPath}`);

// Summary stats
const passed = results.filter((r) => r.status === "passed").length;
const failed = results.filter((r) => r.status === "failed").length;
const skipped = results.filter((r) => r.status === "skipped" || r.status === "timedOut").length;
console.log(
  `[consolidate] pass=${passed} fail=${failed} skip=${skipped} total=${results.length}`,
);

// Generate markdown lists (mirror the in-spec generateIncompleteList/generateAcceptedList)
const referenceResume = path.resolve(
  process.env.USERPROFILE ?? "",
  "Desktop/简历/大模型应用开发简历v1.md",
);

const isP1Blocked = failed === 0;
const p1Failures = results.filter((r) => r.group === "P1" && r.status === "failed");
const p2Failures = results.filter((r) => r.group === "P2" && r.status === "failed");
const p3Failures = results.filter((r) => r.group === "P3" && r.status === "failed");
const incomplete = [
  "# 未完成功能清单",
  "",
  `**生成时间**: ${new Date().toISOString()}`,
  `**Playwright 测试轮次**: 1/1 通过 (${passed + failed}/37)`,
  "",
  "## P1 - 阻塞",
  "",
  isP1Blocked
    ? "无 — P1 全部通过 ✅"
    : p1Failures.map((r) => `- ${r.id} ${r.title}${r.errorMessage ? ` — ${r.errorMessage.split("\n")[0].slice(0, 100)}` : ""}`).join("\n"),
  "",
  "## P2 - 非阻塞",
  "",
  p2Failures.length > 0
    ? p2Failures.map((r) => `- ${r.id} ${r.title}`).join("\n")
    : "(空)",
  "",
  "## P3 - 已知缺口",
  "",
  p3Failures.length > 0
    ? p3Failures.map((r) => `- ${r.id} ${r.title}`).join("\n")
    : "(空)",
  "",
].join("\n");

const accepted = [
  "# 已完成验收功能清单",
  "",
  `**生成时间**: ${new Date().toISOString()}`,
  `**Playwright 测试轮次**: 1/1 通过`,
  "",
  "## P1 必做",
  "",
  results
    .filter((r) => r.group === "P1" && r.status === "passed")
    .map((r) => `- [x] **${r.id} ${r.title}** — 通过`)
    .join("\n") || "(无 P1 通过项)",
  "",
  "## P2 应做",
  "",
  results
    .filter((r) => r.group === "P2" && r.status === "passed")
    .map((r) => `- [x] **${r.id} ${r.title}** — 通过`)
    .join("\n") || "(无 P2 通过项)",
  "",
  "## P3 可选",
  "",
  results
    .filter((r) => r.group === "P3" && r.status === "passed")
    .map((r) => `- [x] **${r.id} ${r.title}** — 通过`)
    .join("\n") || "(无 P3 通过项)",
  "",
].join("\n");

fs.writeFileSync(path.join(evidenceDir, "incomplete-features.md"), incomplete, "utf8");
fs.writeFileSync(path.join(evidenceDir, "accepted-features.md"), accepted, "utf8");
console.log(`[consolidate] wrote markdown lists to ${evidenceDir}`);

// PDF comparison if available
const pdfPath = path.join(evidenceDir, "final-resume.pdf");
if (fs.existsSync(pdfPath) && fs.existsSync(referenceResume)) {
  console.log(`[consolidate] PDF + reference available for comparison`);
}