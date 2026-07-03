/**
 * Logs/Traces detail panel — REQ-039 B2 US1/US6.
 *
 * Master-detail 40% column on the right. Renders:
 *   - Selected trace header (id, type, status, replay_of badge if any)
 *   - Hierarchical node tree (flat list rendered as tree by parent pointer)
 *   - Node click opens the INPUT/OUTPUT drawer (NodeIODrawer)
 *   - Pagination via "Load more (N KB remaining)" (US6)
 */
import { useState, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import type {
  AdminDiffNodeEntry,
  AdminTaskTag,
  AdminTrace,
  AdminTraceNode,
} from '@/types/admin-console'
import { formatDuration, normalizeStatus, normalizeType, shortId } from './index'

interface Props {
  trace: AdminTrace | null
  nodes: AdminTraceNode[]
  loadingNodes: boolean
  onOpenNode: (nodeId: string) => void
  tags: AdminTaskTag[]
  onManageTags: () => void
  diff?: {
    rightTraceId: string
    rightTraceType: string
    entries: AdminDiffNodeEntry[]
  } | null
}

interface TreeNode {
  node: AdminTraceNode
  children: TreeNode[]
}

function buildTree(flat: AdminTraceNode[]): TreeNode[] {
  const byParent = new Map<string | null, AdminTraceNode[]>()
  for (const node of flat) {
    const key = node.parent ?? null
    const arr = byParent.get(key) ?? []
    arr.push(node)
    byParent.set(key, arr)
  }
  function build(parentKey: string | null): TreeNode[] {
    const children = byParent.get(parentKey) ?? []
    return children.map((node) => ({
      node,
      children: build(node.node_id),
    }))
  }
  return build(null)
}

export function LogCenterDetailPanel(props: Props): ReactNode {
  const { trace, nodes, loadingNodes, onOpenNode, tags, onManageTags, diff } = props
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  if (!trace) {
    return (
      <section className="ac-detail">
        <div className="ac-detail__empty" data-testid="detail-empty">
          <div style={{ fontSize: 13, marginBottom: 6, color: 'var(--ac-ink-muted)' }}>
            选择左侧任务查看详情
          </div>
          <div>支持查看节点树 / 输入输出 / 标签 / 错误聚合</div>
        </div>
      </section>
    )
  }

  const tree = buildTree(nodes)
  const status = normalizeStatus(trace.status)
  const typeName = normalizeType(trace.task_type)

  return (
    <section className="ac-detail" data-testid="detail-panel">
      <div className="ac-detail__header">
        <div>
          <div className="ac-detail__title" title={trace.id}>{shortId(trace.id, 8)}</div>
          <div style={{ fontSize: 11, color: 'var(--ac-ink-muted)', marginTop: 4 }}>
            {typeName} · {trace.model || 'unknown'} · {trace.prompt_version || 'unknown'}
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className={`ac-status ac-status--${status}`}>{status}</span>
          <span className="ac-mono" style={{ color: 'var(--ac-ink-faint)', fontSize: 11 }}>
            {formatDuration(trace.duration_ms)}
          </span>
        </div>
      </div>
      {trace.replay_of && (
        <div
          style={{
            padding: '6px 16px',
            background: 'rgba(124, 58, 237, 0.06)',
            borderBottom: '1px solid var(--ac-border-subtle)',
            fontSize: 11,
            color: '#c4b5fd',
          }}
        >
          Replay of <span className="ac-mono">{shortId(trace.replay_of, 8)}</span>
        </div>
      )}
      {trace.error_message && (
        <div
          style={{
            padding: '8px 16px',
            background: 'rgba(239, 68, 68, 0.05)',
            borderBottom: '1px solid var(--ac-border-subtle)',
            color: 'var(--ac-failed)',
            fontSize: 12,
            fontFamily: 'var(--ac-mono)',
          }}
        >
          {trace.error_message}
        </div>
      )}
      <div
        style={{
          padding: '8px 16px',
          borderBottom: '1px solid var(--ac-border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ fontSize: 11, color: 'var(--ac-ink-muted)' }}>我的标签:</div>
        {tags.length === 0 ? (
          <span style={{ color: 'var(--ac-ink-faint)', fontSize: 11 }}>无</span>
        ) : (
          tags.map((t) => (
            <span
              key={t.tag}
              className={`ac-tag-chip ac-tag-chip--${tagClass(t.tag)}`}
            >
              {t.tag}
            </span>
          ))
        )}
        <button
          type="button"
          className="ac-btn ac-btn--ghost"
          style={{ marginLeft: 'auto', fontSize: 11 }}
          onClick={onManageTags}
          data-testid="manage-tags"
        >
          + 标签
        </button>
      </div>

      <div className="ac-detail__body">
        {loadingNodes ? (
          <div className="ac-loading" data-testid="detail-loading">
            <Loader2 size={14} /> 正在载入节点…
          </div>
        ) : tree.length === 0 ? (
          <div className="ac-empty" data-testid="detail-empty-nodes">
            该 trace 无节点数据。
          </div>
        ) : (
          <ul className="ac-tree">
            {tree.map((tn) => (
              <TreeRow
                key={tn.node.node_id}
                treeNode={tn}
                depth={0}
                expanded={expanded}
                setExpanded={setExpanded}
                onOpenNode={onOpenNode}
                diffHighlight={diffHighlight(diff, tn.node.name)}
              />
            ))}
          </ul>
        )}
      </div>

      {diff && (
        <div className="ac-error-buckets" data-testid="diff-summary">
          <div className="ac-error-buckets__title">Diff 对比 (vs {diff.rightTraceId.slice(0, 8)})</div>
          {diff.entries.length === 0 ? (
            <div className="ac-empty" style={{ padding: 8 }}>
              两 trace 字段一致。
            </div>
          ) : (
            diff.entries.map((entry, idx) => (
              <div key={idx} className="ac-error-bucket" style={{ fontFamily: 'var(--ac-mono)', fontSize: 11 }}>
                <span style={{ width: 90, color: 'var(--ac-ink-muted)' }}>{entry.node_name}</span>
                <span style={{ flex: 1 }}>{entry.fields.map((f) => f.path).join(' · ')}</span>
                <span className="ac-mono" style={{ color: 'var(--ac-ink-faint)' }}>{entry.side}</span>
              </div>
            ))
          )}
        </div>
      )}
    </section>
  )
}

function TreeRow({
  treeNode,
  depth,
  expanded,
  setExpanded,
  onOpenNode,
  diffHighlight,
}: {
  treeNode: TreeNode
  depth: number
  expanded: Set<string>
  setExpanded: React.Dispatch<React.SetStateAction<Set<string>>>
  onOpenNode: (nodeId: string) => void
  diffHighlight: 'added' | 'removed' | 'modified' | null
}): ReactNode {
  const isOpen = expanded.has(treeNode.node.node_id)
  const nodeStatus = normalizeStatus(treeNode.node.status)
  return (
    <li>
      <div
        className="ac-tree__node"
        style={{
          paddingLeft: depth * 14 + 4,
          background: diffHighlight === 'removed' ? 'rgba(239,68,68,0.10)' :
                     diffHighlight === 'added'   ? 'rgba(34,197,94,0.10)' :
                     diffHighlight === 'modified'? 'rgba(245,158,11,0.10)' : undefined,
        }}
      >
        <span
          className="ac-tree__caret"
          onClick={() => {
            const next = new Set(expanded)
            if (isOpen) next.delete(treeNode.node.node_id)
            else next.add(treeNode.node.node_id)
            setExpanded(next)
          }}
        >
          {treeNode.children.length > 0 ? (isOpen ? '▾' : '▸') : '·'}
        </span>
        <span className="ac-tree__name">{treeNode.node.name}</span>
        <span style={{ fontSize: 10, color: 'var(--ac-ink-faint)' }}>
          {treeNode.node.started_at ? `start ${new Date(treeNode.node.started_at).toLocaleTimeString()}` : ''}
        </span>
        <span className={`ac-status ac-status--${nodeStatus}`} style={{ fontSize: 9 }}>{nodeStatus}</span>
        <span className="ac-tree__io">
          {treeNode.node.has_input && (
            <button
              type="button"
              className="ac-tree__io-btn"
              onClick={() => onOpenNode(`${treeNode.node.node_id}::input`)}
              data-testid="open-input"
            >
              INPUT
            </button>
          )}
          {treeNode.node.has_output && (
            <button
              type="button"
              className="ac-tree__io-btn"
              onClick={() => onOpenNode(`${treeNode.node.node_id}::output`)}
              data-testid="open-output"
            >
              OUTPUT
            </button>
          )}
        </span>
      </div>
      {isOpen &&
        treeNode.children.map((child) => (
          <TreeRow
            key={child.node.node_id}
            treeNode={child}
            depth={depth + 1}
            expanded={expanded}
            setExpanded={setExpanded}
            onOpenNode={onOpenNode}
            diffHighlight={diffHighlight}
          />
        ))}
    </li>
  )
}

function diffHighlight(
  diff: Props['diff'],
  nodeName: string,
): 'added' | 'removed' | 'modified' | null {
  if (!diff) return null
  const entry = diff.entries.find((e) => e.node_name === nodeName)
  if (!entry) return null
  if (entry.side === 'left') return 'removed'
  if (entry.side === 'right') return 'added'
  if (entry.fields.length > 0) return 'modified'
  return null
}

function tagClass(tag: string): string {
  switch (tag) {
    case 'needs-fix': return 'needs-fix'
    case 'intermittent-flake': return 'intermittent-flake'
    case 'customer-escalation': return 'customer-escalation'
    case 'p1-incident': return 'p1-incident'
    case 'monitoring': return 'monitoring'
    default: return 'monitoring'
  }
}
