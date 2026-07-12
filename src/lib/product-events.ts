export type ProductEventName =
  | 'homepage_primary_cta'
  | 'homepage_demo_cta'
  | 'demo_register_cta'
  | 'onboarding_step_completed'
  | 'onboarding_skipped'
  | 'onboarding_resumed'
  | 'onboarding_activated'

export interface ProductEventDetail {
  name: ProductEventName
  source: string
  step?: number
}

export function trackProductEvent(detail: ProductEventDetail): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent<ProductEventDetail>('intercraft:product-event', { detail }))
}
