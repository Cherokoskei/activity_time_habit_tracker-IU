"""Start the Habit Tracker desktop app.

Run this file from the project folder:

    python main.py
"""

from gui.app import App


def main() -> None:
    """Open the log-in window and keep it open until the user closes it."""
    App().run()


if __name__ == "__main__":
    main()
