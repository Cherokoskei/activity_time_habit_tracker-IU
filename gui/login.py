"""Log-in and sign-up windows.

Both screens only check that the boxes are filled in a friendly way and
then call AuthService. Hashing and the duplicate-email rule live there.
"""

import tkinter as tk
from tkinter import messagebox

from auth import AuthService


def confirm_password(password: str, repeated: str) -> None:
    """Reject sign-up when the two password boxes differ.

    AuthService stores one password. The second box exists so a typing
    mistake is caught before the account is created.

    Raises:
        ValueError: If the two strings are not the same.
    """
    if password != repeated:
        raise ValueError("Passwords do not match.")


class LoginWindow(tk.Frame):
    """Email and password form shown when the app opens.

    Arguments:
        master: The application window.
        app: Controller with ``auth``, ``show_dashboard`` and ``show_login``.
    """

    def __init__(self, master: tk.Misc, app: object) -> None:
        super().__init__(master)
        self.app = app
        self.pack(fill="both", expand=True)

        # The card sits in the middle of the window. The window itself
        # is also centered on the screen by the application controller.
        card = tk.Frame(self)
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="Habit Tracker", font=("Segoe UI", 18, "bold")).pack()
        tk.Label(
            card,
            text="Log in to see your habits and progress.",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 16))

        tk.Label(card, text="Email").pack(anchor="w")
        self.email_entry = tk.Entry(card, width=36)
        self.email_entry.pack(anchor="w", pady=(0, 8))

        tk.Label(card, text="Password").pack(anchor="w")
        self.password_entry = tk.Entry(card, width=36, show="*")
        self.password_entry.pack(anchor="w", pady=(0, 8))
        self.password_entry.bind("<Return>", lambda _event: self._log_in())

        self.message = tk.Label(card, text="", fg="#9b2335", wraplength=280)
        self.message.pack(anchor="w", pady=(0, 8))

        buttons = tk.Frame(card)
        buttons.pack()
        tk.Button(buttons, text="Log in", command=self._log_in, width=12).pack(side="left")
        tk.Button(buttons, text="Sign up", command=self._open_sign_up, width=12).pack(
            side="left", padx=(8, 0)
        )

    def _log_in(self) -> None:
        """Ask AuthService to check the password, then open the dashboard."""
        auth: AuthService = self.app.auth
        try:
            user = auth.log_in(self.email_entry.get(), self.password_entry.get())
        except ValueError as error:
            self.message.config(text=str(error))
            return
        self.app.show_dashboard(user)

    def _open_sign_up(self) -> None:
        """Open the sign-up window on top of log-in."""
        SignupWindow(self.winfo_toplevel(), self.app)


class SignupWindow(tk.Toplevel):
    """Collect a name, email and password for a new account.

    Arguments:
        master: The main window.
        app: Controller. Only ``auth`` is used.
    """

    def __init__(self, master: tk.Misc, app: object) -> None:
        super().__init__(master)
        self.app = app
        self.title("Sign up")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        # Imported here so this module can load before gui.app finishes.
        from gui.app import place_in_center

        place_in_center(self, width=420, height=320)

        frame = tk.Frame(self, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Create an account", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        self.name_entry = self._field(frame, 1, "Name")
        self.email_entry = self._field(frame, 2, "Email")
        self.password_entry = self._field(frame, 3, "Password", secret=True)
        self.confirm_entry = self._field(frame, 4, "Confirm password", secret=True)

        self.message = tk.Label(frame, text="", fg="#9b2335")
        self.message.grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        tk.Button(frame, text="Create account", command=self._sign_up, width=16).grid(
            row=6, column=0, sticky="w"
        )

    def _field(self, frame: tk.Frame, row: int, label: str, secret: bool = False) -> tk.Entry:
        """Add a labelled text box and return the entry."""
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = tk.Entry(frame, width=32, show="*" if secret else "")
        entry.grid(row=row, column=1, sticky="w", pady=4)
        return entry

    def _sign_up(self) -> None:
        """Save the account, then send the user back to log in.

        The diagram goes sign-up, then log-in, so this window does not
        open the dashboard by itself.
        """
        auth: AuthService = self.app.auth
        try:
            confirm_password(self.password_entry.get(), self.confirm_entry.get())
            auth.sign_up(
                self.name_entry.get(),
                self.email_entry.get(),
                self.password_entry.get(),
            )
        except ValueError as error:
            self.message.config(text=str(error))
            return
        messagebox.showinfo(
            "Account created",
            "Your account is saved. Log in with your email and password.",
            parent=self,
        )
        self.destroy()
