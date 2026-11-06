"""Tests for sign-up and log-in. Passwords must never be stored as text."""

import pytest

from auth import AuthService


def test_sign_up_stores_a_hash_not_the_password(db) -> None:
    auth = AuthService(db)
    user = auth.sign_up("Ada Lovelace", "Ada@Example.com", "correct-horse")
    assert user.id is not None
    assert user.email == "ada@example.com"
    assert user.name == "Ada Lovelace"
    assert "correct-horse" not in user.password_hash
    assert "$" in user.password_hash

    stored = db.query("SELECT password_hash FROM users WHERE id = ?", (user.id,))
    assert stored[0]["password_hash"] == user.password_hash
    assert "correct-horse" not in stored[0]["password_hash"]


def test_log_in_accepts_email_in_any_case(db) -> None:
    auth = AuthService(db)
    created = auth.sign_up("Ada", "ada@example.com", "correct-horse")
    logged_in = auth.log_in("ADA@example.com", "correct-horse")
    assert logged_in.id == created.id
    assert logged_in.email == "ada@example.com"


def test_log_in_fails_with_a_wrong_password(db) -> None:
    auth = AuthService(db)
    auth.sign_up("Ada", "ada@example.com", "correct-horse")
    with pytest.raises(ValueError) as wrong_password:
        auth.log_in("ada@example.com", "wrong-horse")
    with pytest.raises(ValueError) as unknown_email:
        auth.log_in("grace@example.com", "correct-horse")
    # The same message for both, so the screen does not say which part failed.
    assert str(wrong_password.value) == str(unknown_email.value)


def test_duplicate_email_is_rejected(db) -> None:
    auth = AuthService(db)
    auth.sign_up("Ada", "ada@example.com", "correct-horse")
    with pytest.raises(ValueError):
        auth.sign_up("Ada Again", "ADA@example.com", "another-secret")


def test_empty_name_is_rejected(db) -> None:
    auth = AuthService(db)
    with pytest.raises(ValueError):
        auth.sign_up("   ", "ada@example.com", "correct-horse")
