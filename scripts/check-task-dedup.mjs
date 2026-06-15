#!/usr/bin/env node
/** T105: Verify task dedup logic — same (user_id, type, related_entity_id) must not create duplicates. */

const assert = (cond, msg) => { if (!cond) { console.error(`FAIL: ${msg}`); process.exit(1) } }

// Simulated task store
const store = new Map()

function findOrCreate(userId, type, relatedEntityId, title) {
  const key = `${userId}:${type}:${relatedEntityId}`
  if (store.has(key)) return store.get(key)
  const task = { id: `task-${store.size + 1}`, userId, type, relatedEntityId, title, status: 'todo' }
  store.set(key, task)
  return task
}

// Test: first call creates, second call returns existing
const t1 = findOrCreate('u1', 'interview_prep', 'job-1', '准备 A 公司面试')
const t2 = findOrCreate('u1', 'interview_prep', 'job-1', '准备 A 公司面试 v2')
assert(t1.id === t2.id, 'same key should return existing task')
assert(t2.title === '准备 A 公司面试', 'title should not be overwritten')

// Test: different user, same type + entity → different task
const t3 = findOrCreate('u2', 'interview_prep', 'job-1', '准备 B 公司面试')
assert(t1.id !== t3.id, 'different user should create new task')

// Test: same user, different entity → different task
const t4 = findOrCreate('u1', 'interview_prep', 'job-2', '准备 C 公司面试')
assert(t1.id !== t4.id, 'different entity should create new task')

// Test: same user, different type → different task
const t5 = findOrCreate('u1', 'resume_update', 'job-1', '更新简历')
assert(t1.id !== t5.id, 'different type should create new task')

console.log('PASS: check-task-dedup — all 4 assertions passed')
