#!/usr/bin/env node
/**
 * Verify time-weighted average aggregation (research.md R-5).
 *
 * Usage: node scripts/verify-profile-aggregation.mjs
 *
 * Linear decay formula:
 *   weight_n = 1 + (n - 1) * decay_factor
 *   weighted_avg = sum(score_n * weight_n) / sum(weight_n)
 *
 * Example: 3 scores [3.0, 3.5, 4.0] → weights [1.0, 1.2, 1.4] → ≈ 3.56
 */

const DECAY_FACTOR = 0.2;
const PRECISION = 2;

function round(v) {
  return Math.round(v * 100) / 100;
}

function timeWeightedAverage(scores) {
  const n = scores.length;
  if (n === 0) return 0;
  if (n === 1) return scores[0];

  const weights = scores.map((_, i) => 1.0 + i * DECAY_FACTOR);
  const weightedSum = scores.reduce((sum, score, i) => sum + score * weights[i], 0);
  const weightSum = weights.reduce((a, b) => a + b, 0);
  return round(weightedSum / weightSum);
}

// Test cases
const tests = [
  { scores: [3.0, 3.5, 4.0], expected: 3.56, label: "3 ascending scores" },
  { scores: [5.0], expected: 5.0, label: "Single score" },
  { scores: [5.0, 5.0, 5.0], expected: 5.0, label: "All equal scores" },
  { scores: [8.0, 6.0, 4.0], expected: 5.78, label: "Descending scores (recent lower)" },
  { scores: [], expected: 0, label: "Empty input" },
  { scores: [10.0, 9.0, 8.0, 7.0], expected: 8.31, label: "4 descending scores" },
];

let passed = 0;
let failed = 0;

console.log("=== Profile Aggregation Verification ===\n");
console.log(`Decay factor: ${DECAY_FACTOR}`);
console.log(`Precision: ${PRECISION} decimal places\n`);

for (const { scores, expected, label } of tests) {
  const result = timeWeightedAverage(scores);
  const ok = Math.abs(result - expected) < 0.02;
  if (ok) {
    console.log(`  ✓ ${label}: [${scores.join(", ")}] → ${result} (expected ${expected})`);
    passed++;
  } else {
    console.log(`  ✗ ${label}: [${scores.join(", ")}] → ${result} (expected ${expected}, got ${result})`);
    failed++;
  }
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
