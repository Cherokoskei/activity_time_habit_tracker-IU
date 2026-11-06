"""Application controller: opens the database and switches screens.

The windows talk to ``auth`` and ``tracker`` only. ``_database`` stays
on this class so a screen cannot run SQL by accident.
"""

import tkinter as tk
from pathlib import Path

from auth import AuthService
from database import Database
from gui.dashboard import DashboardWindow
from gui.login import LoginWindow
from models import User
from tracker import HabitTracker

# habits.db lives next to main.py, even if the app is started from another folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class App:
    """Start the desktop app and move between log-in and the dashboard.

    Arguments:
        db_path: SQLite file. Defaults to ``habits.db`` in the project
            root. Tests and the smoke check can pass ``":memory:"``.
    """

    def __init__(self, db_path: str | None = None) -> None:
        path = db_path if db_path is not None else str(PROJECT_ROOT / "habits.db")
        self.root = tk.Tk()
        self.root.title("Habit Tracker")
        self._database = Database(path)
        self._database.create_tables()
        self.auth = AuthService(self._database)
        self.tracker = HabitTracker(self._database)
        self.screen: LoginWindow | DashboardWindow | None = None
        self.show_login()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def show_login(self) -> None:
        """Show the log-in screen. Used at start and after log out."""
        self._clear()
        self.screen = LoginWindow(self.root, self)
        # Smaller than the dashboard, and centered as its own window.
        place_in_center(self.root, width=460, height=360)

    def show_dashboard(self, user: User) -> None:
        """Show this user's habits and progress.

        Arguments:
            user: Account returned by AuthService.
        """
        self._clear()
        self.screen = DashboardWindow(self.root, self, user)
        place_in_center(self.root)

    def run(self) -> None:
        """Open the window and wait until the user closes it."""
        self.root.mainloop()

    def close(self) -> None:
        """Close the database, then the window."""
        self._database.close()
        self.root.destroy()

    def _clear(self) -> None:
        """Remove the current screen before showing the next one."""
        for child in self.root.winfo_children():
            child.destroy()
        self.screen = None


def window_origin(
    screen_width: int,
    screen_height: int,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Top-left corner that puts a window in the middle of the screen.

    Arguments:
        screen_width: Width of the display in pixels.
        screen_height: Height of the display in pixels.
        width: Window width.
        height: Window height.

    Returns:
        ``(x, y)`` for Tk's geometry string. Never negative, so a window
        that is larger than the screen stays on the visible area.
    """
    return (
        max(0, (screen_width - width) // 2),
        max(0, (screen_height - height) // 2),
    )


def place_in_center(window: tk.Misc, width: int = 760, height: int = 560) -> None:
    """Give a window a fixed size and center it on the screen.

    Called after each screen change. The position is applied again once
    the window exists, because a size read before the window is shown
    can be 1 pixel and would pin the window to the top-left corner.
    A newer call cancels an older pending placement.
    """
    token = getattr(window, "_place_token", 0) + 1
    window._place_token = token

    def apply() -> None:
        if getattr(window, "_place_token", None) != token:
            return
        try:
            window.update_idletasks()
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
        except tk.TclError:
            return
        if screen_width <= 1 or screen_height <= 1:
            window.after(50, apply)
            return
        # The minimum has to match this size. A larger minimum, set for
        # the dashboard, would stop the log-in window from shrinking
        # and would leave it away from the center.
        window.minsize(width, height)
        x_pos, y_pos = window_origin(screen_width, screen_height, width, height)
        window.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    apply()
