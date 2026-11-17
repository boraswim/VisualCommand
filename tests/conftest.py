import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    """One Tk for the whole test run: creating/destroying many Tk instances in a row
    intermittently fails on Windows ("Can't find a usable tk.tcl")."""
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()
