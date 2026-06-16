/** Shared TypeScript types for the Jobs module. */

export interface JobTransitionEdge {
  from: string
  to: string
}

export interface JobTransitionsResponse {
  statuses: string[]
  transitions: JobTransitionEdge[]
}
