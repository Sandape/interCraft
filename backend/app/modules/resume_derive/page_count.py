"""PDF page counting for export hard-gate (REQ-055 FR-018)."""
from __future__ import annotations

import re
from io import BytesIO


def count_pdf_pages(pdf_bytes: bytes) -> int:
    """Return the number of pages in a PDF byte payload.

    Uses pypdf when available; falls back to counting ``/Type /Page``
    objects (excluding ``/Pages``) for lightweight test environments.
    """
    if not pdf_bytes:
        raise ValueError("empty PDF payload")

    try:
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            n = len(reader.pages)
            if n >= 1:
                return n
        except Exception:
            pass
    except ImportError:
        pass

    text = pdf_bytes.decode("latin-1", errors="ignore")
    # Negative lookahead so /Pages is not counted as /Page
    count = len(re.findall(r"/Type\s*/Page(?!\s*s)", text))
    if count < 1:
        raise ValueError("unable to determine PDF page count")
    return count
