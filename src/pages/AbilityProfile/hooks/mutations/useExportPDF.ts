/** Mutation hooks for PDF export operations. */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { triggerExport, downloadExport } from '@/api/abilityProfileClient'

export function useTriggerExport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: triggerExport,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['exportList'] })
    },
  })
}

export function useDownloadExport() {
  return useMutation({
    mutationFn: async (exportId: string) => {
      const blob = await downloadExport(exportId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ability-profile-${exportId.slice(0, 8)}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    },
  })
}
