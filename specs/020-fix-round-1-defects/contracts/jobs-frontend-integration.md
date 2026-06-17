# Contract: Jobs Frontend Integration (FIX-002 / FIX-009 / FIX-010)

This contract covers the three frontend defects that 019 left unaddressed.
It does not change the backend API surface; it tightens the frontend's
behavior to match what the backend already returns.

## 1. Affected Defects

| Defect | Issue | Fix |
|---|---|---|
| D-014 (P1) | `JobsDetailPanel` component exists with all data-testids but is never imported into `src/pages/Jobs.tsx`. Job list rows have no onClick; the 5 new fields are not visible in the UI. | Mount the component; wire row onClick. |
| D-016 (P2) | `/jobs` (and other protected routes) do not redirect to `/login` for unauthenticated visitors. | Add a `requireAuth` loader to `src/router.tsx`. |
| D-017 (P2) | `headcount` `<Input>` is missing `type="number"` and `min="1"`. Users can paste `0` or negative numbers. | Add HTML hard constraints. |

## 2. Job Detail Panel Mount (FIX-002)

### 2.1 File-Level Edits

**File**: `src/pages/Jobs.tsx`

```tsx
// New imports at top of file
import { JobsDetailPanel } from '@/components/jobs/JobsDetailPanel'

// New state inside <Jobs /> (or whatever component owns the list)
const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
const selectedJob = useMemo(
  () => jobs?.find((j) => j.id === selectedJobId) ?? null,
  [jobs, selectedJobId]
)

// List row onClick
<tr
  key={j.id}
  data-testid={`job-row-${j.id}`}
  onClick={() => setSelectedJobId(j.id)}
  className="cursor-pointer hover:bg-gray-50"
>
  ...
</tr>

// Conditional render below the list
{selectedJob && (
  <Card data-testid="job-detail-panel" className="p-4 mt-4">
    <JobsDetailPanel
      job={selectedJob}
      onClose={() => setSelectedJobId(null)}
    />
  </Card>
)}
```

### 2.2 Dead-Component Guard

Add a `useEffect` (dev-only) to `JobsDetailPanel.tsx` that warns if the
component is mounted in a context where it cannot find its parent card.
This catches future "component shipped but not wired" regressions:

```tsx
useEffect(() => {
  if (process.env.NODE_ENV === 'production') return
  const id = setTimeout(() => {
    const el = document.querySelector('[data-testid="job-detail-panel"]')
    if (!el) {
      console.warn(
        '[JobsDetailPanel] mounted without a parent <Card data-testid="job-detail-panel">. ' +
        'Check that <JobsDetailPanel /> is rendered inside Jobs.tsx, not as a standalone page.'
      )
    }
  }, 1000)
  return () => clearTimeout(id)
}, [])
```

### 2.3 Test IDs Exposed

`JobsDetailPanel` already exposes (per `data-testid` audit):

| Test ID | Element | Used by |
|---|---|---|
| `job-detail-panel` | root container | A1 (UI render) |
| `job-detail-company`, `job-detail-position` | header | A1 |
| `job-detail-base-location`, `job-detail-requirements-md`, `job-detail-employment-type`, `job-detail-salary-range-text`, `job-detail-headcount` | 5 new fields | A1, B4 |
| `job-detail-resume-cta` | "为该岗位创建简历分支" button | B1, B2, B6 |
| `job-detail-interview-cta` | "为该岗位开始模拟面试" button | C1, C6 |

No `data-testid` changes are required to `JobsDetailPanel.tsx`; only the
mount in `Jobs.tsx` is missing.

## 3. Auth Guard (FIX-009)

### 3.1 Router-Level Loader

**File**: `src/router.tsx`

```tsx
import { redirect } from 'react-router-dom'

const PROTECTED_PATHS = new Set([
  '/jobs',
  '/resumes',
  '/resumes/branches/:id?',
  '/error-book',
  '/interview',
  '/interview/:id',
  '/profile',
  '/profile/:dim?',
])

const requireAuth = () => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    throw redirect('/login')
  }
  return null
}
```

Apply `loader: requireAuth` to each protected route. Use a route guard
wrapper component for any nested children:

```tsx
{
  path: '/jobs',
  loader: requireAuth,
  element: <Jobs />,
}
```

### 3.2 Token Check Heuristic

The current token storage is `localStorage` (per the round-1 evidence
section 5.4). A future migration to httpOnly cookies is out of scope; for
this fix we read `localStorage.getItem('access_token')`.

The 401 path (token present but invalid) is handled by the existing
`apiClient` interceptor that clears the token and calls
`window.location.assign('/login')`. No new logic is needed for the 401
case.

### 3.3 Edge Case: Interview Live Refresh

`/interview/:id` should still allow the page to be deep-linked **after**
auth. The loader checks token presence only; once on the page, an invalid
token surfaces as 401 → redirect (existing flow).

## 4. headcount HTML Constraints (FIX-010)

### 4.1 Create Modal

**File**: `src/pages/Jobs.tsx` (around the create modal, line ~415-421 per
D-017 evidence)

```tsx
<Input
  type="number"
  min={1}
  step={1}
  inputMode="numeric"
  value={headcount}
  onChange={(e) => setHeadcount(e.target.value.replace(/[^0-9]/g, ''))}
  placeholder="如:5"
  data-testid="job-create-headcount"
/>
```

### 4.2 Edit Modal

The same change is applied in the Job edit modal. The `data-testid` for
the edit field is `job-edit-headcount` (already in the codebase).

### 4.3 Form Validation Message

When the browser blocks the value (e.g., user pastes `-1`), the standard
HTML5 validation tooltip appears. No additional JavaScript validation is
required; the `replace(/[^0-9]/g, '')` filter in the onChange handler is
kept as a belt-and-suspenders guard.

## 5. Test Cases (Round-1 rerun + Round-2)

| ID | File | Description | Anchor |
|---|---|---|---|
| A1 (Round-1) | `tests/e2e/round-1/full-jobs-fields.spec.ts` | Click job row → panel visible → 5 fields rendered. Rerun for regression. | FIX-002 |
| A2 (Round-1) | `tests/e2e/round-1/full-jobs-fields.spec.ts` | UI blocks `headcount` > 99 chars or `-1` paste. Rerun for regression. | FIX-010 |
| B1 (Round-1) | `tests/e2e/round-1/full-resume-binding.spec.ts` | Job detail CTA → resume editor prefill. Rerun for regression. | FIX-002 |
| B4 (Round-1) | `tests/e2e/round-1/full-resume-binding.spec.ts` | `requirements_md` folded card visible. Rerun for regression. | FIX-002 |
| C1 (Round-1) | `tests/e2e/round-1/full-interview-job.spec.ts` | Branch bound → CTA clickable. Rerun for regression. | FIX-002 |
| C6 (Round-1) | `tests/e2e/round-1/full-interview-job.spec.ts` | Branch unbound → CTA disabled with tooltip. Rerun for regression. | FIX-002 |
| E4 (Round-1) | `tests/e2e/round-1/full-permissions.spec.ts` | `/jobs` without token → redirect `/login`. Rerun for regression. | FIX-009 |
| GUARD-01 (Round-2) | `tests/e2e/round-2/auth-guard.spec.ts` | `/jobs` no token → `redirect('/login')`. | FIX-009 |
| GUARD-02 (Round-2) | `tests/e2e/round-2/auth-guard.spec.ts` | `/error-book` no token → `redirect('/login')`. | FIX-009 |
| GUARD-03 (Round-2) | `tests/e2e/round-2/auth-guard.spec.ts` | `/resumes` no token → `redirect('/login')`. | FIX-009 |
| GUARD-04 (Round-2) | `tests/e2e/round-2/auth-guard.spec.ts` | `/interview/:id` no token → `redirect('/login')`. | FIX-009 |

## 6. Out of Scope

- Migration of `localStorage` token to httpOnly cookie (security
  hardening, separate feature).
- Refactoring `Jobs.tsx` into smaller components. The change is
  additive; existing code paths are preserved.
- Mobile responsive redesign of the detail panel.
