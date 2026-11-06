"""Tests for daily and weekly totals, streaks and the dashboard summary.

Every date is fixed. The reference date stands in for "today".
"""

from datetime import date

from models import User
from tracker import HabitTracker

# ISO week 2026-W01 is Monday 29 Dec 2025 through Sunday 4 Jan 2026.
# The dates sit on either side of the calendar year on purpose.
WEEK_ONE_START = "2025-12-29T18:00:00"
WEEK_ONE_INSIDE_JANUARY = "2026-01-03T18:00:00"
PREVIOUS_ISO_WEEK = "2025-12-22T18:00:00"
WEEK_TWO = "2026-01-05T18:00:00"


def _habit(db, user_id, name, periodicity):
    tracker = HabitTracker(db)
    return tracker, tracker.create_habit(
        user_id,
        name,
        periodicity,
        created_at="2025-12-01T08:00:00",
    )


def test_daily_and_weekly_totals(db, test_user) -> None:
    tracker, habit = _habit(db, test_user["id"], "Exercise", "daily")
    tracker.log_completion(test_user["id"], habit.id, 20, timestamp="2026-01-05T10:00:00")
    tracker.log_completion(test_user["id"], habit.id, 15, timestamp="2026-01-05T19:00:00")
    tracker.log_completion(test_user["id"], habit.id, 40, timestamp="2026-01-06T19:00:00")

    analytics = tracker.analytics
    monday = date(2026, 1, 5)
    assert analytics.total_time(habit, "daily", monday) == 35
    assert analytics.total_time(habit, "daily", date(2026, 1, 6)) == 40
    # 5 Jan 2026 is a Monday, so the weekly total is that ISO week only.
    assert analytics.total_time(habit, "weekly", monday) == 75


def test_weekly_total_includes_both_sides_of_the_new_year(db, test_user) -> None:
    tracker, habit = _habit(db, test_user["id"], "Shopping", "weekly")
    tracker.log_completion(test_user["id"], habit.id, 30, timestamp=WEEK_ONE_START)
    tracker.log_completion(
        test_user["id"], habit.id, 20, timestamp=WEEK_ONE_INSIDE_JANUARY
    )
    tracker.log_completion(test_user["id"], habit.id, 100, timestamp=WEEK_TWO)

    total = tracker.analytics.total_time(habit, "weekly", date(2026, 1, 3))
    assert total == 50


def test_streak_resets_after_a_missed_day(db, test_user) -> None:
    tracker, habit = _habit(db, test_user["id"], "Cooking", "daily")
    for stamp, minutes in (
        ("2026-01-01T18:00:00", 10),
        ("2026-01-02T18:00:00", 10),
        ("2026-01-03T18:00:00", 10),
        # 4 Jan is missed.
        ("2026-01-05T18:00:00", 10),
        ("2026-01-05T20:00:00", 5),
    ):
        tracker.log_completion(test_user["id"], habit.id, minutes, timestamp=stamp)

    analytics = tracker.analytics
    # Two logs on 5 Jan still count as one day, and the gap on 4 Jan stops the count.
    assert analytics.streak(habit, date(2026, 1, 5)) == 1
    assert analytics.streak(habit, date(2026, 1, 3)) == 3
    # The current day was missed, so the current streak is 0.
    assert analytics.streak(habit, date(2026, 1, 4)) == 0


def test_weekly_streak_crosses_the_year_boundary(db, test_user) -> None:
    tracker, habit = _habit(db, test_user["id"], "Part-time job", "weekly")
    tracker.log_completion(test_user["id"], habit.id, 120, timestamp=PREVIOUS_ISO_WEEK)
    tracker.log_completion(test_user["id"], habit.id, 120, timestamp=WEEK_ONE_START)
    tracker.log_completion(test_user["id"], habit.id, 120, timestamp=WEEK_TWO)
    assert tracker.analytics.streak(habit, date(2026, 1, 5)) == 3


def test_weekly_streak_resets_when_a_week_is_missed(db, test_user) -> None:
    tracker, habit = _habit(db, test_user["id"], "Shopping", "weekly")
    tracker.log_completion(test_user["id"], habit.id, 40, timestamp=PREVIOUS_ISO_WEEK)
    # 2026-W01 is missed.
    tracker.log_completion(test_user["id"], habit.id, 40, timestamp=WEEK_TWO)
    assert tracker.analytics.streak(habit, date(2026, 1, 5)) == 1


def test_summary_lists_each_habit(db, test_user) -> None:
    tracker, study = _habit(db, test_user["id"], "IU study time", "daily")
    shopping = tracker.create_habit(
        test_user["id"],
        "Shopping",
        "weekly",
        created_at="2025-12-01T08:00:00",
    )
    tracker.log_completion(
        test_user["id"], study.id, 50, timestamp="2026-01-05T18:00:00"
    )
    tracker.log_completion(
        test_user["id"], shopping.id, 80, timestamp="2026-01-06T12:00:00"
    )
    user = User(test_user["name"], test_user["email"], "hash", id=test_user["id"])
    rows = tracker.summary(user, reference=date(2026, 1, 6))
    by_name = {row["name"]: row for row in rows}
    assert by_name["IU study time"]["periodicity"] == "daily"
    assert by_name["IU study time"]["total_time"] == 0
    assert by_name["IU study time"]["streak"] == 0
    assert by_name["Shopping"]["total_time"] == 80
    assert by_name["Shopping"]["streak"] == 1


def test_monthly_total_stays_inside_the_calendar_month(db, test_user) -> None:
    tracker, habit = _habit(db, test_user["id"], "Budget", "monthly")
    tracker.log_completion(test_user["id"], habit.id, 20, timestamp="2025-12-31T18:00:00")
    tracker.log_completion(test_user["id"], habit.id, 30, timestamp="2026-01-02T18:00:00")
    tracker.log_completion(test_user["id"], habit.id, 15, timestamp="2026-01-20T18:00:00")
    tracker.log_completion(test_user["id"], habit.id, 40, timestamp="2026-02-01T18:00:00")

    analytics = tracker.analytics
    assert analytics.total_time(habit, "monthly", date(2026, 1, 15)) == 45
    assert analytics.total_time(habit, "monthly", date(2025, 12, 31)) == 20
    # January's minutes are not part of the February total.
    assert analytics.total_time(habit, "monthly", date(2026, 2, 1)) == 40


def test_monthly_streak_steps_back_one_calendar_month(db, test_user) -> None:
    tracker, habit = _habit(db, test_user["id"], "Budget", "monthly")
    tracker.log_completion(test_user["id"], habit.id, 10, timestamp="2025-11-15T18:00:00")
    tracker.log_completion(test_user["id"], habit.id, 10, timestamp="2025-12-01T18:00:00")
    # January is missed.
    tracker.log_completion(test_user["id"], habit.id, 10, timestamp="2026-02-10T18:00:00")
    tracker.log_completion(test_user["id"], habit.id, 10, timestamp="2026-03-31T18:00:00")

    analytics = tracker.analytics
    assert analytics.streak(habit, date(2026, 3, 31)) == 2
    assert analytics.streak(habit, date(2025, 12, 20)) == 2
    # The current month was missed, so the streak is 0.
    assert analytics.streak(habit, date(2026, 1, 10)) == 0


def test_overview_measures_every_habit_on_the_same_periods(db, test_user) -> None:
    tracker, exercise = _habit(db, test_user["id"], "Exercise", "daily")
    budget = tracker.create_habit(
        test_user["id"], "Budget", "monthly", created_at="2025-12-01T08:00:00"
    )
    tracker.log_completion(test_user["id"], exercise.id, 10, timestamp="2026-01-02T10:00:00")
    tracker.log_completion(test_user["id"], exercise.id, 20, timestamp="2026-01-06T10:00:00")
    tracker.log_completion(test_user["id"], budget.id, 30, timestamp="2026-01-02T10:00:00")

    user = User(test_user["name"], test_user["email"], "hash", id=test_user["id"])
    rows = {row["name"]: row for row in tracker.overview(user, date(2026, 1, 6))}
    # 2 Jan and 6 Jan are the same month and different ISO weeks.
    assert rows["Exercise"]["today"] == 20
    assert rows["Exercise"]["week"] == 20
    assert rows["Exercise"]["month"] == 30
    assert rows["Budget"]["today"] == 0
    assert rows["Budget"]["week"] == 0
    assert rows["Budget"]["month"] == 30


def test_lacking_this_week_lists_habits_with_no_minutes(db, test_user) -> None:
    tracker, exercise = _habit(db, test_user["id"], "Exercise", "daily")
    budget = tracker.create_habit(
        test_user["id"], "Budget", "monthly", created_at="2025-12-01T08:00:00"
    )
    tracker.log_completion(
        test_user["id"], exercise.id, 20, timestamp="2026-01-06T10:00:00"
    )
    # Logged in January, but not in the week of 6 Jan 2026 (5–11 Jan).
    tracker.log_completion(
        test_user["id"], budget.id, 30, timestamp="2026-01-02T10:00:00"
    )
    user = User(test_user["name"], test_user["email"], "hash", id=test_user["id"])
    lacking = tracker.lacking_this_week(user, date(2026, 1, 6))
    assert [row["name"] for row in lacking] == ["Budget"]
