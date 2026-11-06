"""Tests for Database: schema, parameters, constraints and cascades."""

import sqlite3
from pathlib import Path

import pytest

from database import Database
from tests.conftest import PREDEFINED_HABITS


def test_default_database_file_is_habits_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    database = Database()
    try:
        assert database.db_name == "habits.db"
        assert database.conn is not None
        assert (tmp_path / "habits.db").is_file()
    finally:
        database.close()


def test_foreign_keys_are_enabled(db: Database) -> None:
    row = db.query("PRAGMA foreign_keys")
    assert row[0][0] == 1


def test_create_tables_is_idempotent_and_builds_the_schema(db: Database) -> None:
    db.create_tables()
    names = {row["name"] for row in db.query(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    assert {"users", "habits", "completions"} <= names


def test_insert_query_and_update_round_trip(db: Database) -> None:
    user_id = db.insert(
        "users",
        {
            "name": "Ada",
            "email": "ada@example.com",
            "password_hash": "hashed",
        },
    )
    habit_id = db.insert(
        "habits",
        {
            "user_id": user_id,
            "name": "Exercise",
            "periodicity": "daily",
            "created_at": "2026-01-05T08:00:00",
        },
    )

    rows = db.query("SELECT name, is_active FROM habits WHERE id = ?", (habit_id,))
    assert len(rows) == 1
    assert rows[0]["name"] == "Exercise"
    # Omitted column uses the schema default.
    assert rows[0]["is_active"] == 1

    changed = db.update("habits", {"name": "Morning exercise"}, "id = ?", (habit_id,))
    assert changed == 1
    renamed = db.query("SELECT name FROM habits WHERE id = ?", (habit_id,))
    assert renamed[0]["name"] == "Morning exercise"


def test_update_does_not_change_other_rows(db: Database) -> None:
    first = db.insert(
        "users",
        {"name": "Ada", "email": "ada@example.com", "password_hash": "a"},
    )
    second = db.insert(
        "users",
        {"name": "Grace", "email": "grace@example.com", "password_hash": "b"},
    )
    db.update("users", {"name": "Ada Lovelace"}, "id = ?", (first,))
    other = db.query("SELECT name FROM users WHERE id = ?", (second,))
    assert other[0]["name"] == "Grace"


def test_duplicate_email_is_rejected(db: Database) -> None:
    db.insert(
        "users",
        {"name": "Ada", "email": "ada@example.com", "password_hash": "a"},
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.insert(
            "users",
            {"name": "Ada Again", "email": "ada@example.com", "password_hash": "b"},
        )


def test_invalid_periodicity_is_rejected(db: Database, test_user: dict) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.insert(
            "habits",
            {
                "user_id": test_user["id"],
                "name": "Reading",
                "periodicity": "yearly",
                "created_at": "2026-01-05T08:00:00",
            },
        )


def test_older_database_gains_monthly_habits(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            periodicity TEXT NOT NULL CHECK (periodicity IN ('daily', 'weekly')),
            created_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            minutes_spent INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO users (name, email, password_hash) VALUES ('Ada', 'ada@example.com', 'hash')"
    )
    connection.execute(
        """
        INSERT INTO habits (user_id, name, periodicity, created_at)
        VALUES (1, 'Exercise', 'daily', '2026-01-05T08:00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO completions (habit_id, minutes_spent, timestamp)
        VALUES (1, 20, '2026-01-05T10:00:00')
        """
    )
    connection.commit()
    connection.close()

    database = Database(str(path))
    try:
        database.create_tables()
        database.insert(
            "habits",
            {
                "user_id": 1,
                "name": "Budget",
                "periodicity": "monthly",
                "created_at": "2026-01-05T08:00:00",
            },
        )
        kept = database.query("SELECT minutes_spent FROM completions WHERE habit_id = 1")
        assert kept[0]["minutes_spent"] == 20
    finally:
        database.close()


def test_habit_requires_a_real_user(db: Database) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.insert(
            "habits",
            {
                "user_id": 999,
                "name": "Exercise",
                "periodicity": "daily",
                "created_at": "2026-01-05T08:00:00",
            },
        )


def test_delete_habit_removes_its_completions(db: Database, test_user: dict) -> None:
    habit_id = db.insert(
        "habits",
        {
            "user_id": test_user["id"],
            "name": "Cooking",
            "periodicity": "daily",
            "created_at": "2026-01-05T08:00:00",
        },
    )
    db.insert(
        "completions",
        {
            "habit_id": habit_id,
            "minutes_spent": 25,
            "timestamp": "2026-01-05T18:00:00",
        },
    )
    removed = db.delete("habits", "id = ?", (habit_id,))
    assert removed == 1
    left = db.query(
        "SELECT id FROM completions WHERE habit_id = ?",
        (habit_id,),
    )
    assert left == []


def test_values_are_bound_not_executed_as_sql(db: Database) -> None:
    hostile = "x'; DROP TABLE users;--"
    db.insert(
        "users",
        {"name": hostile, "email": "safe@example.com", "password_hash": "h"},
    )
    rows = db.query("SELECT name FROM users WHERE email = ?", ("safe@example.com",))
    assert rows[0]["name"] == hostile
    still_there = db.query(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    )
    assert still_there


def test_unsafe_identifier_is_rejected(db: Database) -> None:
    with pytest.raises(ValueError):
        db.insert("users; DROP TABLE users", {"name": "Ada"})


def test_empty_insert_and_update_are_rejected(db: Database) -> None:
    with pytest.raises(ValueError):
        db.insert("users", {})
    with pytest.raises(ValueError):
        db.update("users", {}, "id = ?", (1,))


def test_methods_fail_after_close() -> None:
    database = Database(":memory:")
    database.close()
    with pytest.raises(RuntimeError):
        database.query("SELECT 1")


def test_seeded_fixture_has_seven_habits_across_four_weeks(
    db: Database,
    seeded_habits: list[dict],
) -> None:
    assert [habit["name"] for habit in seeded_habits] == [
        name for name, _periodicity in PREDEFINED_HABITS
    ]
    stored = db.query("SELECT id FROM habits")
    assert len(stored) == 7

    for habit in seeded_habits:
        assert habit["created_at"] == "2026-01-05T08:00:00"
        assert len(habit["completions"]) >= 5
        timestamps = [entry["timestamp"] for entry in habit["completions"]]
        assert min(timestamps) >= "2026-01-05"
        assert max(timestamps) <= "2026-02-01T23:59:59"
        assert all(entry["minutes_spent"] > 0 for entry in habit["completions"])
