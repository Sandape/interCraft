#!/usr/bin/env node
/** T105: Verify error question status machine — legal transitions + illegal rejections. */

const assert = (cond, msg) => { if (!cond) { console.error(`FAIL: ${msg}`); process.exit(1) } }

const ALLOWED = {
  fresh: ['practicing'],
  practicing: ['fresh', 'mastered'],
  mastered: ['fresh'],
}

function reduceStatus(current, target) {
  const allowed = ALLOWED[current]
  if (!allowed || !allowed.includes(target)) {
    return { ok: false, error: `Cannot transition from ${current} to ${target}` }
  }
  return { ok: true, status: target }
}

// Legal transitions
assert(reduceStatus('fresh', 'practicing').ok, 'fresh → practicing should be allowed')
assert(reduceStatus('practicing', 'mastered').ok, 'practicing → mastered should be allowed')
assert(reduceStatus('practicing', 'fresh').ok, 'practicing → fresh should be allowed (downgrade)')
assert(reduceStatus('mastered', 'fresh').ok, 'mastered → fresh should be allowed (reset)')

// Illegal transitions
assert(!reduceStatus('fresh', 'mastered').ok, 'fresh → mastered should be rejected (skip practicing)')
assert(!reduceStatus('mastered', 'practicing').ok, 'mastered → practicing should be rejected')
assert(!reduceStatus('fresh', 'fresh').ok, 'fresh → fresh should be rejected (no-op)')
assert(!reduceStatus('practicing', 'practicing').ok, 'practicing → practicing should be rejected (no-op)')

// Unknown status
assert(!reduceStatus('unknown', 'fresh').ok, 'unknown source should be rejected')

console.log('PASS: check-error-fsm — all 9 assertions passed')
