# Activity Time Habit Tracker

A desktop habit tracker designed to help users record how much time they spend on everyday activities and monitor their progress over time.

## Project Aim

This project aims to create a simple, practical application for tracking personal routines and life activities in a clear and consistent way. It focuses on everyday commitments such as:

- Daily habits: IU study time, cooking, exercise, sleeping, and cleaning
- Weekly habits: shopping and part-time work

The application is meant to be easy to use, store data locally, and make progress visible each time the user logs in.

## Features

- Track daily activities with time-based records
- Track weekly activities separately from daily routines
- View progress over time for each habit
- Keep personal data stored locally on the machine
- Make the app simple enough for everyday use
- Keep the project structure clean and easy to test or extend

## Why this project matters

Many people want to build healthier routines but struggle to monitor their time consistently. This tracker helps users reflect on how their time is distributed across study, rest, household tasks, and work. It supports better planning by turning daily and weekly activity data into clear, readable progress information.

## Application Goals

- Record time spent on each habit accurately
- Show personal improvement over time
- Support easy daily and weekly tracking
- Preserve record history between sessions
- Keep the system lightweight and local-first

## How to run

From the project folder, in PowerShell:

```bash
python main.py
```

The first screen is log in. There is no window until this command is run, and the file has to be this `main.py` (an empty file exits immediately).

Install the extra packages once:

```bash
python -m pip install -r requirements.txt
```

Sign-up, habits, streaks and the CSV export use the Python standard library (Tkinter, SQLite, hashlib, csv). `requirements.txt` also lists pytest, for the tests, and Matplotlib, which draws the weekly bar chart. The chart window is the only place that imports Matplotlib. The buttons still ask `HabitTracker` for the numbers.

Data is stored in `habits.db` in this folder. The next time you log in, the same habits and progress are loaded. Deleting that file starts from an empty database.

## Using the app

1. **Sign up.** On the log-in screen, choose Sign up and enter a name, email and password. Type the password again in Confirm password. The two boxes must match. The password is stored as a salted PBKDF2 hash, not as plain text. After the account is saved, log in with the email and password. A wrong password or an unknown email shows the same error.
2. **Empty dashboard.** Create, Chart and Export are available. Edit and Delete stay disabled until a habit exists. Log out returns to the log-in screen. The main window opens in the center of the screen.
3. **Create a habit.** Choose one of the seven templates (IU study time, Cooking, Exercise, Sleeping, Cleaning, Shopping, Part-time job) or type a name, then choose daily or weekly. The habit is stamped with the current date and time and appears as a button. Daily buttons are blue and weekly buttons are amber.
4. **Log time.** Click a habit button, enter minutes, and choose Log time. Logging again in the same day or week adds another entry. Each entry is stamped when it is saved. To correct an entry, select it, enter the new minutes, and choose Update selected.
5. **Edit.** Rename the habit, or select one time entry and save a corrected number of minutes. Only the habit you selected is changed.
6. **Delete.** Choose the habit. The app asks you to confirm, then removes that habit and its time records.
7. **Progress.** The panel under the buttons shows, for each habit, the minutes in the current period (today for a daily habit, this ISO week for a weekly habit) and the current streak. A missed day or week sets the streak back to zero.
8. **Chart.** Opens a bar chart of minutes logged in the current ISO week, for every habit. Daily and weekly habits share that week so the bars can be compared. Blue bars are daily habits and amber bars are weekly habits.
9. **Export.** Saves this account's habits and time entries to a CSV file you choose. The file does not contain the password. Another account's habits are not included.

## Tests

From the project folder:

```bash
python -m pytest
```

The tests use an in-memory database and fixed dates. They do not open a window and they do not read `habits.db`.

## Technology Overview

This project is designed as a Python desktop application, with local data storage for persistence beyond a single session. The expected structure separates concerns into modules such as:

- authentication-related logic
- database management
- habit tracking logic
- analytics and progress reporting
- application entry point

## Project Structure

The windows call `AuthService` and `HabitTracker`. Those classes call `Database`. The GUI does not talk to SQLite itself.

```text
activity_time_habit_tracker-IU/
├── main.py                 # starts the app
├── database.py             # all SQLite access
├── models.py               # User, Habit, Completion
├── auth.py                 # sign up and log in
├── tracker.py              # create, edit, delete, log time
├── analytics.py            # totals, streaks, summary, weekly minutes
├── charts.py               # draws the weekly bar chart
├── templates.py            # the seven predefined habits
├── gui/
│   ├── app.py              # switches between screens
│   ├── login.py            # log in and sign up
│   └── dashboard.py        # habit buttons, dialogs, progress
├── tests/                  # pytest, no GUI
├── requirements.txt        # pytest and matplotlib
└── habits.db               # created on first launch
```

## Local Storage

The app stores records locally so that users can continue viewing their progress at the next login without relying on an external service. This makes the tracker simple, private, and easy to run on a desktop computer.

## Setup

1. Open the project folder.
2. Use Python 3.14 (Tkinter is part of the standard install).
3. Run `python main.py`.

## Possible later additions

Charts and CSV export are already included. They sit on `HabitTracker`, and the windows still do not call SQLite. Reminders are not in the app.

## License

This project is intended for educational and personal use. Add a license if you plan to share it publicly.

## Summary

The Activity Time Habit Tracker is a practical desktop app for recording daily and weekly time habits. It helps users stay aware of how they spend their time, track meaningful progress, and build consistent routines around study, health, household responsibilities, and work.
