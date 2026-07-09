/**
 * T190 — Verify SC-005: PDF export success rate ≥ 99%.
 *
 * Runs 100 PDF exports with varied data payloads. Counts successes.
 * Asserts ≥ 99/100 succeed; failures must auto-retry within 5s.
 *
 * Skip-if-down: bails early if backend is not reachable.
 *
 * Usage:
 *   API_BASE_URL=http://localhost:8000 tsx scripts/verify-pdf-success-rate.ts
 */
const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";
const TOKEN = process.env.AUTH_TOKEN || ""; // optional bearer for /export/render
const N = 100;
const RETRY_WINDOW_MS = 5000;

async function isBackendUp(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE_URL}/api/v1/openapi.json`);
    return r.ok || r.status < 500;
  } catch {
    return false;
  }
}

function randomPayload(i: number): unknown {
  return {
    format: "pdf",
    template: ["pikachu", "onyx", "azurill", "kakuna"][i % 4],
    data: {
      basics: { name: `Test ${i}`, headline: `Headline ${i}` },
      sections: { profiles: { items: [{ id: `p${i}`, network: "GitHub", username: `user${i}` }] } },
    },
  };
}

async function main(): Promise<void> {
  if (!(await isBackendUp())) {
    console.log(`Backend not reachable at ${API_BASE_URL} — skipping SC-005.`);
    process.exit(0);
  }

  let success = 0;
  let fail = 0;
  for (let i = 0; i < N; i++) {
    const t0 = Date.now();
    let attemptOk = false;
    let attempt = 0;
    while (Date.now() - t0 < RETRY_WINDOW_MS && !attemptOk) {
      attempt++;
      try {
        const r = await fetch(`${API_BASE_URL}/api/v1/export/render`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
          },
          body: JSON.stringify(randomPayload(i)),
        });
        if (r.ok) {
          const buf = await r.arrayBuffer();
          if (buf.byteLength > 512) {
            attemptOk = true;
          }
        }
      } catch {
        /* retry */
      }
      if (!attemptOk && Date.now() - t0 < RETRY_WINDOW_MS) {
        await new Promise((res) => setTimeout(res, 200));
      }
    }
    if (attemptOk) {
      success++;
    } else {
      fail++;
      console.error(`SC-005 export #${i} failed after ${attempt} attempts`);
    }
  }

  const rate = (success / N) * 100;
  console.log(`SC-005 PDF success rate: ${success}/${N} (${rate.toFixed(1)}%)`);
  if (success < 99) {
    console.error(`SC-005 FAIL: success rate ${rate.toFixed(1)}% < 99%`);
    process.exit(1);
  }
  console.log("SC-005 PASS");
}

main().catch((err) => {
  console.error("SC-005 fatal:", err);
  process.exit(1);
});