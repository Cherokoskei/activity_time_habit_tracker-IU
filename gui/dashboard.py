"""Dashboard: habit buttons, create / edit / delete, and the progress summary.

After every change the screen calls ``refresh_habits()`` so the buttons
match the database. Edit and Delete stay disabled until the user has
at least one habit.

Clicking a habit opens one window for that habit. Adding minutes and
changing a saved entry use different boxes, so the two actions are not
easy to mix up.
"""

import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from models import Completion, Habit, User
from templates import HABIT_TEMPLATES
from tracker import HabitTracker


# Button colours. The chart uses the stronger shade of the same three.
_PERIOD_COLORS = {
    "daily": ("#d6e6fb", "#c3d9f5"),
    "weekly": ("#fde7c7", "#f6d7a8"),
    "monthly": ("#d7f0df", "#bfe5cc"),
}


def _period_words(periodicity: str) -> tuple[str, str, str]:
    """Words for a period: when it is, and the streak unit singular and plural."""
    if periodicity == "daily":
        return "today", "day", "days"
    if periodicity == "monthly":
        return "this month", "month", "months"
    return "this week", "week", "weeks"


def friendly_timestamp(value: str) -> str:
    """Turn a stored timestamp into a short date a person can read.

    Arguments:
        value: Timestamp saved with the completion, usually ISO format.

    Returns:
        ``5 Jan 2026, 18:00`` when the value can be parsed. The original
        string otherwise, so a bad row is still visible.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%d %b %Y, %H:%M")


class HabitButton(tk.Button):
    """A floating button for one habit.

    The label shows the name and the minutes already logged in the
    current period. Clicking it calls ``on_habit_click`` on the dashboard.

    Arguments:
        master: Frame that lays the buttons out.
        habit: Habit this button represents.
        on_click: Called with the habit when the button is pressed.
        minutes: Time logged today (daily) or this week (weekly).
        streak: Current streak, shown on the button so progress is
            visible without reading the summary box.
    """

    def __init__(
        self,
        master: tk.Misc,
        habit: Habit,
        on_click,
        minutes: int = 0,
        streak: int = 0,
    ) -> None:
        self.habit = habit
        # Two colours so a daily habit and a weekly habit can be told
        # apart without reading the second line of the label.
        background, active = _PERIOD_COLORS[habit.periodicity]
        when, _singular, _plural = _period_words(habit.periodicity)
        super().__init__(
            master,
            text=f"{habit.name}\n{minutes} min {when}\nstreak {streak}",
            width=16,
            height=4,
            wraplength=130,
            justify="center",
            command=lambda: on_click(habit),
            relief="raised",
            bg=background,
            activebackground=active,
            font=("Segoe UI", 9),
        )


class DashboardWindow(tk.Frame):
    """Main screen after a successful log-in.

    Arguments:
        master: The application window.
        app: Controller with ``tracker`` and ``show_login``.
        user: Account whose habits are shown.
    """

    def __init__(self, master: tk.Misc, app: object, user: User) -> None:
        super().__init__(master, padx=16, pady=16)
        self.app = app
        self.user = user
        self.pack(fill="both", expand=True)

        header = tk.Frame(self)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"Hello, {user.name}",
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left")
        tk.Button(header, text="Log out", command=self._log_out).pack(side="right")

        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", pady=(12, 4))
        tk.Button(toolbar, text="New habit", width=12, command=self._open_create).pack(side="left")
        # Disabled until refresh_habits sees at least one habit.
        self.edit_button = tk.Button(
            toolbar, text="Rename", width=12, command=self._open_edit, state="disabled"
        )
        self.edit_button.pack(side="left", padx=8)
        self.delete_button = tk.Button(
            toolbar, text="Delete", width=12, command=self._open_delete, state="disabled"
        )
        self.delete_button.pack(side="left")
        tk.Button(toolbar, text="This week", width=12, command=self._open_chart).pack(
            side="left", padx=(16, 0)
        )
        tk.Button(toolbar, text="Export CSV", width=12, command=self._export).pack(
            side="left", padx=8
        )
        tk.Label(
            self,
            text=(
                "Blue is daily, amber is weekly, green is monthly. "
                "Click a habit to add the minutes you spent."
            ),
            fg="#445066",
        ).pack(anchor="w", pady=(0, 8))

        self.notice = tk.Label(
            self,
            text="",
            wraplength=700,
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.habits_heading = tk.Label(self, text="Your habits", font=("Segoe UI", 11, "bold"))
        self.habits_heading.pack(anchor="w")
        self.button_area = tk.Frame(self, bg="#f4f7fb", height=180)
        self.button_area.pack(fill="both", expand=True, pady=(4, 8))
        self.button_area.bind("<Configure>", self._reflow)
        self.empty_label = tk.Label(
            self.button_area,
            text="No habits yet.\nClick New habit and pick a template, or type your own.",
            bg="#f4f7fb",
            fg="#445066",
            justify="left",
        )

        tk.Label(self, text="All activities", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.totals_label = tk.Label(self, text="", fg="#445066", anchor="w")
        self.totals_label.pack(fill="x", pady=(2, 4))
        columns = ("habit", "type", "today", "week", "month", "streak")
        self.progress_table = ttk.Treeview(
            self, columns=columns, show="headings", height=6
        )
        headings = (
            ("habit", "Habit", 160),
            ("type", "Type", 80),
            ("today", "Today", 70),
            ("week", "This week", 90),
            ("month", "This month", 90),
            ("streak", "Streak", 90),
        )
        for column, title, width in headings:
            self.progress_table.heading(column, text=title)
            self.progress_table.column(column, width=width, anchor="w", stretch=True)
        self.progress_table.pack(fill="x")

        self._buttons: list[HabitButton] = []
        self._announced_gaps = False
        self.refresh_habits()

    def refresh_habits(self) -> None:
        """Reload habits and the progress summary from the tracker.

        Called after create, log, edit, delete and when the dashboard opens,
        so the screen cannot show a habit that was just removed.
        """
        tracker: HabitTracker = self.app.tracker
        for button in self._buttons:
            button.destroy()
        habits = tracker.get_habits(self.user.id)
        progress = {row["habit_id"]: row for row in tracker.summary(self.user)}
        self._buttons = [
            HabitButton(
                self.button_area,
                habit,
                self.on_habit_click,
                minutes=progress.get(habit.id, {}).get("total_time", 0),
                streak=progress.get(habit.id, {}).get("streak", 0),
            )
            for habit in habits
        ]
        # An empty dashboard can only create. Edit and Delete need a habit.
        state = "normal" if habits else "disabled"
        self.edit_button.config(state=state)
        self.delete_button.config(state=state)
        if habits:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(x=12, y=12)
        self._show_overview(tracker.overview(self.user))
        lacking = tracker.lacking_this_week(self.user)
        self._show_lacking(lacking)
        # One dialog when the dashboard opens. Later refreshes only
        # update the banner, so logging time does not pop a window.
        if not self._announced_gaps:
            self._announced_gaps = True
            if lacking:
                names = lacking
                self.after(200, lambda: self._announce_lacking(names))
        self._reflow()

    def on_habit_click(self, habit: Habit) -> None:
        """Open the log-time window for the habit that was clicked.

        Arguments:
            habit: Habit attached to the button.
        """
        LogTimeDialog(self, habit)

    def _show_overview(self, rows: list[dict]) -> None:
        """Fill the table so every habit can be compared on the same periods."""
        self.progress_table.delete(*self.progress_table.get_children())
        if not rows:
            self.totals_label.config(
                text="Add a habit, then every activity shows up here together."
            )
            return
        today = sum(row["today"] for row in rows)
        week = sum(row["week"] for row in rows)
        month = sum(row["month"] for row in rows)
        self.totals_label.config(
            text=(
                f"Together: {today} min today"
                f"  ·  {week} min this week"
                f"  ·  {month} min this month"
            )
        )
        for row in rows:
            _when, singular, plural = _period_words(row["periodicity"])
            unit = singular if row["streak"] == 1 else plural
            self.progress_table.insert(
                "",
                "end",
                values=(
                    row["name"],
                    row["periodicity"].capitalize(),
                    f"{row['today']} min",
                    f"{row['week']} min",
                    f"{row['month']} min",
                    f"{row['streak']} {unit}",
                ),
            )

    def _show_lacking(self, rows: list[dict]) -> None:
        """Show which habits have no minutes in the current week."""
        if not self._buttons:
            self.notice.pack_forget()
            return
        if not rows:
            self.notice.config(
                text="Every habit has some time logged this week.",
                bg="#e7f6ec",
                fg="#1f6b3a",
            )
        else:
            names = ", ".join(row["name"] for row in rows)
            self.notice.config(
                text=(
                    f"Not logged this week: {names}. "
                    "Click each one and add the minutes you spent."
                ),
                bg="#fff4e5",
                fg="#8a4b08",
            )
        self.notice.pack(fill="x", pady=(0, 8), before=self.habits_heading)

    def _announce_lacking(self, rows: list[dict]) -> None:
        """Pop a reminder for habits with nothing logged this week."""
        if not self.winfo_exists() or not rows:
            return
        names = "\n".join(f"• {row['name']}" for row in rows)
        messagebox.showinfo(
            "Habits still open this week",
            "You have not logged any time this week for:\n\n" + names,
            parent=self,
        )

    def _reflow(self, _event: object = None) -> None:
        """Place habit buttons in rows that fit the current window width."""
        width = self.button_area.winfo_width()
        columns = max(1, width // 150)
        for index, button in enumerate(self._buttons):
            row, column = divmod(index, columns)
            button.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")

    def _log_out(self) -> None:
        """Return to the log-in screen. The account stays in the database."""
        self.app.show_login()

    def _open_create(self) -> None:
        CreateHabitDialog(self)

    def _open_edit(self) -> None:
        EditHabitDialog(self)

    def _open_delete(self) -> None:
        DeleteHabitDialog(self)

    def _open_chart(self) -> None:
        """Open the bar chart for this ISO week.

        Matplotlib is imported only when the button is pressed, so a
        missing package produces a message instead of stopping log-in.
        The minutes come from the tracker. This window does not query SQLite.
        """
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure

            from charts import draw_weekly_bars
        except ImportError:
            messagebox.showerror(
                "Chart",
                "Matplotlib is not installed.\n\nRun: python -m pip install -r requirements.txt",
                parent=self,
            )
            return
        rows = self.app.tracker.weekly_minutes(self.user)
        ChartWindow(self, rows, Figure, FigureCanvasTkAgg, draw_weekly_bars)

    def _export(self) -> None:
        """Ask for a path, then write this user's log as CSV."""
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export habits",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="habits.csv",
        )
        if not path:
            return
        try:
            count = self.app.tracker.export_csv(self.user, path)
        except (ValueError, OSError) as error:
            messagebox.showerror("Cannot export", str(error), parent=self)
            return
        messagebox.showinfo("Export", f"Saved {count} rows.", parent=self)


class CreateHabitDialog(tk.Toplevel):
    """Ask for a name and a period, with the seven templates as shortcuts.

    Arguments:
        dashboard: Screen to refresh after a habit is saved.
    """

    def __init__(self, dashboard: DashboardWindow) -> None:
        super().__init__(dashboard)
        self.dashboard = dashboard
        self.title("Create habit")
        self.resizable(False, False)
        self.transient(dashboard.winfo_toplevel())
        self.grab_set()

        frame = tk.Frame(self, padx=16, pady=16)
        frame.pack()
        tk.Label(
            frame,
            text="Pick a template to fill the name, or type your own.",
        ).pack(anchor="w")
        self.template_list = tk.Listbox(frame, height=7, width=32, exportselection=False)
        for name, periodicity in HABIT_TEMPLATES:
            self.template_list.insert("end", f"{name} ({periodicity})")
        self.template_list.pack(anchor="w", pady=8)
        self.template_list.bind("<<ListboxSelect>>", self._apply_template)

        tk.Label(frame, text="Name").pack(anchor="w")
        self.name_entry = tk.Entry(frame, width=32)
        self.name_entry.pack(anchor="w", pady=(0, 8))

        self.periodicity = tk.StringVar(value="daily")
        period_row = tk.Frame(frame)
        period_row.pack(anchor="w", pady=(0, 8))
        tk.Radiobutton(period_row, text="Daily", variable=self.periodicity, value="daily").pack(
            side="left"
        )
        tk.Radiobutton(
            period_row, text="Weekly", variable=self.periodicity, value="weekly"
        ).pack(side="left")
        tk.Radiobutton(
            period_row, text="Monthly", variable=self.periodicity, value="monthly"
        ).pack(side="left")

        tk.Button(frame, text="Add habit", command=self._create, width=12).pack(anchor="w")

    def _apply_template(self, _event: object = None) -> None:
        """Copy the selected template into the name and period controls."""
        selection = self.template_list.curselection()
        if not selection:
            return
        name, periodicity = HABIT_TEMPLATES[selection[0]]
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, name)
        self.periodicity.set(periodicity)

    def _create(self) -> None:
        """Save the habit through the tracker and refresh the dashboard."""
        tracker: HabitTracker = self.dashboard.app.tracker
        try:
            tracker.create_habit(
                self.dashboard.user.id,
                self.name_entry.get(),
                self.periodicity.get(),
            )
        except ValueError as error:
            messagebox.showerror("Cannot create habit", str(error), parent=self)
            return
        self.dashboard.refresh_habits()
        self.destroy()


class LogTimeDialog(tk.Toplevel):
    """Add a block of time and show the entries already saved.

    Arguments:
        dashboard: Screen to refresh after a change.
        habit: Habit the user clicked.
    """

    def __init__(self, dashboard: DashboardWindow, habit: Habit) -> None:
        super().__init__(dashboard)
        self.dashboard = dashboard
        self.habit = habit
        self.title(habit.name)
        self.resizable(False, False)
        self.transient(dashboard.winfo_toplevel())
        self.grab_set()

        frame = tk.Frame(self, padx=16, pady=16)
        frame.pack()
        period = {
            "daily": "every day",
            "weekly": "every week",
            "monthly": "every month",
        }[habit.periodicity]
        tk.Label(
            frame,
            text=habit.name,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(frame, text=f"You track this {period}.", fg="#445066").pack(anchor="w")

        add_box = tk.LabelFrame(frame, text="Add time", padx=10, pady=8)
        add_box.pack(fill="x", pady=(12, 0))
        tk.Label(add_box, text="How many minutes did you just spend?").pack(anchor="w")
        add_row = tk.Frame(add_box)
        add_row.pack(anchor="w", pady=(6, 0))
        self.minutes_entry = tk.Entry(add_row, width=8)
        self.minutes_entry.pack(side="left")
        self.minutes_entry.bind("<Return>", lambda _event: self._log())
        tk.Button(add_row, text="Add", command=self._log, width=10).pack(side="left", padx=(8, 0))

        saved_box = tk.LabelFrame(frame, text="Already logged", padx=10, pady=8)
        saved_box.pack(fill="x", pady=(12, 0))
        self.entry_list = tk.Listbox(saved_box, height=6, width=46, exportselection=False)
        self.entry_list.pack(anchor="w")
        self.empty_entries = tk.Label(
            saved_box,
            text="Nothing saved yet. Use Add above, then the line shows up here.",
            fg="#445066",
        )

        self.status = tk.Label(frame, text="", fg="#1f6b3a")
        self.status.pack(anchor="w", pady=(10, 0))
        tk.Button(frame, text="Done", command=self.destroy, width=10).pack(anchor="e", pady=(8, 0))
        self._entries: list[Completion] = []
        self._load_entries()
        self.minutes_entry.focus_set()

    def _load_entries(self) -> None:
        """Fill the list with this habit's saved times."""
        tracker: HabitTracker = self.dashboard.app.tracker
        self._entries = tracker.get_completions(self.dashboard.user.id, self.habit.id)
        self.entry_list.delete(0, "end")
        if not self._entries:
            self.empty_entries.pack(anchor="w", pady=(4, 0))
            return
        self.empty_entries.pack_forget()
        for entry in self._entries:
            self.entry_list.insert(
                "end",
                f"{friendly_timestamp(entry.timestamp)}    {entry.minutes_spent} min",
            )
        self.entry_list.see("end")

    def _log(self) -> None:
        """Append a new completion stamped with the current time."""
        tracker: HabitTracker = self.dashboard.app.tracker
        try:
            tracker.log_completion(
                self.dashboard.user.id,
                self.habit.id,
                self.minutes_entry.get(),
            )
        except ValueError as error:
            messagebox.showerror("Cannot log time", str(error), parent=self)
            return
        self.dashboard.refresh_habits()
        self.minutes_entry.delete(0, "end")
        self._load_entries()
        self.status.config(text="Added. The new line is at the bottom of the list.")


class EditHabitDialog(tk.Toplevel):
    """Rename a habit.

    Arguments:
        dashboard: Screen to refresh after a change.
    """

    def __init__(self, dashboard: DashboardWindow) -> None:
        super().__init__(dashboard)
        self.dashboard = dashboard
        self.title("Rename habit")
        self.resizable(False, False)
        self.transient(dashboard.winfo_toplevel())
        self.grab_set()

        frame = tk.Frame(self, padx=16, pady=16)
        frame.pack()
        tk.Label(frame, text="Which habit?").pack(anchor="w")
        self.habit_list = tk.Listbox(frame, height=5, width=40, exportselection=False)
        self.habit_list.pack(anchor="w", pady=(0, 8))
        self.habit_list.bind("<<ListboxSelect>>", lambda _event: self._show_name())

        tk.Label(frame, text="New name").pack(anchor="w")
        self.name_entry = tk.Entry(frame, width=32)
        self.name_entry.pack(anchor="w", pady=(0, 8))
        tk.Button(frame, text="Save name", command=self._save, width=12).pack(anchor="w")

        tracker: HabitTracker = dashboard.app.tracker
        self._habits = tracker.get_habits(dashboard.user.id)
        for habit in self._habits:
            self.habit_list.insert("end", f"{habit.name} ({habit.periodicity})")
        if self._habits:
            self.habit_list.selection_set(0)
            self._show_name()

    def _selected_habit(self) -> Habit | None:
        """Return the habit highlighted in the list."""
        selection = self.habit_list.curselection()
        if not selection:
            return None
        return self._habits[selection[0]]

    def _show_name(self) -> None:
        """Copy the selected habit's current name into the text box."""
        habit = self._selected_habit()
        if habit is None:
            return
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, habit.name)
        self.name_entry.selection_range(0, "end")
        self.name_entry.focus_set()

    def _save(self) -> None:
        """Rename the selected habit. Time entries are left as they are."""
        habit = self._selected_habit()
        if habit is None:
            messagebox.showerror("Rename habit", "Select a habit first.", parent=self)
            return
        tracker: HabitTracker = self.dashboard.app.tracker
        try:
            tracker.edit_habit(
                self.dashboard.user.id,
                habit.id,
                name=self.name_entry.get(),
            )
        except ValueError as error:
            messagebox.showerror("Cannot rename habit", str(error), parent=self)
            return
        self.dashboard.refresh_habits()
        self.destroy()


class DeleteHabitDialog(tk.Toplevel):
    """Pick a habit and ask for confirmation before it is removed.

    Arguments:
        dashboard: Screen to refresh after a deletion.
    """

    def __init__(self, dashboard: DashboardWindow) -> None:
        super().__init__(dashboard)
        self.dashboard = dashboard
        self.title("Delete habit")
        self.resizable(False, False)
        self.transient(dashboard.winfo_toplevel())
        self.grab_set()

        frame = tk.Frame(self, padx=16, pady=16)
        frame.pack()
        tk.Label(
            frame,
            text="Select a habit. You will be asked to confirm before it is removed.",
        ).pack(anchor="w")
        self.habit_list = tk.Listbox(frame, height=6, width=40, exportselection=False)
        self.habit_list.pack(anchor="w", pady=8)
        tk.Button(frame, text="Delete", command=self._delete, width=12).pack(anchor="w")

        tracker: HabitTracker = dashboard.app.tracker
        self._habits = tracker.get_habits(dashboard.user.id)
        for habit in self._habits:
            self.habit_list.insert("end", f"{habit.name} ({habit.periodicity})")

    def _delete(self) -> None:
        """Confirm, then remove the habit and its time records."""
        selection = self.habit_list.curselection()
        if not selection:
            messagebox.showerror("Delete habit", "Select a habit first.", parent=self)
            return
        habit = self._habits[selection[0]]
        confirmed = messagebox.askyesno(
            "Delete habit",
            f"Delete {habit.name} and all of its time records?",
            parent=self,
        )
        if not confirmed:
            return
        tracker: HabitTracker = self.dashboard.app.tracker
        try:
            tracker.delete_habit(self.dashboard.user.id, habit.id)
        except ValueError as error:
            messagebox.showerror("Cannot delete habit", str(error), parent=self)
            return
        self.dashboard.refresh_habits()
        self.destroy()


class ChartWindow(tk.Toplevel):
    """Bar chart of minutes logged in the current ISO week.

    Arguments:
        dashboard: Owner of the pop-up.
        rows: One dictionary per habit, from ``HabitTracker.weekly_minutes``.
        figure_type: Matplotlib ``Figure`` class. It is passed in so this
            module does not import Matplotlib at start-up.
        canvas_type: ``FigureCanvasTkAgg`` class, which embeds the figure.
        draw: ``draw_weekly_bars``. Called with the figure and the rows.
    """

    def __init__(
        self,
        dashboard: DashboardWindow,
        rows: list[dict],
        figure_type: type,
        canvas_type: type,
        draw,
    ) -> None:
        super().__init__(dashboard)
        self.title("Minutes this week")
        self.transient(dashboard.winfo_toplevel())
        figure = figure_type(figsize=(6.5, 3.8), dpi=100)
        draw(figure, rows)
        canvas = canvas_type(figure, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(
            self,
            text="Blue bars are daily, amber bars are weekly, green bars are monthly.",
        ).pack(anchor="w", padx=12, pady=(0, 8))
