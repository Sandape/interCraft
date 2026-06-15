#!/usr/bin/env node
/** T105: Verify ability dimension normalization — scores clamped to [0, 10], sub_scores validated. */

const assert = (cond, msg) => { if (!cond) { console.error(`FAIL: ${msg}`); process.exit(1) } }

function normalizeScore(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 0
  return Math.max(0, Math.min(10, value))
}

function normalizeDimension(dim) {
  const actual = normalizeScore(dim.actual_score)
  const ideal = normalizeScore(dim.ideal_score)
  const subScores = {}
  if (dim.sub_scores) {
    for (const [k, v] of Object.entries(dim.sub_scores)) {
      subScores[k] = {
        actual: normalizeScore(v.actual),
        ideal: normalizeScore(v.ideal),
      }
    }
  }
  return { ...dim, actual_score: actual, ideal_score: ideal, sub_scores: subScores }
}

// Test: scores in range pass through
const r1 = normalizeDimension({ actual_score: 5.5, ideal_score: 10, sub_scores: { fundamentals: { actual: 6, ideal: 10 } } })
assert(r1.actual_score === 5.5, 'in-range value should pass through')
assert(r1.sub_scores.fundamentals.actual === 6, 'sub-score in-range should pass through')

// Test: below 0 clamped
const r2 = normalizeDimension({ actual_score: -3, ideal_score: 10, sub_scores: {} })
assert(r2.actual_score === 0, 'negative score should clamp to 0')

// Test: above 10 clamped
const r3 = normalizeDimension({ actual_score: 15, ideal_score: 10, sub_scores: {} })
assert(r3.actual_score === 10, 'above-10 score should clamp to 10')

// Test: NaN → 0
const r4 = normalizeDimension({ actual_score: NaN, ideal_score: 10, sub_scores: {} })
assert(r4.actual_score === 0, 'NaN should default to 0')

// Test: null/undefined sub_scores handled
const r5 = normalizeDimension({ actual_score: 5, ideal_score: 10, sub_scores: null })
assert(r5.actual_score === 5, 'null sub_scores should not crash')
assert(Object.keys(r5.sub_scores).length === 0, 'null sub_scores should produce empty object')

// Test: sub_scores also clamped
const r6 = normalizeDimension({ actual_score: 5, ideal_score: 10, sub_scores: { fundamentals: { actual: -1, ideal: 20 } } })
assert(r6.sub_scores.fundamentals.actual === 0, 'negative sub-score should clamp')
assert(r6.sub_scores.fundamentals.ideal === 10, 'high sub-score should clamp')

console.log('PASS: check-ability-normalize — all 8 assertions passed')
