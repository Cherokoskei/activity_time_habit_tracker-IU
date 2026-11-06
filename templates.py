"""The seven predefined habits from the concept.

The create-habit window offers these as quick choices. The tests import
the same list, so the fixtures cannot drift away from the dialog.
"""

# (name, periodicity). Periodicity is only "daily" or "weekly".
HABIT_TEMPLATES: list[tuple[str, str]] = [
    ("IU study time", "daily"),
    ("Cooking", "daily"),
    ("Exercise", "daily"),
    ("Sleeping", "daily"),
    ("Cleaning", "daily"),
    ("Shopping", "weekly"),
    ("Part-time job", "weekly"),
]
