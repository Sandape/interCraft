/** Mutation hooks for PDF export operations. */
import { useMutation } from '@tanstack/react-query'
import { downloadExportPdf } from '@/api/abilityProfileClient'

/** Sync PDF download (Feature 024). */
export function useExportPdf() {
  return useMutation({
    mutationFn: downloadExportPdf,
  })
}

/** @deprecated Prefer useExportPdf */
export function useTriggerExport() {
  return useExportPdf()
}

/** @deprecated Prefer useExportPdf */
export function useDownloadExport() {
  return useExportPdf()
}
