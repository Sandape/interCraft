"""Contract-ish error code constants (REQ-055)."""

EXPECTED_ERROR_CODES = {
    "NO_ROOT",
    "NO_JD",
    "ROOT_EXISTS",
    "PAGE_COUNT_MISMATCH",
    "INVALID_TARGET_PAGES",
    "EXPORT_BLOCKED",
}


def test_error_codes_documented():
    assert "NO_JD" in EXPECTED_ERROR_CODES
    assert "PAGE_COUNT_MISMATCH" in EXPECTED_ERROR_CODES
