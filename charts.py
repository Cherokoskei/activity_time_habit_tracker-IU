"""Draw the weekly minutes bar chart.

The numbers come from HabitTracker. This module only paints them, so
the chart can be checked without opening a window and without SQL.
Matplotlib is imported here because it is the one extra package the
chart needs. The rest of the app still runs on the standard library.
"""

from matplotlib.figure import Figure

# Same colours as the habit buttons, so the chart and the dashboard
# describe daily, weekly and monthly the same way.
_DAILY_BAR = "#7eabe8"
_WEEKLY_BAR = "#f0b45a"
_MONTHLY_BAR = "#7dcea0"


def draw_weekly_bars(figure: Figure, rows: list[dict]) -> None:
    """Replace the figure contents with one bar per habit.

    Arguments:
        figure: A Matplotlib figure. The window supplies it and then
            embeds it in Tk; tests pass a figure that is never shown.
        rows: Dictionaries from ``HabitTracker.weekly_minutes``, each
            with ``name``, ``periodicity`` and ``minutes``.
    """
    figure.clear()
    axes = figure.add_subplot(111)
    if not rows:
        axes.set_axis_off()
        axes.text(0.5, 0.5, "No habits yet", ha="center", va="center")
        figure.tight_layout()
        return

    names = [row["name"] for row in rows]
    minutes = [row["minutes"] for row in rows]
    colors = [_bar_color(row["periodicity"]) for row in rows]
    axes.bar(names, minutes, color=colors)
    axes.set_ylabel("Minutes")
    axes.set_title("Minutes this week")
    # Long habit names stay readable when there are several bars.
    axes.tick_params(axis="x", labelrotation=30)
    figure.tight_layout()


def _bar_color(periodicity: str) -> str:
    """Bar colour for one habit period."""
    if periodicity == "daily":
        return _DAILY_BAR
    if periodicity == "monthly":
        return _MONTHLY_BAR
    return _WEEKLY_BAR
