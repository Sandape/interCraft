"""Unit tests for auth.schemas — password strength, email validation."""
import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import RegisterInput, _validate_password_strength


def test_password_min_length():
    with pytest.raises(ValueError, match="at least 8"):
        _validate_password_strength("Ab1")


def test_password_missing_digit():
    with pytest.raises(ValueError, match="digit"):
        _validate_password_strength("OnlyLetters")


def test_password_missing_letter():
    with pytest.raises(ValueError, match="letter"):
        _validate_password_strength("12345678")


def test_password_ok():
    assert _validate_password_strength("P@ssw0rd123") == "P@ssw0rd123"


def test_register_input_email_normalized():
    payload = RegisterInput(email="USER@Example.COM", password="P@ssw0rd123")
    assert payload.email == "user@example.com"


def test_register_input_password_rejected_weak():
    with pytest.raises(ValidationError):
        RegisterInput(email="a@b.com", password="abcdefgh")  # no digit
