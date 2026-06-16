# Data Model: Resume Export Gateway

## ExportRequest

Represents the user's binary export request.

Fields:

- `markdown`: required string; must contain non-whitespace content; maximum 500 KB.
- `style_id`: required string; one of the supported resume style identifiers.
- `format`: required string; one of `pdf`, `png`, or `jpeg`.
- `locale`: optional string; defaults to `zh`.

Validation:

- Empty markdown is rejected with `EMPTY_CONTENT`.
- Unknown style is rejected with `INVALID_STYLE`.
- Unknown format is rejected with `INVALID_FORMAT`.
- Oversized markdown is rejected with `CONTENT_TOO_LARGE`.

## ExportResult

Represents a successful binary render.

Fields:

- `content`: binary file bytes.
- `media_type`: `application/pdf`, `image/png`, or `image/jpeg`.
- `filename`: downloadable filename with extension matching the requested format.
- `request_id`: request correlation identifier returned in the response header.

Lifecycle:

1. Request is validated.
2. Renderer is invoked.
3. Binary response is returned.
4. No server-side export record is retained.

## ExportError

Represents a validation or rendering failure.

Fields:

- `error`: stable code such as `EMPTY_CONTENT` or `RENDERING_FAILED`.
- `message`: user-safe diagnostic text.
- `request_id`: correlation identifier for logs.

Lifecycle:

1. Failure is detected before or during rendering.
2. Failure is logged with `request_id`.
3. Structured JSON error is returned.
4. Frontend keeps the export menu open and displays the message.
