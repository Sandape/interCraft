# Quickstart: Resume Export Gateway

## Prerequisites

- Frontend dev server on `http://localhost:5173`
- Backend on `http://127.0.0.1:8000`
- Existing seeded or newly created resume branch with at least one block

## Validation

### 1. Backend contract tests

```bash
cd backend
uv run pytest tests/contract/test_resume_export_api.py -q
```

Expected: validation, success, and renderer-failure cases pass.

### 2. Frontend client tests

```bash
npm run test -- tests/unit/export-api.test.ts
```

Expected: filename parsing and structured error mapping pass.

### 3. Browser E2E

```bash
npx playwright test tests/e2e/resume-export-gateway.spec.ts --workers=1
```

Expected: PDF export triggers a download; forced server failure keeps the export menu open and shows an error.

### 4. curl success

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/export/render \
  -H "Content-Type: application/json" \
  -d "{\"markdown\":\"# Candidate\\n\\n## Summary\\n\\nSenior engineer\",\"style_id\":\"compact-one-page\",\"format\":\"pdf\"}" \
  --output resume.pdf
```

Expected: non-empty PDF file and HTTP 200 response headers.

### 5. curl validation error

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/export/render \
  -H "Content-Type: application/json" \
  -d "{\"markdown\":\"\",\"style_id\":\"compact-one-page\",\"format\":\"pdf\"}"
```

Expected: JSON error with `EMPTY_CONTENT`.

### 6. In-app browser

1. Open the resume editor.
2. Click Export.
3. Choose PDF and confirm a download starts.
4. Re-run with forced API failure and confirm the menu displays the error without navigation.
