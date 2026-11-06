"""Sign-up and log-in.

Passwords are hashed with PBKDF2 before they are stored. The database
receives the salt and the hash, never the text the user typed. A failed
log-in uses one message for an unknown email and a wrong password, so
the screen does not reveal which of the two was wrong.
"""

import hashlib
import hmac
import os

from database import Database
from models import User

# More iterations make a stolen hash slower to guess. 100 000 is a
# comfortable default for a local desktop app.
_ITERATIONS = 100_000

# Used when the email is unknown, so the failure path still does a hash
# comparison and does not return faster than a wrong password.
_DUMMY_HASH = ("00" * 16) + "$" + ("00" * 32)


class AuthService:
    """Register accounts and check passwords.

    Arguments:
        database: Open Database with the tables already created.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def sign_up(self, name: str, email: str, password: str) -> User:
        """Create an account and return the saved user.

        Arguments:
            name: Display name. Must not be empty.
            email: Compared case-insensitively and stored in lower case.
            password: Hashed before insert. Must not be empty.

        Returns:
            The new User, including its database id.

        Raises:
            ValueError: If the name, email or password is unusable, or
                the email is already registered.
        """
        clean_name = name.strip() if isinstance(name, str) else ""
        if not clean_name:
            raise ValueError("Name cannot be empty.")
        clean_email = _normalise_email(email)
        if not isinstance(password, str) or not password:
            raise ValueError("Password cannot be empty.")

        existing = self._database.query(
            "SELECT id FROM users WHERE lower(email) = ?",
            (clean_email,),
        )
        if existing:
            raise ValueError("An account with this email already exists.")

        password_hash = hash_password(password)
        user_id = self._database.insert(
            "users",
            {
                "name": clean_name,
                "email": clean_email,
                "password_hash": password_hash,
            },
        )
        return User(clean_name, clean_email, password_hash, id=user_id)

    def log_in(self, email: str, password: str) -> User:
        """Return the user when the email and password match.

        Arguments:
            email: Looked up case-insensitively.
            password: Checked against the stored hash.

        Returns:
            The matching User.

        Raises:
            ValueError: If the email is unknown or the password is wrong.
                Both cases raise the same message.
        """
        message = "Email or password is incorrect."
        try:
            clean_email = _normalise_email(email)
        except ValueError:
            # Still spend the time on a hash so this path is not a shortcut.
            verify_password(password if isinstance(password, str) else "", _DUMMY_HASH)
            raise ValueError(message) from None

        rows = self._database.query(
            "SELECT id, name, email, password_hash FROM users WHERE lower(email) = ?",
            (clean_email,),
        )
        stored_hash = rows[0]["password_hash"] if rows else _DUMMY_HASH
        password_text = password if isinstance(password, str) else ""
        if not rows or not verify_password(password_text, stored_hash):
            raise ValueError(message)

        row = rows[0]
        return User(row["name"], row["email"], row["password_hash"], id=row["id"])


def hash_password(password: str) -> str:
    """Return ``salt_hex$hash_hex`` for ``password``.

    A new random salt is used for every account, so two users who pick
    the same password do not get the same stored value.
    """
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
    )
    return f"{salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Return True when ``password`` matches the stored salt and hash.

    ``hmac.compare_digest`` compares every byte, so the check does not
    stop early and leak how much of the hash matched.
    """
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        salt = b"\x00" * 16
        expected = b"\x00" * 32
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
    )
    if len(derived) != len(expected):
        return False
    return hmac.compare_digest(derived, expected)


def _normalise_email(email: object) -> str:
    """Return a lower-case email, or reject text that is not an address."""
    if not isinstance(email, str):
        raise ValueError("Enter a valid email address.")
    cleaned = email.strip().lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
        raise ValueError("Enter a valid email address.")
    local, domain = cleaned.split("@", 1)
    if not local or "." not in domain:
        raise ValueError("Enter a valid email address.")
    return cleaned
