/**
 * Resume UI store — selection, drag, collapse state.
 */
import { create } from 'zustand'

interface ResumeUIState {
  selectedBranchId: string | null
  draggingBlockId: string | null
  collapsedBlockIds: Set<string>
  setSelectedBranch: (id: string | null) => void
  setDragging: (id: string | null) => void
  toggleCollapse: (id: string) => void
  reset: () => void
}

export const useResumeUIStore = create<ResumeUIState>((set, get) => ({
  selectedBranchId: null,
  draggingBlockId: null,
  collapsedBlockIds: new Set(),
  setSelectedBranch: (id) => set({ selectedBranchId: id }),
  setDragging: (id) => set({ draggingBlockId: id }),
  toggleCollapse: (id) => {
    const next = new Set(get().collapsedBlockIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    set({ collapsedBlockIds: next })
  },
  reset: () => set({ selectedBranchId: null, draggingBlockId: null, collapsedBlockIds: new Set() }),
}))
