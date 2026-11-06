"""Tests for creating, logging, editing and deleting habits."""

from datetime import datetime

import pytest

from tracker import HabitTracker


def test_habit_is_stamped_automatically(db, test_user) -> None:
    tracker = HabitTracker(db)
    before = datetime.now().replace(microsecond=0)
    habit = tracker.create_habit(test_user["id"], "Exercise", "daily")
    after = datetime.now()
    stamped = datetime.fromisoformat(habit.created_at)
    assert before <= stamped <= after
    stored = db.query("SELECT created_at FROM habits WHERE id = ?", (habit.id,))
    assert stored[0]["created_at"] == habit.created_at


def test_time_update_is_saved(db, test_user) -> None:
    tracker = HabitTracker(db)
    habit = tracker.create_habit(
        test_user["id"],
        "Cooking",
        "daily",
        created_at="2026-01-05T08:00:00",
    )
    entry = tracker.log_completion(
        test_user["id"],
        habit.id,
        "30",
        timestamp="2026-01-05T18:00:00",
    )
    tracker.edit_habit(
        test_user["id"],
        habit.id,
        completion_id=entry.id,
        minutes=45,
    )
    stored = db.query(
        "SELECT minutes_spent FROM completions WHERE id = ?",
        (entry.id,),
    )
    assert stored[0]["minutes_spent"] == 45


def test_logging_twice_in_one_period_keeps_both_entries(db, test_user) -> None:
    tracker = HabitTracker(db)
    habit = tracker.create_habit(
        test_user["id"],
        "Exercise",
        "daily",
        created_at="2026-01-05T08:00:00",
    )
    tracker.log_completion(
        test_user["id"], habit.id, 20, timestamp="2026-01-05T10:00:00"
    )
    tracker.log_completion(
        test_user["id"], habit.id, 15, timestamp="2026-01-05T19:00:00"
    )
    entries = tracker.get_completions(test_user["id"], habit.id)
    assert [entry.minutes_spent for entry in entries] == [20, 15]


def test_edit_and_delete_affect_only_the_chosen_habit(db, test_user) -> None:
    tracker = HabitTracker(db)
    cooking = tracker.create_habit(
        test_user["id"], "Cooking", "daily", created_at="2026-01-05T08:00:00"
    )
    cleaning = tracker.create_habit(
        test_user["id"], "Cleaning", "daily", created_at="2026-01-05T08:00:00"
    )
    cooking_entry = tracker.log_completion(
        test_user["id"], cooking.id, 25, timestamp="2026-01-05T18:00:00"
    )
    cleaning_entry = tracker.log_completion(
        test_user["id"], cleaning.id, 40, timestamp="2026-01-05T18:00:00"
    )

    tracker.edit_habit(test_user["id"], cooking.id, name="Meal prep")
    tracker.edit_habit(
        test_user["id"],
        cooking.id,
        completion_id=cooking_entry.id,
        minutes=50,
    )

    names = {habit.name for habit in tracker.get_habits(test_user["id"])}
    assert names == {"Meal prep", "Cleaning"}
    untouched = db.query(
        "SELECT minutes_spent FROM completions WHERE id = ?",
        (cleaning_entry.id,),
    )
    assert untouched[0]["minutes_spent"] == 40

    tracker.delete_habit(test_user["id"], cooking.id)
    remaining = tracker.get_habits(test_user["id"])
    assert [habit.name for habit in remaining] == ["Cleaning"]
    cooking_rows = db.query(
        "SELECT id FROM completions WHERE habit_id = ?",
        (cooking.id,),
    )
    cleaning_rows = db.query(
        "SELECT id FROM completions WHERE habit_id = ?",
        (cleaning.id,),
    )
    assert cooking_rows == []
    assert len(cleaning_rows) == 1


def test_deleting_a_habit_removes_its_completions(db, test_user) -> None:
    tracker = HabitTracker(db)
    habit = tracker.create_habit(
        test_user["id"], "Shopping", "weekly", created_at="2026-01-05T08:00:00"
    )
    tracker.log_completion(
        test_user["id"], habit.id, 60, timestamp="2026-01-05T12:00:00"
    )
    tracker.delete_habit(test_user["id"], habit.id)
    left = db.query("SELECT id FROM completions WHERE habit_id = ?", (habit.id,))
    assert left == []
    assert tracker.get_habits(test_user["id"]) == []


def test_invalid_periodicity_is_rejected(db, test_user) -> None:
    tracker = HabitTracker(db)
    with pytest.raises(ValueError):
        tracker.create_habit(test_user["id"], "Reading", "yearly")


def test_user_cannot_change_another_users_habit(db) -> None:
    tracker = HabitTracker(db)
    ada = db.insert(
        "users",
        {"name": "Ada", "email": "ada@example.com", "password_hash": "a"},
    )
    grace = db.insert(
        "users",
        {"name": "Grace", "email": "grace@example.com", "password_hash": "b"},
    )
    habit = tracker.create_habit(ada, "Exercise", "daily", created_at="2026-01-05T08:00:00")
    entry = tracker.log_completion(
        ada, habit.id, 30, timestamp="2026-01-05T18:00:00"
    )
    with pytest.raises(ValueError):
        tracker.edit_habit(grace, habit.id, name="Stolen")
    with pytest.raises(ValueError):
        tracker.log_completion(grace, habit.id, 10, timestamp="2026-01-06T18:00:00")
    with pytest.raises(ValueError):
        tracker.delete_habit(grace, habit.id)
    assert [item.name for item in tracker.get_habits(grace)] == []
    assert [item.name for item in tracker.get_habits(ada)] == ["Exercise"]
    stored = db.query(
        "SELECT minutes_spent FROM completions WHERE id = ?",
        (entry.id,),
    )
    assert stored[0]["minutes_spent"] == 30


def test_completion_from_another_habit_cannot_be_edited(db, test_user) -> None:
    tracker = HabitTracker(db)
    first = tracker.create_habit(
        test_user["id"], "Cooking", "daily", created_at="2026-01-05T08:00:00"
    )
    second = tracker.create_habit(
        test_user["id"], "Cleaning", "daily", created_at="2026-01-05T08:00:00"
    )
    other = tracker.log_completion(
        test_user["id"], second.id, 15, timestamp="2026-01-05T18:00:00"
    )
    with pytest.raises(ValueError):
        tracker.edit_habit(
            test_user["id"],
            first.id,
            completion_id=other.id,
            minutes=90,
        )
    stored = db.query(
        "SELECT minutes_spent FROM completions WHERE id = ?",
        (other.id,),
    )
    assert stored[0]["minutes_spent"] == 15
