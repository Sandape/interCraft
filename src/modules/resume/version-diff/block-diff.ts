/**
 * Block-level diff between two ordered snapshots of resume blocks (spec 027 US7).
 *
 * Mirrors the backend `diff_blocks` algorithm so the frontend can preview a
 * diff locally without an extra round trip — though the canonical source of
 * truth is the backend endpoint at `/resume-branches/:id/versions/:v1/diff/:v2`.
 *
 * Classification:
 *   - unchanged: same (type|title) key + identical content_md
 *   - modified:  same key + different content_md
 *   - added:     present in newBlocks only
 *   - removed:   present in oldBlocks only
 *
 * For modified blocks, `lineDiff` carries a per-line entry with kind ∈
 * {unchanged, added, removed}; the VersionDiffView renders these with the
 * color code mandated by FR-050 (green add / red remove / yellow modify).
 */

import { diffArrays, type ArrayChange } from 'diff'

export interface SnapshotBlockLike {
  id: string
  type: string
  title: string | null
  content_md: string
  meta?: Record<string, unknown> | null
  order_index: string
}

export type DiffOp = 'unchanged' | 'added' | 'removed' | 'modified'

export interface BlockLineDiff {
  kind: 'unchanged' | 'added' | 'removed'
  text: string
}

export interface BlockDiff {
  op: DiffOp
  key: string
  type: string
  title: string | null
  oldBlock: SnapshotBlockLike | null
  newBlock: SnapshotBlockLike | null
  lineDiff: BlockLineDiff[] | null
}

export interface BranchDiff {
  name: string | null
  company: string | null
  position: string | null
  status: string | null
}

export interface VersionDiff {
  branchId: string
  oldVersionNo: number
  newVersionNo: number
  branchDiff: BranchDiff
  blocks: BlockDiff[]
  summary: { added: number; removed: number; modified: number; unchanged: number }
}

/** Pairwise diff helper for branch-level scalar fields. */
function pairDiff(oldVal: unknown, newVal: unknown): string | null {
  if (oldVal === newVal) return null
  return `${String(oldVal)} -> ${String(newVal)}`
}

function blockKey(b: SnapshotBlockLike): string {
  return `${b.type}|${b.title ?? b.id}`
}

/**
 * LCS-style line diff using `diff`'s sequence-matcher. Splits both strings
 * on '\n' and runs diffArrays, which is the same primitive Python's
 * difflib.SequenceMatcher wraps.
 */
export function lineDiff(a: string, b: string): BlockLineDiff[] {
  const aLines = a.split('\n')
  const bLines = b.split('\n')
  const changes = diffArrays(aLines, bLines)
  const out: BlockLineDiff[] = []
  for (const change of changes) {
    if (change.added) {
      for (const text of change.value) {
        out.push({ kind: 'added', text })
      }
    } else if (change.removed) {
      for (const text of change.value) {
        out.push({ kind: 'removed', text })
      }
    } else {
      for (const text of change.value) {
        out.push({ kind: 'unchanged', text })
      }
    }
  }
  return out
}

/**
 * Diff two ordered block lists by LCS-matching the (type|title) key sequence.
 *
 * Uses `diff.diffArrays` so behavior matches the Python backend closely
 * (both wrap an LCS / Myers-style matcher). `replace` opcodes emit a
 * removed block followed by an added block in order, so the rendered
 * diff reads as "old removed → new added".
 *
 * Uniqueness assumption: `(type|title)` is unique within a snapshot.
 * `diff.diffArrays` emits LCS subsequences where each key appears once,
 * so we can look up the matching block in each side by exact key match.
 */
export function diffBlocks(
  oldBlocks: SnapshotBlockLike[],
  newBlocks: SnapshotBlockLike[],
): BlockDiff[] {
  const oldByKey = new Map(oldBlocks.map((b) => [blockKey(b), b]))
  const newByKey = new Map(newBlocks.map((b) => [blockKey(b), b]))
  const oldKeys = oldBlocks.map(blockKey)
  const newKeys = newBlocks.map(blockKey)
  const changes = diffArrays(oldKeys, newKeys)
  const out: BlockDiff[] = []
  for (const change of changes) {
    if (change.added) {
      for (const key of change.value) {
        const next = newByKey.get(key)
        if (!next) continue
        out.push({
          op: 'added',
          key: blockKey(next),
          type: next.type,
          title: next.title,
          oldBlock: null,
          newBlock: next,
          lineDiff: null,
        })
      }
    } else if (change.removed) {
      for (const key of change.value) {
        const old = oldByKey.get(key)
        if (!old) continue
        out.push({
          op: 'removed',
          key: blockKey(old),
          type: old.type,
          title: old.title,
          oldBlock: old,
          newBlock: null,
          lineDiff: null,
        })
      }
    } else {
      // Equal span — look up by key. If content differs, mark as modified.
      for (const key of change.value) {
        const old = oldByKey.get(key)
        const next = newByKey.get(key)
        if (!old || !next) continue
        if (old.content_md === next.content_md) {
          out.push({
            op: 'unchanged',
            key: blockKey(old),
            type: old.type,
            title: old.title,
            oldBlock: old,
            newBlock: next,
            lineDiff: null,
          })
        } else {
          out.push({
            op: 'modified',
            key: blockKey(old),
            type: next.type,
            title: next.title,
            oldBlock: old,
            newBlock: next,
            lineDiff: lineDiff(old.content_md, next.content_md),
          })
        }
      }
    }
  }
  return out
}

/**
 * Compute diff summary counts from a BlockDiff[].
 * Kept separate so callers that already have a VersionDiff don't re-walk the list.
 */
export function summarize(blocks: BlockDiff[]): VersionDiff['summary'] {
  let added = 0, removed = 0, modified = 0, unchanged = 0
  for (const b of blocks) {
    if (b.op === 'added') added++
    else if (b.op === 'removed') removed++
    else if (b.op === 'modified') modified++
    else unchanged++
  }
  return { added, removed, modified, unchanged }
}

export function diffBranchFields(
  oldB: { name: string; company: string | null; position: string | null; status: string } | null,
  newB: { name: string; company: string | null; position: string | null; status: string } | null,
): BranchDiff {
  return {
    name: pairDiff(oldB?.name, newB?.name),
    company: pairDiff(oldB?.company, newB?.company),
    position: pairDiff(oldB?.position, newB?.position),
    status: pairDiff(oldB?.status, newB?.status),
  }
}

/** Re-export the underlying ArrayChange type for downstream consumers. */
export type { ArrayChange }