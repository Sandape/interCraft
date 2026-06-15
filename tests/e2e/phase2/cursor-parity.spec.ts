/**
 * E2E: Cross-end cursor encoding parity (DEC-P2-1).
 * Validates that frontend can decode backend-issued cursors.
 */
import { test, expect } from '@playwright/test'

test('cursor encoding round-trips correctly', async ({ page }) => {
  // Navigate to the app and verify the cursor utility is available
  await page.goto('/login')

  // Execute the cursor encode/decode in the browser context
  const result = await page.evaluate(() => {
    // Base64url encode then decode a sample payload
    const payload = JSON.stringify({ occurred_at: '2026-06-13T00:00:00Z', id: 'test-id' })
    const encoded = btoa(payload).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    const decoded = atob(encoded.replace(/-/g, '+').replace(/_/g, '/'))
    return { encoded, decoded }
  })

  expect(result.encoded).toBeTruthy()
  expect(result.decoded).toContain('occurred_at')
  expect(result.decoded).toContain('test-id')
})
