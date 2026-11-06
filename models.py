"""Data objects for an account, a habit and one logged block of time.

These classes do not talk to SQLite. HabitTracker and AuthService save
them through the Database class. Keeping the rules here (a name cannot
be empty, minutes must be a positive whole number) means the GUI and
the tests share one definition of valid data.
"""


class User:
    """One private account.

    Attributes:
        id: Database id, or None before the row is saved.
        name: Name shown on the dashboard.
        email: Stored in lower case so log-in is case-insensitive.
        password_hash: Salt and hash together. Never the plain password.
    """

    def __init__(
        self,
        name: str,
        email: str,
        password_hash: str,
        id: int | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash


# The only periods a habit can use. The database CHECK constraint lists
# the same three values.
PERIODS = ("daily", "weekly", "monthly")


class Habit:
    """One activity the user tracks, daily, weekly or monthly.

    Attributes:
        id: Database id, or None before the row is saved.
        user_id: Owner of the habit. Accounts are private, so every
            habit row remembers which user created it.
        name: Label shown on the habit button.
        periodicity: ``"daily"``, ``"weekly"`` or ``"monthly"``.
        created_at: ISO timestamp set when the habit is created.
        is_active: False when the habit should be hidden. Deleting a
            habit removes the row instead of using this flag.
    """

    def __init__(
        self,
        name: str,
        periodicity: str,
        created_at: str,
        is_active: bool = True,
        id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        self.id = id
        self.user_id = user_id
        self.name = _clean_name(name)
        self.periodicity = _clean_periodicity(periodicity)
        self.created_at = created_at
        self.is_active = is_active

    def rename(self, new_name: str) -> None:
        """Change the habit's name.

        Arguments:
            new_name: Replacement label. Blank text is rejected.

        Raises:
            ValueError: If the name is empty or only spaces.
        """
        self.name = _clean_name(new_name)

    @classmethod
    def from_row(cls, row: object) -> "Habit":
        """Build a Habit from a sqlite3.Row (or any mapping)."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            periodicity=row["periodicity"],
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
        )


class Completion:
    """One recorded block of time for a habit.

    Attributes:
        id: Database id, or None before the row is saved.
        habit_id: Habit this entry belongs to.
        minutes_spent: Positive whole number of minutes.
        timestamp: ISO timestamp set when the entry is recorded.
    """

    def __init__(
        self,
        habit_id: int,
        minutes_spent: object,
        timestamp: str,
        id: int | None = None,
    ) -> None:
        self.id = id
        self.habit_id = habit_id
        self.minutes_spent = parse_minutes(minutes_spent)
        self.timestamp = timestamp

    def update_minutes(self, minutes: object) -> None:
        """Correct the time on this entry.

        Arguments:
            minutes: New length. Must be a positive whole number.
                A second log for the same day is a new Completion;
                this method changes an existing one.

        Raises:
            ValueError: If ``minutes`` is not a positive whole number.
        """
        self.minutes_spent = parse_minutes(minutes)

    @classmethod
    def from_row(cls, row: object) -> "Completion":
        """Build a Completion from a sqlite3.Row (or any mapping)."""
        return cls(
            id=row["id"],
            habit_id=row["habit_id"],
            minutes_spent=row["minutes_spent"],
            timestamp=row["timestamp"],
        )


def parse_minutes(value: object) -> int:
    """Turn user input into a positive whole number of minutes.

    Booleans are rejected because ``bool`` is a subclass of ``int`` in
    Python, so ``True`` would otherwise be accepted as 1 minute.

    Returns:
        The minutes as an int.

    Raises:
        ValueError: If the value is missing, not a whole number, or not positive.
    """
    if isinstance(value, bool):
        raise ValueError("Minutes must be a positive whole number.")
    if isinstance(value, int):
        minutes = value
    elif isinstance(value, str) and value.strip().isdigit():
        minutes = int(value.strip())
    else:
        raise ValueError("Minutes must be a positive whole number.")
    if minutes <= 0:
        raise ValueError("Minutes must be greater than zero.")
    return minutes


def _clean_name(name: object) -> str:
    """Return a stripped habit name, or reject an empty one."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Habit name cannot be empty.")
    return name.strip()


def _clean_periodicity(periodicity: object) -> str:
    """Return ``daily``, ``weekly`` or ``monthly``.

    The check is the same rule as the database CHECK constraint, so a
    bad value fails in the logic layer with a clear message before SQL runs.
    """
    if not isinstance(periodicity, str):
        raise ValueError("Periodicity must be 'daily', 'weekly' or 'monthly'.")
    cleaned = periodicity.strip().lower()
    if cleaned not in PERIODS:
        raise ValueError("Periodicity must be 'daily', 'weekly' or 'monthly'.")
    return cleaned
