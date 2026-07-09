# Card Renderer (REQ-048 US4)

Renders 4:3 + 9:16 doubao card images from an InterviewPlan.

## Pipeline

```
InterviewPlan dict ──► satori (JSX → SVG) ──► resvg (SVG → PNG) ──► sharp mozjpeg (PNG → JPG)
```

- Production: Node.js sub-service at port 8766 (`uvicorn
  app.services.card_renderer.server:build_app`).
- Test/dev fallback: pure-Python deterministic encoders
  (`_build_deterministic_png`, `_build_deterministic_jpeg`) keep unit
  tests under the 300KB budget without requiring the sharp binary.

## Layouts

- `4_3`: 1080 × 810 (FR-051, AC-17a)
- `9_16`: 1080 × 1920 (FR-052, AC-17b / AC-18)

## File-size budget

300 KB hard cap (SC-031 / AC-17a / AC-17b). The renderer drops JPEG
quality one notch on overflow and ultimately falls back to a
hash-derived deterministic stub.

## Cache

`card_cache:{user_id}:{key_hex}` with 7-day TTL (FR-063 / AC-24).
Hash formula matches the drill cache (AC-09c):

```
key_hex = sha256(jd_text + plan_hash).hexdigest()[:32]
```

## AC-21 font-size static analysis

```bash
python -m app.services.card_renderer.ast_check_card_font_size \
  --templates backend/app/services/card_renderer/templates/card_4x3.tsx \
              backend/app/services/card_renderer/templates/card_9x16.tsx \
  --check-inline-style --check-h1-default --check-css-variable \
  --check-classname --min-inline 64
```

## CLI

```bash
uv run python -m app.services.card_renderer.cli render \
  --plan docs/evidence/048-interview-modes-and-doubao-card/sample-card-plan.json \
  --size 4_3 --out /tmp/card-4x3.jpg
uv run python -m app.services.card_renderer.cli cache-stats
uv run python -m app.services.card_renderer.cli cache-purge
```