"""Tests for the chart numbers, the CSV export, and the small UI helpers.

The chart test checks the drawn bar heights. It does not open a window.
"""

import csv
from datetime import date

import pytest
from matplotlib.figure import Figure

from charts import draw_weekly_bars
from gui.app import window_origin
from gui.login import confirm_password
from models import User
from tracker import HabitTracker


def test_weekly_minutes_use_one_shared_week(db, test_user) -> None:
    tracker = HabitTracker(db)
    exercise = tracker.create_habit(
        test_user["id"], "Exercise", "daily", created_at="2026-01-01T08:00:00"
    )
    shopping = tracker.create_habit(
        test_user["id"], "Shopping", "weekly", created_at="2026-01-01T08:00:00"
    )
    # 5 and 6 Jan 2026 are the same ISO week. 12 Jan is the next week.
    tracker.log_completion(test_user["id"], exercise.id, 20, timestamp="2026-01-05T10:00:00")
    tracker.log_completion(test_user["id"], exercise.id, 15, timestamp="2026-01-06T10:00:00")
    tracker.log_completion(test_user["id"], exercise.id, 99, timestamp="2026-01-12T10:00:00")
    tracker.log_completion(test_user["id"], shopping.id, 40, timestamp="2026-01-06T12:00:00")

    user = User(test_user["name"], test_user["email"], "hash", id=test_user["id"])
    rows = {row["name"]: row for row in tracker.weekly_minutes(user, date(2026, 1, 6))}
    assert rows["Exercise"]["minutes"] == 35
    assert rows["Exercise"]["periodicity"] == "daily"
    assert rows["Shopping"]["minutes"] == 40
    # A habit with nothing in this week is still listed, at zero.
    quiet = tracker.create_habit(
        test_user["id"], "Sleeping", "daily", created_at="2026-01-01T08:00:00"
    )
    names = [row["name"] for row in tracker.weekly_minutes(user, date(2026, 1, 6))]
    assert "Sleeping" in names
    assert quiet.id is not None


def test_weekly_minutes_ignore_another_users_habits(db) -> None:
    tracker = HabitTracker(db)
    ada = db.insert(
        "users",
        {"name": "Ada", "email": "ada@example.com", "password_hash": "a"},
    )
    grace = db.insert(
        "users",
        {"name": "Grace", "email": "grace@example.com", "password_hash": "b"},
    )
    habit = tracker.create_habit(ada, "Exercise", "daily", created_at="2026-01-01T08:00:00")
    tracker.log_completion(ada, habit.id, 30, timestamp="2026-01-05T10:00:00")
    grace_user = User("Grace", "grace@example.com", "b", id=grace)
    assert tracker.weekly_minutes(grace_user, date(2026, 1, 5)) == []


def test_export_csv_contains_only_that_users_rows(db, tmp_path) -> None:
    tracker = HabitTracker(db)
    ada = db.insert(
        "users",
        {"name": "Ada", "email": "ada@example.com", "password_hash": "secret-hash"},
    )
    grace = db.insert(
        "users",
        {"name": "Grace", "email": "grace@example.com", "password_hash": "other-hash"},
    )
    cooking = tracker.create_habit(ada, "Cooking", "daily", created_at="2026-01-05T08:00:00")
    tracker.log_completion(ada, cooking.id, 25, timestamp="2026-01-05T18:00:00")
    tracker.log_completion(ada, cooking.id, 10, timestamp="2026-01-06T18:00:00")
    empty = tracker.create_habit(ada, "Cleaning", "daily", created_at="2026-01-05T08:00:00")
    hidden = tracker.create_habit(grace, "Exercise", "daily", created_at="2026-01-05T08:00:00")
    tracker.log_completion(grace, hidden.id, 80, timestamp="2026-01-05T18:00:00")

    destination = tmp_path / "habits.csv"
    user = User("Ada", "ada@example.com", "secret-hash", id=ada)
    written = tracker.export_csv(user, str(destination))
    assert written == 3

    with destination.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["habit_name"] for row in rows] == ["Cooking", "Cooking", "Cleaning"]
    assert rows[0]["minutes_spent"] == "25"
    assert rows[0]["recorded_at"] == "2026-01-05T18:00:00"
    assert rows[2]["minutes_spent"] == ""
    text = destination.read_text(encoding="utf-8")
    assert "secret-hash" not in text
    assert "Exercise" not in text
    assert empty.name == "Cleaning"


def test_chart_bar_height_matches_the_minutes() -> None:
    figure = Figure()
    draw_weekly_bars(
        figure,
        [
            {"name": "Exercise", "periodicity": "daily", "minutes": 35},
            {"name": "Shopping", "periodicity": "weekly", "minutes": 40},
        ],
    )
    bars = figure.axes[0].patches
    assert [bar.get_height() for bar in bars] == [35, 40]
    assert bars[0].get_facecolor() != bars[1].get_facecolor()


def test_chart_without_habits_draws_no_bars() -> None:
    figure = Figure()
    draw_weekly_bars(figure, [])
    assert len(figure.axes[0].patches) == 0


def test_confirm_password_rejects_a_mismatch() -> None:
    confirm_password("correct-horse", "correct-horse")
    with pytest.raises(ValueError):
        confirm_password("correct-horse", "wrong-horse")


def test_window_origin_is_centered_and_never_negative() -> None:
    assert window_origin(1000, 800, 760, 560) == (120, 120)
    assert window_origin(400, 300, 760, 560) == (0, 0)
