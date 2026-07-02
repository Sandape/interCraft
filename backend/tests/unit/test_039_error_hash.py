"""REQ-039 US5 — error_hash normalization + SHA256 prefix tests (FR-021 / FR-022).

Coverage matrix (per FR-022 Option B):

- rule 1: lowercase
- rule 2: strip leading / trailing whitespace
- rule 3: collapse internal whitespace to a single space
- rule 4: strip UUID
- rule 5: strip hex blob (>=16 hex)
- rule 6: strip digit sequences >=12
- rule 7: preserve ordinary numbers (1-11 digits) and all words

Plus shape tests for the SHA256 prefix (16 hex chars).
"""
from __future__ import annotations

import string

import pytest

from app.observability.error_hash import (
    compute_error_hash,
    normalize_error_message,
)


# ---------------------------------------------------------------------------
# Shape (FR-021)
# ---------------------------------------------------------------------------


class TestComputeErrorHashShape:
    def test_returns_16_hex_chars(self) -> None:
        h = compute_error_hash("anything")
        assert len(h) == 16
        assert all(c in string.hexdigits.lower() for c in h)

    def test_empty_message_returns_16_hex(self) -> None:
        h = compute_error_hash("")
        assert len(h) == 16

    def test_deterministic(self) -> None:
        assert compute_error_hash("retry 3") == compute_error_hash("retry 3")

    def test_different_message_different_hash(self) -> None:
        assert compute_error_hash("a") != compute_error_hash("b")


# ---------------------------------------------------------------------------
# Normalization rules (FR-022)
# ---------------------------------------------------------------------------


class TestNormalizationRule1Lowercase:
    def test_uppercase_lowered(self) -> None:
        assert normalize_error_message("RETRY 3") == "retry 3"

    def test_mixed_case_lowered(self) -> None:
        assert normalize_error_message("Failed To Connect") == "failed to connect"


class TestNormalizationRule2Strip:
    def test_leading_trailing_whitespace_stripped(self) -> None:
        assert normalize_error_message("   retry 3   ") == "retry 3"

    def test_tabs_and_newlines_stripped(self) -> None:
        assert normalize_error_message("\t\nretry 3\n\t") == "retry 3"


class TestNormalizationRule3Collapse:
    def test_internal_whitespace_collapsed(self) -> None:
        assert normalize_error_message("retry   3  times") == "retry 3 times"

    def test_mixed_whitespace_collapsed(self) -> None:
        assert normalize_error_message("retry\t3\ntimes") == "retry 3 times"


class TestNormalizationRule4StripUUID:
    def test_uuid_stripped(self) -> None:
        msg = "key 12345678-1234-1234-1234-123456789012 missing"
        assert normalize_error_message(msg) == "key missing"

    def test_uppercase_uuid_stripped(self) -> None:
        msg = "key ABCDEF12-3456-7890-ABCD-EF1234567890 missing"
        assert normalize_error_message(msg) == "key missing"

    def test_uuid_in_text_stripped(self) -> None:
        msg = "trace 12345678-1234-5678-9012-123456789012 failed"
        assert normalize_error_message(msg) == "trace failed"


class TestNormalizationRule5StripHexBlob:
    def test_hex_blob_stripped(self) -> None:
        msg = "leaked secret abcdef0123456789abcdef0123456789 now"
        assert normalize_error_message(msg) == "leaked secret now"

    def test_16_char_hex_stripped(self) -> None:
        msg = "value abcdef0123456789 was"
        assert normalize_error_message(msg) == "value was"

    def test_short_hex_preserved(self) -> None:
        # 15 chars < 16 threshold — not stripped.
        msg = "value abcdef012345678 was"
        assert normalize_error_message(msg) == "value abcdef012345678 was"


class TestNormalizationRule6StripLongDigits:
    def test_long_digit_seq_stripped(self) -> None:
        msg = "leaked 1234567890123456 now"
        assert normalize_error_message(msg) == "leaked now"

    def test_12_digit_threshold(self) -> None:
        msg = "leaked 123456789012 now"
        assert normalize_error_message(msg) == "leaked now"

    def test_11_digit_preserved(self) -> None:
        # 11 digits is the upper boundary — must be preserved.
        msg = "leaked 12345678901 now"
        assert normalize_error_message(msg) == "leaked 12345678901 now"


class TestNormalizationRule7PreserveOrdinary:
    def test_small_number_preserved(self) -> None:
        assert normalize_error_message("retry 3 times") == "retry 3 times"

    def test_two_digit_number_preserved(self) -> None:
        assert normalize_error_message("retry 42 times") == "retry 42 times"

    def test_eight_digit_number_preserved(self) -> None:
        assert normalize_error_message("phone 12345678") == "phone 12345678"

    def test_eleven_digit_number_preserved(self) -> None:
        # 11 digits — preserved (just under the 12-digit threshold).
        assert (
            normalize_error_message("id 12345678901 was bad")
            == "id 12345678901 was bad"
        )

    def test_words_preserved(self) -> None:
        assert normalize_error_message("Connection Refused") == "connection refused"

    def test_unicode_words_preserved(self) -> None:
        assert normalize_error_message("错误: 连接失败") == "错误: 连接失败"


# ---------------------------------------------------------------------------
# Bucket stability (FR-021 / SC-005)
# ---------------------------------------------------------------------------


class TestBucketStability:
    def test_same_message_different_uuid_same_bucket(self) -> None:
        a = "key 12345678-1234-1234-1234-123456789012 missing"
        b = "key abcdef12-3456-7890-abcd-ef1234567890 missing"
        assert compute_error_hash(a) == compute_error_hash(b)

    def test_different_ordinary_numbers_different_buckets(self) -> None:
        a = compute_error_hash("retry 3 times")
        b = compute_error_hash("retry 5 times")
        assert a != b

    def test_lowercase_stability(self) -> None:
        a = compute_error_hash("Retry 3 times")
        b = compute_error_hash("retry 3 times")
        assert a == b

    def test_whitespace_stability(self) -> None:
        a = compute_error_hash("  retry   3   times  ")
        b = compute_error_hash("retry 3 times")
        assert a == b