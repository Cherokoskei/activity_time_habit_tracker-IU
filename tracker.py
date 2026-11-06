"""Create, edit, delete and log habits for one user at a time.

The GUI calls this class and does not write SQL. Every change checks
the user id, so one account cannot read or edit another account's habits.
"""

import csv
from datetime import date, datetime

from analytics import Analytics
from database import Database
from models import Completion, Habit, User, parse_minutes


class HabitTracker:
    """The operations the dashboard needs.

    Arguments:
        database: Open Database with the tables already created.
    """

    def __init__(self, database: Database) -> None:
        self._database = database
        # The GUI asks the tracker for the progress summary. Analytics
        # stays behind this class, which matches the class diagram.
        self.analytics = Analytics(database)

    def create_habit(
        self,
        user_id: int,
        name: str,
        periodicity: str,
        created_at: str | None = None,
    ) -> Habit:
        """Save a new habit and stamp it with the current date and time.

        Arguments:
            user_id: Owner. The habit is visible only to this account.
            name: Label. Must not be empty.
            periodicity: ``"daily"``, ``"weekly"`` or ``"monthly"``.
            created_at: ISO timestamp. Leave this empty in the app so
                the stamp is taken from the clock. Tests pass a fixed
                value. It is not a default argument, because defaults
                are filled in once, when the function is defined, and
                every habit would then share one timestamp.

        Returns:
            The saved Habit, including its new id.

        Raises:
            ValueError: If the name, periodicity or user is not valid.
        """
        self._require_user(user_id)
        if created_at is None:
            created_at = datetime.now().isoformat(timespec="seconds")
        habit = Habit(
            name=name,
            periodicity=periodicity,
            created_at=created_at,
            user_id=user_id,
        )
        habit_id = self._database.insert(
            "habits",
            {
                "user_id": user_id,
                "name": habit.name,
                "periodicity": habit.periodicity,
                "created_at": habit.created_at,
            },
        )
        habit.id = habit_id
        return habit

    def edit_habit(
        self,
        user_id: int,
        habit_id: int,
        name: str | None = None,
        completion_id: int | None = None,
        minutes: object = None,
    ) -> Habit:
        """Rename a habit, correct one logged entry, or both.

        Only the habit identified by ``habit_id`` is written. A completion
        id from a different habit is rejected, so a correction cannot
        land on someone else's row.

        Arguments:
            user_id: Owner of the habit.
            habit_id: Habit to change.
            name: New name, when renaming.
            completion_id: Entry to correct. Requires ``minutes``.
            minutes: New length for that entry.

        Returns:
            The habit after the change.

        Raises:
            ValueError: If the habit is not this user's, the name is
                empty, the entry does not belong to the habit, or the
                minutes are not a positive whole number.
        """
        habit = self._owned_habit(user_id, habit_id)
        if name is None and completion_id is None:
            raise ValueError("Nothing to change.")

        if name is not None:
            habit.rename(name)
            self._database.update(
                "habits",
                {"name": habit.name},
                "id = ? AND user_id = ?",
                (habit_id, user_id),
            )

        if completion_id is not None:
            if minutes is None:
                raise ValueError("Enter the corrected number of minutes.")
            completion = self._owned_completion(habit_id, completion_id)
            completion.update_minutes(minutes)
            self._database.update(
                "completions",
                {"minutes_spent": completion.minutes_spent},
                "id = ? AND habit_id = ?",
                (completion_id, habit_id),
            )
        return habit

    def delete_habit(self, user_id: int, habit_id: int) -> None:
        """Delete one habit and the time records that belong to it.

        Foreign keys are on, so the completions are removed with the
        habit. Other habits are left as they are.

        Arguments:
            user_id: Owner of the habit.
            habit_id: Habit to remove.

        Raises:
            ValueError: If this user does not own the habit.
        """
        self._owned_habit(user_id, habit_id)
        self._database.delete(
            "habits",
            "id = ? AND user_id = ?",
            (habit_id, user_id),
        )

    def log_completion(
        self,
        user_id: int,
        habit_id: int,
        minutes: object,
        timestamp: str | None = None,
    ) -> Completion:
        """Append one time entry. Logging again in the same period adds another row.

        Arguments:
            user_id: Owner of the habit.
            habit_id: Habit being logged.
            minutes: Positive whole number. Strings from the text box
                are accepted here so the check lives in one place.
            timestamp: ISO timestamp. Leave empty in the app so the
                entry is stamped from the clock. Same reason as
                ``create_habit``: the clock is read when the method runs.

        Returns:
            The saved Completion.

        Raises:
            ValueError: If the minutes are invalid or the habit is not
                this user's.
        """
        self._owned_habit(user_id, habit_id)
        if timestamp is None:
            timestamp = datetime.now().isoformat(timespec="seconds")
        completion = Completion(habit_id, parse_minutes(minutes), timestamp)
        completion.id = self._database.insert(
            "completions",
            {
                "habit_id": habit_id,
                "minutes_spent": completion.minutes_spent,
                "timestamp": completion.timestamp,
            },
        )
        return completion

    def get_habits(self, user_id: int) -> list[Habit]:
        """Return this user's active habits, oldest first.

        Arguments:
            user_id: Account whose habits should be loaded.

        Returns:
            A list of Habit objects. Empty when the user has none.
        """
        rows = self._database.query(
            """
            SELECT id, user_id, name, periodicity, created_at, is_active
            FROM habits
            WHERE user_id = ? AND is_active = 1
            ORDER BY id
            """,
            (user_id,),
        )
        return [Habit.from_row(row) for row in rows]

    def get_completions(self, user_id: int, habit_id: int) -> list[Completion]:
        """Return the time entries for one of this user's habits.

        Arguments:
            user_id: Owner. Used to reject another account's habit.
            habit_id: Habit whose entries are listed.

        Returns:
            Completions ordered by the time they were recorded.

        Raises:
            ValueError: If this user does not own the habit.
        """
        self._owned_habit(user_id, habit_id)
        rows = self._database.query(
            """
            SELECT id, habit_id, minutes_spent, timestamp
            FROM completions
            WHERE habit_id = ?
            ORDER BY timestamp, id
            """,
            (habit_id,),
        )
        return [Completion.from_row(row) for row in rows]

    def summary(self, user: User, reference: date | None = None) -> list[dict]:
        """Dashboard progress rows. See ``Analytics.summary``.

        Arguments:
            user: Logged-in account.
            reference: Date treated as today. The GUI leaves this empty.

        Returns:
            One dictionary per habit, with name, periodicity, total time
            in the current period, and streak.
        """
        return self.analytics.summary(user, reference)

    def overview(self, user: User, reference: date | None = None) -> list[dict]:
        """Every habit measured on today, this week and this month.

        Arguments:
            user: Logged-in account.
            reference: Date treated as today. The GUI leaves this empty.

        Returns:
            One dictionary per habit. See ``Analytics.overview``.
        """
        return self.analytics.overview(user, reference)

    def weekly_minutes(self, user: User, reference: date | None = None) -> list[dict]:
        """Minutes per habit for the chart. See ``Analytics.weekly_minutes``.

        Arguments:
            user: Logged-in account.
            reference: A date inside the week. The GUI leaves this empty
                so the chart shows the current week.

        Returns:
            One dictionary per habit, with name, periodicity and minutes.
        """
        return self.analytics.weekly_minutes(user, reference)

    def lacking_this_week(self, user: User, reference: date | None = None) -> list[dict]:
        """Habits with nothing logged in the current ISO week.

        Arguments:
            user: Logged-in account.
            reference: A date inside the week. The GUI leaves this empty.

        Returns:
            One dictionary per habit that has zero minutes this week.
        """
        return self.analytics.lacking_this_week(user, reference)

    def export_csv(self, user: User, file_path: str) -> int:
        """Write this user's habits and time entries to a CSV file.

        The password hash and email are left out. The file is a copy of
        the activity log, not of the account. Only this user's rows are
        written.

        Arguments:
            user: Logged-in account. Needs an id.
            file_path: Destination path chosen in the save dialog.

        Returns:
            How many data rows were written. A habit with no time entries
            still produces one row so it appears in the file.

        Raises:
            ValueError: If the user has not been saved.
            OSError: If the file cannot be written.
        """
        if user.id is None:
            raise ValueError("User has not been saved.")
        habits = self.get_habits(user.id)
        written = 0
        # newline="" is required by the csv module on Windows, otherwise
        # each row is followed by a blank line.
        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["habit_name", "periodicity", "created_at", "minutes_spent", "recorded_at"]
            )
            for habit in habits:
                entries = self.get_completions(user.id, habit.id)
                if not entries:
                    writer.writerow([habit.name, habit.periodicity, habit.created_at, "", ""])
                    written += 1
                    continue
                for entry in entries:
                    writer.writerow(
                        [
                            habit.name,
                            habit.periodicity,
                            habit.created_at,
                            entry.minutes_spent,
                            entry.timestamp,
                        ]
                    )
                    written += 1
        return written

    def _require_user(self, user_id: int) -> None:
        """Fail clearly when the account id is not in the database."""
        rows = self._database.query("SELECT id FROM users WHERE id = ?", (user_id,))
        if not rows:
            raise ValueError("User not found.")

    def _owned_habit(self, user_id: int, habit_id: int) -> Habit:
        """Load a habit only when it belongs to ``user_id``.

        A missing habit and someone else's habit produce the same error,
        so the message does not reveal that the other row exists.
        """
        rows = self._database.query(
            """
            SELECT id, user_id, name, periodicity, created_at, is_active
            FROM habits
            WHERE id = ? AND user_id = ?
            """,
            (habit_id, user_id),
        )
        if not rows:
            raise ValueError("Habit not found.")
        return Habit.from_row(rows[0])

    def _owned_completion(self, habit_id: int, completion_id: int) -> Completion:
        """Load an entry only when it belongs to this habit."""
        rows = self._database.query(
            """
            SELECT id, habit_id, minutes_spent, timestamp
            FROM completions
            WHERE id = ? AND habit_id = ?
            """,
            (completion_id, habit_id),
        )
        if not rows:
            raise ValueError("Time entry not found for this habit.")
        return Completion.from_row(rows[0])
