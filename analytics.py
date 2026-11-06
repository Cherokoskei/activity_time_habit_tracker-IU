"""Progress calculations: time in the current period, and the streak.

A daily period is one calendar date. A weekly period is an ISO week
(``date.isocalendar()``), which has its own year. Week 1 of a year can
start in December of the previous calendar year, so week numbers are
never subtracted by hand. The previous week is found by going back
seven days and reading ``isocalendar()`` again. A monthly period is one
calendar month. The previous month is the month of the last day before
the first of this month, so January steps back to December.

The reference date defaults to today. Tests pass a fixed date so the
result does not change depending on when the suite runs.
"""

from datetime import date, datetime, timedelta

from database import Database
from models import PERIODS, Habit, User


class Analytics:
    """Read completions and calculate totals and streaks.

    Arguments:
        database: Open Database. This class only reads.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def total_time(
        self,
        habit: Habit,
        period: str,
        reference: date | None = None,
    ) -> int:
        """Total minutes logged for ``habit`` in one period.

        Arguments:
            habit: Habit whose completions are summed. Needs an id.
            period: ``"daily"`` (that calendar date), ``"weekly"``
                (the ISO week that contains the reference date) or
                ``"monthly"`` (that calendar month).
            reference: The date the period is taken from. Defaults to today.

        Returns:
            Whole minutes. Zero when nothing was logged in the period.
            Several entries in the same period are added together.

        Raises:
            ValueError: If ``period`` is not daily, weekly or monthly,
                or the habit has not been saved.
        """
        period_name = _clean_period(period)
        ref = _as_date(reference)
        ref_key = _period_key(ref, period_name)
        total = 0
        for row in self._completion_rows(habit):
            logged = _logged_date(row["timestamp"])
            if _period_key(logged, period_name) == ref_key:
                total += int(row["minutes_spent"])
        return total

    def streak(self, habit: Habit, reference: date | None = None) -> int:
        """Consecutive successful periods ending at the reference period.

        Daily habits count days. Weekly habits count ISO weeks. Monthly
        habits count calendar months. The current period has to contain
        at least one completion; if it was missed, the streak is 0. A
        gap further back stops the count as well. Two completions in
        one period count as a single period.

        Arguments:
            habit: Habit to measure. Periodicity selects days or weeks.
            reference: End of the streak. Defaults to today.

        Returns:
            How many periods are in the streak.

        Raises:
            ValueError: If the habit has not been saved.
        """
        period_name = _clean_period(habit.periodicity)
        ref = _as_date(reference)
        ref_key = _period_key(ref, period_name)
        # Ignore periods after the reference. A completion later in the
        # same week still counts, because the key is the whole ISO week.
        keys = set()
        for row in self._completion_rows(habit):
            key = _period_key(_logged_date(row["timestamp"]), period_name)
            if key <= ref_key:
                keys.add(key)

        cursor = ref
        count = 0
        while _period_key(cursor, period_name) in keys:
            count += 1
            cursor = _previous_period(cursor, period_name)
        return count

    def summary(self, user: User, reference: date | None = None) -> list[dict]:
        """Progress for every habit belonging to ``user``.

        Arguments:
            user: Account whose habits are listed. Needs an id.
            reference: Date treated as "today" for the totals and streaks.

        Returns:
            One dictionary per habit, in id order, with ``habit_id``,
            ``name``, ``periodicity``, ``total_time`` (current period)
            and ``streak``. The current period follows the habit:
            today for a daily habit, this ISO week for a weekly habit,
            this calendar month for a monthly habit.

        Raises:
            ValueError: If the user has not been saved.
        """
        report = []
        for habit in self._habits_for(user):
            report.append(
                {
                    "habit_id": habit.id,
                    "name": habit.name,
                    "periodicity": habit.periodicity,
                    "total_time": self.total_time(habit, habit.periodicity, reference),
                    "streak": self.streak(habit, reference),
                }
            )
        return report

    def overview(self, user: User, reference: date | None = None) -> list[dict]:
        """Minutes for every habit on the same three periods.

        ``summary`` follows each habit's own period, so a daily habit
        shows today while a monthly habit shows the whole month. This
        report uses today, this ISO week and this calendar month for
        every habit, which is what a single progress table needs.

        Arguments:
            user: Account whose habits are listed. Needs an id.
            reference: Date treated as today. Defaults to today.

        Returns:
            One dictionary per habit, in id order, with ``habit_id``,
            ``name``, ``periodicity``, ``today``, ``week``, ``month``
            and ``streak``.

        Raises:
            ValueError: If the user has not been saved.
        """
        report = []
        for habit in self._habits_for(user):
            report.append(
                {
                    "habit_id": habit.id,
                    "name": habit.name,
                    "periodicity": habit.periodicity,
                    "today": self.total_time(habit, "daily", reference),
                    "week": self.total_time(habit, "weekly", reference),
                    "month": self.total_time(habit, "monthly", reference),
                    "streak": self.streak(habit, reference),
                }
            )
        return report

    def weekly_minutes(self, user: User, reference: date | None = None) -> list[dict]:
        """Minutes each habit logged in the ISO week of ``reference``.

        Daily, weekly and monthly habits are all measured over that same
        week. ``summary`` still uses each habit's own period (today, this
        week, or this month). The chart needs one shared week so the bars
        can be compared.

        Arguments:
            user: Account whose habits are included. Needs an id.
            reference: Any date inside the week. Defaults to today.

        Returns:
            One dictionary per habit, in id order, with ``habit_id``,
            ``name``, ``periodicity`` and ``minutes``. A habit with no
            entries this week is included with zero minutes.

        Raises:
            ValueError: If the user has not been saved.
        """
        return [
            {
                "habit_id": habit.id,
                "name": habit.name,
                "periodicity": habit.periodicity,
                "minutes": self.total_time(habit, "weekly", reference),
            }
            for habit in self._habits_for(user)
        ]

    def lacking_this_week(self, user: User, reference: date | None = None) -> list[dict]:
        """Habits with no minutes in the ISO week of ``reference``.

        A habit counts as lacking for the week when nothing was logged
        between Monday and Sunday, whatever its own period is. A monthly
        habit that was logged in the month but not in this week is still
        listed here.

        Arguments:
            user: Account whose habits are checked. Needs an id.
            reference: Any date inside the week. Defaults to today.

        Returns:
            The ``weekly_minutes`` rows whose minutes are zero, in id order.

        Raises:
            ValueError: If the user has not been saved.
        """
        return [row for row in self.weekly_minutes(user, reference) if row["minutes"] == 0]

    def _habits_for(self, user: User) -> list[Habit]:
        """Active habits owned by ``user``, oldest first."""
        if user.id is None:
            raise ValueError("User has not been saved.")
        rows = self._database.query(
            """
            SELECT id, user_id, name, periodicity, created_at, is_active
            FROM habits
            WHERE user_id = ? AND is_active = 1
            ORDER BY id
            """,
            (user.id,),
        )
        return [Habit.from_row(row) for row in rows]

    def _completion_rows(self, habit: Habit) -> list:
        """Completions for one saved habit."""
        if habit.id is None:
            raise ValueError("Habit has not been saved.")
        return self._database.query(
            """
            SELECT minutes_spent, timestamp
            FROM completions
            WHERE habit_id = ?
            ORDER BY timestamp
            """,
            (habit.id,),
        )


def _as_date(reference: date | None) -> date:
    """Use today when the caller does not pass a date.

    ``datetime`` is a subclass of ``date``, so it is checked first and
    reduced to a calendar date. The time of day does not change the period.
    """
    if reference is None:
        return date.today()
    if isinstance(reference, datetime):
        return reference.date()
    if isinstance(reference, date):
        return reference
    raise ValueError("Reference must be a date.")


def _clean_period(period: object) -> str:
    """Return ``daily``, ``weekly`` or ``monthly``."""
    if not isinstance(period, str):
        raise ValueError("Period must be 'daily', 'weekly' or 'monthly'.")
    cleaned = period.strip().lower()
    if cleaned not in PERIODS:
        raise ValueError("Period must be 'daily', 'weekly' or 'monthly'.")
    return cleaned


def _logged_date(timestamp: str) -> date:
    """Calendar date of an ISO timestamp stored on a completion."""
    return datetime.fromisoformat(timestamp).date()


def _period_key(day: date, period: str) -> tuple[int, ...]:
    """Identity of the period that contains ``day``.

    Weekly keys use the ISO year, not the calendar year. Otherwise the
    last days of December would be grouped with the wrong week.
    """
    if period == "daily":
        return (day.toordinal(),)
    if period == "monthly":
        return (day.year, day.month)
    iso = day.isocalendar()
    return (iso.year, iso.week)


def _previous_period(day: date, period: str) -> date:
    """The date one period before ``day``, staying inside that period's key.

    A month is not a fixed number of days. Subtracting 30 days from 31
    March lands in March again, so the previous month is found from the
    day before the first of this month.
    """
    if period == "daily":
        return day - timedelta(days=1)
    if period == "weekly":
        return day - timedelta(days=7)
    return day.replace(day=1) - timedelta(days=1)
