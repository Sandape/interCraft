// spec: specs/018-fix-product-defects/spec.md — User Story 2 (defect #7)
// On interview resume, the summary banner must render Chinese, not
// "Restored N answers, N questions, N scores.".
import { test, expect } from '@playwright/test';

test.describe('interview resume — Chinese text', () => {
  test('served bundle has no legacy English "Restored ... answers" string', async ({ page }) => {
    await page.goto('/login');
    // Vite dev server exposes the page as HTML; entrypoint is /src/main.tsx
    const html = await page.request.get('http://localhost:5173/');
    const body = await html.text();
    // Look for any of the legacy substrings.  Vite serves the source
    // modules through @vite/client; we don't need to traverse the graph
    // because the legacy literal lived inside src/pages/InterviewLive.tsx.
    const offending = [
      'Restored {userAnswers.length} answers',
      'Restored ${userAnswers.length} answers',
    ];
    for (const phrase of offending) {
      expect(body, `index.html should not embed the legacy literal: ${phrase}`).not.toContain(phrase);
    }
    // Additionally, fetch InterviewLive.tsx via Vite's module endpoint and
    // assert directly on the source.
    const module = await page.request.get('http://localhost:5173/src/pages/InterviewLive.tsx');
    expect(module.status()).toBe(200);
    const src = await module.text();
    // Vite transforms JSX `Restored {x} answers` into separate string
    // fragments joined with commas. Match the literal "Restored " prefix
    // as a strong signal of the legacy banner.
    expect(src, 'src/pages/InterviewLive.tsx must not contain "Restored "').not.toContain('"Restored "');
  });
});
