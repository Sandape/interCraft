# Quickstart: Error Book Completion

## Prerequisites

- Backend dependencies installed for `backend/`
- Frontend dependencies installed at repo root
- A configured local database when running backend integration tests
- Vite dev server and FastAPI backend available for browser E2E

## Backend Validation

Run focused integration tests:

```powershell
cd backend
python -m pytest tests/integration/test_error_questions_crud.py -q
```

Expected:

- create/list/get/update/delete tests pass
- recall transitions pass
- invalid recall/reset tests pass
- cross-user access returns 404

## Curl Smoke Test

Start backend, register/login a user, then run:

```powershell
$API = "http://localhost:8000/api/v1"
$TOKEN = "<access_token>"
$Headers = @{ Authorization = "Bearer $TOKEN"; "Content-Type" = "application/json"; "X-Device-Fingerprint" = "quickstart-device" }

$created = Invoke-RestMethod -Method Post "$API/error-questions" -Headers $Headers -Body '{"question_text":"What is quicksort average complexity?","answer_text":"O(n log n)","dimension":"algorithm"}'
$created.frequency

$recalled = Invoke-RestMethod -Method Post "$API/error-questions/$($created.id)/recall" -Headers $Headers
$recalled.status
$recalled.frequency

Invoke-RestMethod -Method Get "$API/error-questions?dimension=algorithm" -Headers $Headers
```

Expected:

- create returns `201` with `frequency=3`
- first recall returns `status=practicing`, `frequency=2`
- list contains the created question

## Frontend Validation

Run focused repository/unit checks:

```powershell
npm test -- src/repositories/__tests__/ErrorQuestionRepository.test.ts
```

Run type check/build:

```powershell
npm run typecheck
npm run build
```

Expected:

- no TypeScript errors
- ErrorBook route compiles without hook-rule runtime hazards

## E2E Validation

Run the focused browser flow:

```powershell
npm run e2e -- tests/e2e/error-book-completion.spec.ts
```

Expected:

- normal flow creates a question, recalls it to mastered, resets it, and deletes it
- interrupted flow creates/recalls, navigates away, returns, and sees persisted state
- invalid create and invalid reset/recall show user-safe feedback

## Manual Browser Check

Open `/error-book` in the in-app browser:

- Verify Chinese text is readable
- Verify empty, list, detail, modal, success, and error states
- Verify no console errors
- Verify layout at desktop and narrow widths
