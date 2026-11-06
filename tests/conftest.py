"""Shared pytest fixtures.

Every test gets a new in-memory database, so nothing is written to
``habits.db`` and tests cannot see each other's rows. Dates are fixed.
Using ``datetime.now()`` here would make totals and streaks depend on
the day the suite runs.
"""

from collections.abc import Iterator
from datetime import date

import pytest

from database import Database
from templates import HABIT_TEMPLATES as PREDEFINED_HABITS


# Monday 5 Jan 2026 through Sunday 1 Feb 2026 is four ISO weeks:
# 2026-W02, 2026-W03, 2026-W04 and 2026-W05.
FOUR_WEEK_START = date(2026, 1, 5)
FOUR_WEEK_END = date(2026, 2, 1)

# One timestamp on each Monday of the four-week window, plus a second
# timestamp inside week 3 so a period can contain more than one entry.
WEEK_STARTS = (
    "2026-01-05T18:00:00",
    "2026-01-12T18:00:00",
    "2026-01-19T18:00:00",
    "2026-01-26T18:00:00",
)
EXTRA_IN_WEEK_THREE = "2026-01-14T12:00:00"

# Extra days for daily habits, spread across the same four weeks.
DAILY_TIMESTAMPS = WEEK_STARTS + (
    "2026-01-06T18:00:00",
    "2026-01-13T18:00:00",
    "2026-01-20T18:00:00",
    "2026-01-27T18:00:00",
    EXTRA_IN_WEEK_THREE,
)

HABIT_CREATED_AT = "2026-01-05T08:00:00"


@pytest.fixture
def db() -> Iterator[Database]:
    """A connected in-memory database with empty tables."""
    database = Database(":memory:")
    database.create_tables()
    yield database
    database.close()


@pytest.fixture
def test_user(db: Database) -> dict:
    """One account used as the owner of the seeded habits.

    ``password_hash`` is a placeholder. Auth tests hash real passwords.
    """
    user_id = db.insert(
        "users",
        {
            "name": "Test User",
            "email": "test@example.com",
            "password_hash": "placeholder-hash",
        },
    )
    return {
        "id": user_id,
        "name": "Test User",
        "email": "test@example.com",
    }


@pytest.fixture
def seeded_habits(db: Database, test_user: dict) -> list[dict]:
    """The seven predefined habits, each with several completions.

    Daily habits are logged on nine fixed timestamps across the four
    weeks. Weekly habits are logged once per ISO week, plus one extra
    entry in week 3. Minutes differ per habit so tests can tell rows apart.
    """
    habits: list[dict] = []
    user_id = test_user["id"]

    for index, (name, periodicity) in enumerate(PREDEFINED_HABITS):
        habit_id = db.insert(
            "habits",
            {
                "user_id": user_id,
                "name": name,
                "periodicity": periodicity,
                "created_at": HABIT_CREATED_AT,
            },
        )
        timestamps = DAILY_TIMESTAMPS if periodicity == "daily" else (
            WEEK_STARTS + (EXTRA_IN_WEEK_THREE,)
        )
        completions = []
        for entry_index, timestamp in enumerate(timestamps):
            # Positive, unique minutes: habit 1 starts at 10, habit 2 at 20, ...
            minutes = (index + 1) * 10 + entry_index
            completion_id = db.insert(
                "completions",
                {
                    "habit_id": habit_id,
                    "minutes_spent": minutes,
                    "timestamp": timestamp,
                },
            )
            completions.append(
                {
                    "id": completion_id,
                    "minutes_spent": minutes,
                    "timestamp": timestamp,
                }
            )
        habits.append(
            {
                "id": habit_id,
                "user_id": user_id,
                "name": name,
                "periodicity": periodicity,
                "created_at": HABIT_CREATED_AT,
                "completions": completions,
            }
        )
    return habits
