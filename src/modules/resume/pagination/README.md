# Resume Pagination

Smart A4 pagination using `rs-md-html-parser`.

## Public API

```typescript
import { paginateDom, applySinglePageMode, attachWindowScaleListener } from '@/modules/resume/pagination'

// After rendering HTML into a DOM node:
const { pageCount, separators } = paginateDom(domNode)
console.log(`${pageCount} pages`)

// Single-page mode (clip to first A4 page):
applySinglePageMode(domNode, true)

// Window resize auto-scale (for narrow windows):
const detach = attachWindowScaleListener()
```

## Algorithm

`rs-md-html-parser`'s `htmlParser(domNode)` walks the rendered DOM, computes
A4 page boundaries, inserts `.rs-line-split` separator elements at break
points, and sets `data-pages="<n>"` on the root.

## Debouncing

Pagination should be debounced on frequent content changes (e.g., typing).
Use a 500ms debounce to avoid recalculating on every keystroke.

```typescript
const debouncedPaginate = useMemo(() => debounce(paginateDom, 500), [])
```
