/* ---- Resume branches & blocks ---- */

export type BranchStatus = 'draft' | 'optimizing' | 'ready' | 'submitted' | 'archived'

export type BlockType =
  | 'heading'
  | 'summary'
  | 'experience'
  | 'education'
  | 'project'
  | 'skill'
  | 'custom'

export interface ResumeBranch {
  id: string
  parent_id: string | null
  name: string
  company: string | null
  position: string | null
  status: BranchStatus
  match_score: number | null
  is_main: boolean
  is_pinned: boolean
  style_preference: string | null
  /** Theme id (default | blue | orange | pupple). Spec 027 US3. */
  theme_id: string
  /** HEX accent color (e.g. '#39393a'). Spec 027 US3. */
  accent_color: string
  last_edited_at: string
  created_at: string
  updated_at: string
  version_count: number
  block_count: number
}

export interface ResumeBlock {
  id: string
  branch_id: string
  type: BlockType
  title: string | null
  content_md: string
  content_html: string | null
  meta: Record<string, unknown> | null
  order_index: string
  collapsed: boolean
  created_at: string
  updated_at: string
}

export interface CreateBranchInput {
  name: string
  company?: string | null
  position?: string | null
  parent_id?: string | null
  is_main?: boolean
}

export interface PatchBranchInput {
  name?: string
  company?: string | null
  position?: string | null
  status?: BranchStatus
  is_pinned?: boolean
  style_preference?: string | null
  /** Theme id (default | blue | orange | pupple). Spec 027 US3. */
  theme_id?: string
  /** HEX accent color (e.g. '#39393a'). Spec 027 US3. */
  accent_color?: string
}

export interface CreateBlockInput {
  type: BlockType
  title?: string | null
  content_md?: string
  meta?: Record<string, unknown>
  prev_id?: string | null
  next_id?: string | null
}

export interface PatchBlockInput {
  type?: BlockType
  title?: string | null
  content_md?: string
  meta?: Record<string, unknown> | null
  collapsed?: boolean
}

export interface ReorderBlocksInput {
  prev_id: string | null
  next_id: string | null
}

export interface RefreshFromParentResponse {
  branch: ResumeBranch
  cloned_blocks: number
}

/* ---- Versions ---- */

export type VersionTrigger = 'manual' | 'auto' | 'ai'

export interface ResumeVersionSummary {
  id: string
  branch_id: string
  version_no: number
  label: string | null
  trigger: VersionTrigger
  is_full_snapshot: boolean
  author_type: 'user' | 'ai'
  actor_id: string | null
  created_at: string
}

export interface SnapshotBlock {
  id: string
  type: string
  title: string | null
  content_md: string
  meta: Record<string, unknown> | null
  order_index: string
}

export interface SnapshotBranch {
  id: string
  name: string
  company: string | null
  position: string | null
  status: string
}

export interface Snapshot {
  branch: SnapshotBranch
  blocks: SnapshotBlock[]
}

export interface ResumeVersionDetail extends ResumeVersionSummary {
  snapshot: Snapshot
}

export interface CreateVersionInput {
  label?: string
}

export interface RollbackResponse {
  new_branch_id: string
}
