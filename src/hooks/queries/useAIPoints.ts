/**
 * REQ-061 (US8) — TanStack Query hooks for AI point account / ledger / budget.
 *
 * Query keys are namespaced under `aiPoints`. No RMB/purchase mutations.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query'
import {
  exportAIPointLedger,
  getAIPointAccount,
  getAIPointBudget,
  listAIPointLedger,
  updateAIPointBudget,
} from '@/api/ai-metering'
import type {
  ExportAIPointLedgerBody,
  ExportJob,
  LedgerPage,
  ListAIPointLedgerQuery,
  PointAccount,
  PointBudget,
  UpdateAIPointBudgetBody,
} from '@/types/ai-metering'

/** Canonical TanStack Query key factory (T054). */
export const aiPointKeys = {
  all: ['aiPoints'] as const,
  account: () => [...aiPointKeys.all, 'account'] as const,
  ledgers: () => [...aiPointKeys.all, 'ledger'] as const,
  ledger: (filters?: ListAIPointLedgerQuery) =>
    [...aiPointKeys.ledgers(), filters ?? {}] as const,
  budget: () => [...aiPointKeys.all, 'budget'] as const,
}

export function useAIPointAccount(
  options?: Pick<UseQueryOptions<PointAccount>, 'enabled' | 'staleTime'>,
) {
  return useQuery({
    queryKey: aiPointKeys.account(),
    queryFn: ({ signal }) => getAIPointAccount(signal),
    staleTime: options?.staleTime ?? 15_000,
    enabled: options?.enabled ?? true,
    retry: 1,
  })
}

export function useAIPointLedger(
  filters: ListAIPointLedgerQuery = {},
  options?: Pick<UseQueryOptions<LedgerPage>, 'enabled' | 'staleTime'>,
) {
  return useQuery({
    queryKey: aiPointKeys.ledger(filters),
    queryFn: ({ signal }) => listAIPointLedger(filters, signal),
    staleTime: options?.staleTime ?? 15_000,
    enabled: options?.enabled ?? true,
    retry: 1,
  })
}

export function useAIPointBudget(
  options?: Pick<UseQueryOptions<PointBudget>, 'enabled' | 'staleTime'>,
) {
  return useQuery({
    queryKey: aiPointKeys.budget(),
    queryFn: ({ signal }) => getAIPointBudget(signal),
    staleTime: options?.staleTime ?? 15_000,
    enabled: options?.enabled ?? true,
    retry: 1,
  })
}

export function useExportAIPointLedger() {
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: ExportAIPointLedgerBody
      idempotencyKey: string
    }): Promise<ExportJob> => exportAIPointLedger(body, idempotencyKey),
  })
}

export function useUpdateAIPointBudget() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      body,
      idempotencyKey,
    }: {
      body: UpdateAIPointBudgetBody
      idempotencyKey: string
    }): Promise<PointBudget> => updateAIPointBudget(body, idempotencyKey),
    onSuccess: (data) => {
      queryClient.setQueryData(aiPointKeys.budget(), data)
    },
  })
}
