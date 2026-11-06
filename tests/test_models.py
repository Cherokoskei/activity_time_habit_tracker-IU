"""Tests for User, Habit and Completion. No database and no GUI."""

import pytest

from models import Completion, Habit, User, parse_minutes


def test_user_keeps_account_fields() -> None:
    user = User("Ada", "ada@example.com", "salt$hash", id=3)
    assert user.id == 3
    assert user.name == "Ada"
    assert user.email == "ada@example.com"
    assert user.password_hash == "salt$hash"


def test_habit_strips_name_and_periodicity() -> None:
    habit = Habit("  Exercise  ", " Daily ", "2026-01-05T08:00:00", user_id=1)
    assert habit.name == "Exercise"
    assert habit.periodicity == "daily"
    assert habit.is_active is True


def test_rename_changes_only_that_habit() -> None:
    first = Habit("Cooking", "daily", "2026-01-05T08:00:00")
    second = Habit("Cleaning", "daily", "2026-01-05T08:00:00")
    first.rename("  Meal prep  ")
    assert first.name == "Meal prep"
    assert second.name == "Cleaning"


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_habit_name_is_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        Habit(name, "daily", "2026-01-05T08:00:00")
    habit = Habit("Cooking", "daily", "2026-01-05T08:00:00")
    with pytest.raises(ValueError):
        habit.rename(name)


def test_monthly_periodicity_is_accepted() -> None:
    habit = Habit("Budget", " Monthly ", "2026-01-05T08:00:00")
    assert habit.periodicity == "monthly"


@pytest.mark.parametrize("periodicity", ["yearly", "", "hourly"])
def test_invalid_periodicity_is_rejected(periodicity: str) -> None:
    with pytest.raises(ValueError):
        Habit("Reading", periodicity, "2026-01-05T08:00:00")


def test_update_minutes_saves_a_positive_integer() -> None:
    entry = Completion(habit_id=1, minutes_spent="30", timestamp="2026-01-05T18:00:00")
    entry.update_minutes(45)
    assert entry.minutes_spent == 45


@pytest.mark.parametrize("minutes", [0, -5, "0", "abc", "", 1.5, True, False])
def test_minutes_must_be_a_positive_whole_number(minutes: object) -> None:
    with pytest.raises(ValueError):
        parse_minutes(minutes)
    entry = Completion(1, 10, "2026-01-05T18:00:00")
    with pytest.raises(ValueError):
        entry.update_minutes(minutes)
    assert entry.minutes_spent == 10
