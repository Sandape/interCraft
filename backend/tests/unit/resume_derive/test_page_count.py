"""Unit tests for PDF page counting (REQ-055)."""
from __future__ import annotations

import pytest

from app.modules.resume_derive.page_count import count_pdf_pages


def _minimal_pdf(pages: int) -> bytes:
    # Minimal-ish PDF with N page objects for fallback counter.
    parts = ["%PDF-1.4\n"]
    for i in range(pages):
        parts.append(f"1 0 obj<< /Type /Page /Parent 2 0 R /Contents {i} 0 R >>endobj\n")
    parts.append("2 0 obj<< /Type /Pages /Kids [] /Count %d >>endobj\n" % pages)
    parts.append("trailer<< /Root 2 0 R >>\n%%EOF\n")
    return "".join(parts).encode("latin-1")


def test_count_pdf_pages_one():
    assert count_pdf_pages(_minimal_pdf(1)) == 1


def test_count_pdf_pages_two():
    assert count_pdf_pages(_minimal_pdf(2)) == 2


def test_count_pdf_pages_three():
    assert count_pdf_pages(_minimal_pdf(3)) == 3


def test_count_pdf_pages_empty_raises():
    with pytest.raises(ValueError):
        count_pdf_pages(b"")
