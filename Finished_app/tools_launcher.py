"""Open the two standalone tkinter tools (Survival Guide, Survival Calendar) in their own
window. They run as separate processes so they never block or crash the Flet app."""
import atexit
import os
import subprocess
import sys

TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
SCRIPTS = {"guide": "survival_guide.py", "calendar": "survival_calendar.py"}
_procs = {}


def open_tool(name):
    """Returns "started", "already", "missing" or "error"."""
    running = _procs.get(name)
    if running and running.poll() is None:
        return "already"                  # window is still open
    script = os.path.join(TOOLS_DIR, SCRIPTS[name])
    if not os.path.exists(script):
        print("Tool script not found:", script)
        return "missing"
    try:
        _procs[name] = subprocess.Popen([sys.executable, script], cwd=TOOLS_DIR)
        return "started"
    except Exception as ex:
        print(f"Cannot open {name}:", ex)
        return "error"


def close_all():
    """Close every tool window that is still open (called when the app exits)."""
    for p in _procs.values():
        if p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass


atexit.register(close_all)