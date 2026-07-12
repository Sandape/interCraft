/**
 * Convenience aliases over generated OpenAPI schemas (REQ-061 US8).
 * Source of truth: `src/types/generated/ai-metering.ts` from
 * `specs/061-ai-agent-production/contracts/ai-metering.openapi.yaml`.
 */
import type { components, operations } from './generated/ai-metering'

export type PointEventType = components['schemas']['PointEventType']
export type PointBucket = components['schemas']['PointBucket']
export type PointAccount = components['schemas']['PointAccount']
export type LedgerEntry = components['schemas']['LedgerEntry']
export type LedgerPage = components['schemas']['LedgerPage']
export type PointBudget = components['schemas']['PointBudget']
export type ExportJob = components['schemas']['ExportJob']

export type ListAIPointLedgerQuery = NonNullable<
  operations['listAIPointLedger']['parameters']['query']
>

export type ExportAIPointLedgerBody =
  operations['exportAIPointLedger']['requestBody']['content']['application/json']

export type UpdateAIPointBudgetBody =
  operations['updateAIPointBudget']['requestBody']['content']['application/json']
