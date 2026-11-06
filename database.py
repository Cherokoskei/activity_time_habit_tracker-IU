"""SQLite access for the habit tracker.

AuthService, HabitTracker and Analytics are the only callers. The GUI must
not import this module or write SQL. That split is what lets the logic be
tested with an in-memory database and no Tkinter window.
"""

import re
import sqlite3
from typing import Any, Mapping, Sequence


# Table and column names cannot be bound as ``?`` parameters. They are
# interpolated only after this check, and only from names our own code passes.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Database:
    """All SQLite access for users, habits and completions.

    A connection always has ``PRAGMA foreign_keys = ON``. Without that
    pragma, SQLite ignores ``ON DELETE CASCADE`` and deleting a habit
    would leave its completion rows behind.

    Arguments:
        db_name: Path to the database file. Production uses ``habits.db``.
            Tests pass ``":memory:"`` so nothing is written to disk.

    The connection is opened in ``__init__`` via ``connect()``. Call
    ``create_tables()`` once before inserting rows.
    """

    def __init__(self, db_name: str = "habits.db") -> None:
        self.db_name = db_name
        self.conn: sqlite3.Connection | None = None
        self.connect()

    def connect(self) -> sqlite3.Connection:
        """Open the database if it is not already open.

        Calling this twice returns the same connection. A second
        ``sqlite3.connect(":memory:")`` would be a different, empty
        database, so reconnecting silently would drop test data.

        Returns:
            The open connection.

        Raises:
            sqlite3.Error: If SQLite cannot open ``db_name``.
        """
        if self.conn is not None:
            return self.conn

        self.conn = sqlite3.connect(self.db_name)
        # Rows can be read by column name (row["email"]) or by index.
        self.conn.row_factory = sqlite3.Row
        # Required on every connection, not just at database-creation time.
        self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn

    def close(self) -> None:
        """Close the connection. Safe to call more than once."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def create_tables(self) -> None:
        """Create users, habits and completions if they do not exist.

        ``habits.user_id`` is not in the original concept table. It is
        required here because each account is private: a user must only
        load and change their own habits.

        Email uniqueness is exact text. AuthService stores emails in
        lower case so ``Test@x.com`` and ``test@x.com`` cannot both exist.
        """
        conn = self._require_connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                periodicity TEXT NOT NULL CHECK (periodicity IN ('daily', 'weekly', 'monthly')),
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
                minutes_spent INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            );
            """
        )
        conn.commit()
        self._allow_monthly_habits()

    def _allow_monthly_habits(self) -> None:
        """Rebuild an older habits table so monthly habits can be saved.

        ``CREATE TABLE IF NOT EXISTS`` leaves a database that was created
        before monthly tracking alone. SQLite cannot change a CHECK
        constraint in place, so the table is copied when its definition
        does not mention ``monthly``. Completions stay, because foreign
        keys are switched off only for this copy.
        """
        conn = self._require_connection()
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'habits'"
        ).fetchone()
        if row is None or "monthly" in row["sql"]:
            return
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            CREATE TABLE habits_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                periodicity TEXT NOT NULL CHECK (periodicity IN ('daily', 'weekly', 'monthly')),
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO habits_new (id, user_id, name, periodicity, created_at, is_active)
            SELECT id, user_id, name, periodicity, created_at, is_active FROM habits;
            DROP TABLE habits;
            ALTER TABLE habits_new RENAME TO habits;
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    def insert(self, table: str, data: Mapping[str, Any]) -> int:
        """Insert one row.

        Arguments:
            table: Table name from our own code, not from user input.
            data: Column names mapped to values. Values are bound as
                parameters and are never interpolated into the SQL text.

        Returns:
            The new row id.

        Raises:
            ValueError: If ``table``, a column name, or ``data`` is empty
                or not a safe identifier.
            sqlite3.IntegrityError: If a constraint fails (duplicate email,
                bad periodicity, missing foreign key, and so on).
        """
        if not data:
            raise ValueError("insert() needs at least one column.")

        table_name = _check_identifier(table)
        columns = [_check_identifier(column) for column in data]
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO {table_name} ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
        cursor = self._require_connection().execute(sql, tuple(data.values()))
        self._require_connection().commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Insert did not return a row id.")
        return int(cursor.lastrowid)

    def update(
        self,
        table: str,
        data: Mapping[str, Any],
        where: str,
        params: Sequence[Any] = (),
    ) -> int:
        """Update columns in ``data`` for rows matching ``where``.

        Arguments:
            table: Table name from our own code.
            data: Columns to change. Values are bound as parameters.
            where: SQL predicate written by our code, such as ``"id = ?"``.
                User text belongs in ``params``, not in this string.
            params: Values for the ``?`` placeholders in ``where``.

        Returns:
            How many rows were changed.

        Raises:
            ValueError: If an identifier is unsafe or ``data`` is empty.
        """
        if not data:
            raise ValueError("update() needs at least one column.")

        table_name = _check_identifier(table)
        assignments = ", ".join(
            f"{_check_identifier(column)} = ?" for column in data
        )
        sql = f"UPDATE {table_name} SET {assignments} WHERE {where}"
        values = tuple(data.values()) + tuple(params)
        cursor = self._require_connection().execute(sql, values)
        self._require_connection().commit()
        return int(cursor.rowcount)

    def delete(self, table: str, where: str, params: Sequence[Any] = ()) -> int:
        """Delete rows matching ``where``.

        Arguments:
            table: Table name from our own code.
            where: SQL predicate written by our code. With foreign keys
                on, deleting a habit also deletes its completions.
            params: Values for the ``?`` placeholders in ``where``.

        Returns:
            How many rows were deleted from ``table`` itself. Cascaded
            completions are removed but are not included in this count.

        Raises:
            ValueError: If ``table`` is not a safe identifier.
        """
        table_name = _check_identifier(table)
        sql = f"DELETE FROM {table_name} WHERE {where}"
        cursor = self._require_connection().execute(sql, tuple(params))
        self._require_connection().commit()
        return int(cursor.rowcount)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Run a SELECT and return every matching row.

        Arguments:
            sql: A statement written by our code. Use ``?`` for values.
            params: Values bound to those placeholders.

        Returns:
            A list of rows. Empty when nothing matches.
        """
        cursor = self._require_connection().execute(sql, tuple(params))
        return list(cursor.fetchall())

    def _require_connection(self) -> sqlite3.Connection:
        """Return the open connection, or explain that ``connect()`` is needed.

        After ``close()``, a new ``:memory:`` connection would be empty.
        Failing here is clearer than quietly querying a blank database.
        """
        if self.conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self.conn


def _check_identifier(name: str) -> str:
    """Reject table or column names that are not plain identifiers.

    SQLite cannot parameterise identifiers. Checking them stops a value
    that was meant to be data from being executed as SQL.

    Raises:
        ValueError: If ``name`` is not a simple identifier.
    """
    if not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None:
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name
