#!/usr/bin/env python3
"""
The Hollow - Survival Calendar
==============================
A standalone planner for life underground: plan events (ration pickups, filter swaps, drills,
scavenging runs...), make them repeat, tick them off as done, and keep a status and a log for
every day. Standard library only (tkinter + json); it doesn't need any other Hollow file.

    python survival_calendar.py                      # uses survival_calendar.json next to this file
    python survival_calendar.py --file plan.json     # open / create another calendar file
    python survival_calendar.py --empty              # a brand-new calendar without the sample events

Mouse   click a day to select it, double-click a day to add an event on it,
        click an event chip to select it, double-click an event (anywhere) to edit it.
Keys    arrows move the selected day, PageUp / PageDown change month, T jumps to today,
        Ctrl+N new event, Ctrl+F search, Enter edits the selected event, Space ticks it done,
        Delete removes it, Escape clears the search.
Everything is saved automatically after every change (atomic write, so a crash can't corrupt it).

Data file layout (plain JSON, easy to read from other tools later):
    settings  sealed_on (day counter start), story_today (in-world "today"), week_start
    events    id, title, date, time, category, priority, location, repeat, interval, until,
              notes, done [dates ticked off], skip [dates removed from a repeating event]
    days      "YYYY-MM-DD": {status, note}
"""

import argparse
import calendar
import datetime as dt
import json
import os
import tempfile
import tkinter as tk
import uuid
from tkinter import messagebox, ttk

# ----------------------------------------------------------------------------- look & feel
BG, PANEL_BG, FIELD_BG, BORDER = "#14161c", "#1d2029", "#262a35", "#363c4d"
MUTED, TEXT, DIM = "#9aa3b5", "#dfe4ee", "#5c6375"
RED, AMBER, GREEN, ACCENT = "#ff7b72", "#f2c94c", "#6ee7a0", "#7cc4ff"
CELL_BG, CELL_OUT_BG, CELL_SEL, CHIP_DONE = "#1d2029", "#17191f", "#283044", "#2b2f3b"
FONT = "Helvetica"

UPCOMING_DAYS = 14          # how far ahead the "upcoming" list looks
MAX_CHIPS = 3               # events drawn inside one day cell before "+N more"

CATEGORIES = {              # name -> chip colour
    "Rations":     "#d9a441",
    "Water":       "#3a8ee0",
    "Air":         "#41b8a8",
    "Power":       "#c9c24a",
    "Maintenance": "#7d8aa6",
    "Medical":     "#e0605a",
    "Scavenging":  "#a77fe0",
    "Security":    "#e0863a",
    "Drill":       "#d65fa8",
    "Meeting":     "#5ab36e",
    "Other":       "#6b7384",
}
PRIORITIES = ["Low", "Normal", "High", "Critical"]
PRIORITY_MARK = {"Low": "", "Normal": "", "High": "! ", "Critical": "!! "}
REPEATS = ["None", "Daily", "Weekly", "Monthly"]
REPEAT_UNIT = {"None": "", "Daily": "day(s)", "Weekly": "week(s)", "Monthly": "month(s)"}
DAY_STATUSES = {"Normal": "", "Alert": AMBER, "Emergency": RED, "Lockdown": "#c77dff"}
WEEK_STARTS = {"Monday": 0, "Sunday": 6}
ALL_CATEGORIES = "All categories"


# ----------------------------------------------------------------------------- helpers
def parse_date(text):
    text = str(text).strip()
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a date - use YYYY-MM-DD") from None


def parse_time(text):
    """'7:5' -> '07:05', '' -> '' (all day). Raises ValueError for anything else."""
    text = str(text).strip()
    if not text:
        return ""
    try:
        h, m = text.split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    raise ValueError(f"'{text}' is not a time - use HH:MM (24h) or leave it empty for all day")


def months_between(a, b):
    return (b.year - a.year) * 12 + b.month - a.month


def text_on(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#111111" if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#ffffff"


def relative_day(d, today):
    n = (d - today).days
    if n == 0:
        return "today"
    if n == 1:
        return "tomorrow"
    if n == -1:
        return "yesterday"
    return f"in {n} days" if n > 0 else f"{-n} days ago"


def repeat_text(ev):
    if ev["repeat"] == "None":
        return "One-off"
    n, unit = ev["interval"], REPEAT_UNIT[ev["repeat"]].replace("(s)", "")
    text = f"Every {unit}" if n == 1 else f"Every {n} {unit}s"
    return text + (f" until {ev['until']}" if ev["until"] else "")


# ----------------------------------------------------------------------------- data
class CalendarStore:
    """All calendar data plus the JSON file it lives in. No tkinter in here."""

    def __init__(self, path, seed=True):
        self.path = path
        self.events = {}        # id -> event dict (done/skip are sets, _start/_until are dates)
        self.days = {}          # "YYYY-MM-DD" -> {"status": ..., "note": ...}
        self.settings = {"sealed_on": "", "story_today": "", "week_start": "Monday"}
        self.warning = ""
        if os.path.exists(path):
            self._load()
        else:
            if seed:
                self._seed()
            try:
                self.save()
            except OSError as e:
                self.warning = f"Can't create {path}: {e}"

    # ---- file ----------------------------------------------------------------
    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("not a calendar file")
        except (OSError, ValueError) as e:
            backup = self.path + ".broken"
            try:
                os.replace(self.path, backup)
                kept = f"the old file was kept as {os.path.basename(backup)}"
            except OSError:
                kept = "the old file was left untouched"
            self.warning = f"Couldn't read {os.path.basename(self.path)} ({e}); {kept}. Starting empty."
            return
        for k, v in (data.get("settings") or {}).items():
            if k in self.settings and isinstance(v, str):
                self.settings[k] = v
        for raw in data.get("events") or []:
            ev = self._normalize(raw)
            if ev:
                self.events[ev["id"]] = ev
        for k, v in (data.get("days") or {}).items():
            if isinstance(v, dict):
                status = v.get("status") if v.get("status") in DAY_STATUSES else "Normal"
                self.days[k] = {"status": status, "note": str(v.get("note") or "")}

    def save(self):
        events = []
        for ev in sorted(self.events.values(), key=lambda e: (e["date"], e["time"], e["title"].lower())):
            out = {k: v for k, v in ev.items() if not k.startswith("_")}
            out["done"], out["skip"] = sorted(ev["done"]), sorted(ev["skip"])
            events.append(out)
        data = {
            "version": 1,
            "settings": self.settings,
            "events": events,
            "days": {k: v for k, v in sorted(self.days.items())
                     if v["status"] != "Normal" or v["note"].strip()},
        }
        folder = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(prefix=".calendar-", suffix=".json", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)          # atomic: the old file stays intact until this
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _seed(self):
        """A few sample events so a first run isn't empty (skip with --empty)."""
        t = dt.date.today()
        next_monday = t + dt.timedelta(days=(7 - t.weekday()) % 7 or 7)
        self.settings["sealed_on"] = (t - dt.timedelta(days=211)).isoformat()
        samples = [
            dict(title="Water ration pickup", date=t, time="07:30", category="Water",
                 location="Level 4 depot", repeat="Daily"),
            dict(title="Air scrubber filter swap", date=t + dt.timedelta(1), time="14:00", category="Air",
                 priority="High", repeat="Daily", interval=3, notes="Bring two spare filters from stores."),
            dict(title="Ration distribution", date=next_monday, time="09:00", category="Rations",
                 repeat="Weekly", location="Mess hall, level 3"),
            dict(title="Medical check-ups", date=t + dt.timedelta(3), category="Medical",
                 repeat="Weekly", interval=2, location="Infirmary"),
            dict(title="Lockdown drill", date=t + dt.timedelta(5), time="20:00", category="Drill",
                 priority="Critical", notes="All levels. Bulkheads sealed within 4 minutes."),
            dict(title="Council meeting", date=t + dt.timedelta(6), time="18:00", category="Meeting",
                 location="Level 1"),
            dict(title="Scavenging run: upper vents", date=t + dt.timedelta(9), time="05:00",
                 category="Scavenging", priority="High", location="Vent shaft C"),
            dict(title="Generator overhaul", date=t + dt.timedelta(12), time="10:00", category="Power",
                 priority="High", repeat="Monthly"),
        ]
        for s in samples:
            s["date"] = s["date"].isoformat()
            self.add_event(s)
        self.days[(t + dt.timedelta(5)).isoformat()] = {"status": "Alert",
                                                         "note": "Drill day: keep corridors clear."}

    # ---- events --------------------------------------------------------------
    @staticmethod
    def _normalize(raw):
        """Validated event dict, or None if it's unusable."""
        try:
            start = parse_date(raw["date"])
            until = parse_date(raw["until"]) if raw.get("until") else None
            ev = {
                "id": str(raw.get("id") or uuid.uuid4().hex),
                "title": str(raw.get("title", "")).strip() or "(untitled)",
                "date": start.isoformat(),
                "time": parse_time(raw.get("time", "")),
                "category": raw.get("category") if raw.get("category") in CATEGORIES else "Other",
                "priority": raw.get("priority") if raw.get("priority") in PRIORITIES else "Normal",
                "location": str(raw.get("location", "")).strip(),
                "repeat": raw.get("repeat") if raw.get("repeat") in REPEATS else "None",
                "interval": max(1, int(raw.get("interval", 1))),
                "until": until.isoformat() if until else "",
                "notes": str(raw.get("notes", "")).rstrip(),
                "done": {str(x) for x in raw.get("done", [])},
                "skip": {str(x) for x in raw.get("skip", [])},
                "_start": start,
                "_until": until,
            }
        except (KeyError, ValueError, TypeError, AttributeError):
            return None
        return ev

    def add_event(self, fields):
        ev = self._normalize(dict(fields, id=uuid.uuid4().hex))
        if ev is None:
            raise ValueError("invalid event")
        self.events[ev["id"]] = ev
        return ev["id"]

    def update_event(self, eid, fields):
        old = self.events[eid]
        ev = self._normalize(dict(fields, id=eid, done=old["done"], skip=old["skip"]))
        if ev is None:
            raise ValueError("invalid event")
        self.events[eid] = ev

    def delete_event(self, eid):
        self.events.pop(eid, None)

    def skip_occurrence(self, eid, d):
        self.events[eid]["skip"].add(d.isoformat())
        self.events[eid]["done"].discard(d.isoformat())

    def is_done(self, ev, d):
        return d.isoformat() in ev["done"]

    def toggle_done(self, eid, d):
        done, key = self.events[eid]["done"], d.isoformat()
        if key in done:
            done.discard(key)
            return False
        done.add(key)
        return True

    @staticmethod
    def occurs_on(ev, d):
        start, until = ev["_start"], ev["_until"]
        if d < start or (until and d > until) or d.isoformat() in ev["skip"]:
            return False
        rep, n = ev["repeat"], ev["interval"]
        if rep == "None":
            return d == start
        if rep == "Daily":
            return (d - start).days % n == 0
        if rep == "Weekly":
            return (d - start).days % (7 * n) == 0
        # Monthly: same day of the month; a start on the 31st falls on the last day of short months
        if months_between(start, d) % n:
            return False
        return d.day == min(start.day, calendar.monthrange(d.year, d.month)[1])

    def events_on(self, d, keep=None):
        evs = [e for e in self.events.values() if self.occurs_on(e, d) and (keep is None or keep(e))]
        evs.sort(key=lambda e: (e["time"] != "", e["time"], -PRIORITIES.index(e["priority"]),
                                e["title"].lower()))
        return evs

    def upcoming(self, start, days, keep=None):
        out = []
        for i in range(days):
            d = start + dt.timedelta(i)
            out += [(d, e) for e in self.events_on(d, keep) if not self.is_done(e, d)]
        return out

    # ---- days & settings -----------------------------------------------------
    def day(self, d):
        return self.days.get(d.isoformat(), {"status": "Normal", "note": ""})

    def set_day(self, d, status, note):
        self.days[d.isoformat()] = {"status": status if status in DAY_STATUSES else "Normal",
                                    "note": note}

    def today(self):
        try:
            return parse_date(self.settings["story_today"])
        except ValueError:
            return dt.date.today()

    def week_start(self):
        return WEEK_STARTS.get(self.settings.get("week_start", "Monday"), 0)

    def day_counter(self):
        try:
            sealed = parse_date(self.settings["sealed_on"])
        except ValueError:
            return ""
        n = (self.today() - sealed).days
        return f"Day {n + 1:,} underground" if n >= 0 else f"Sealing in {-n:,} days"


# ----------------------------------------------------------------------------- widgets
class FlatButton(tk.Label):
    """A label that acts as a button, so the dark colours also work on macOS (tk.Button ignores
    bg there)."""

    def __init__(self, parent, text, command, bg=FIELD_BG, fg=TEXT, hover=BORDER, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, cursor="hand2", padx=10, pady=4,
                         font=(FONT, 10, "bold"), **kw)
        self._bg, self._hover, self.command = bg, hover, command
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))

    def _click(self, e):
        # only fire if the mouse is still over the button when released
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self.command()


def make_entry(parent, width=24):
    return tk.Entry(parent, width=width, bg=FIELD_BG, fg=TEXT, insertbackground=TEXT, relief="flat",
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                    font=(FONT, 11))


def make_text(parent, height):
    return tk.Text(parent, height=height, wrap="word", bg=FIELD_BG, fg=TEXT, insertbackground=TEXT,
                   relief="flat", highlightthickness=1, highlightbackground=BORDER,
                   highlightcolor=ACCENT, font=(FONT, 11), padx=6, pady=4, undo=True)


def make_listbox(parent, height):
    return tk.Listbox(parent, height=height, bg=FIELD_BG, fg=TEXT, selectbackground=BORDER,
                      selectforeground=TEXT, highlightthickness=0, relief="flat", activestyle="none",
                      font=(FONT, 10), exportselection=False)


def section(parent, text):
    tk.Label(parent, text=text, bg=PANEL_BG, fg=MUTED, font=(FONT, 9, "bold"),
             anchor="w").pack(fill="x", padx=14, pady=(12, 3))


def setup_style(root):
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TCombobox", fieldbackground=FIELD_BG, background=FIELD_BG, foreground=TEXT,
                    arrowcolor=TEXT, bordercolor=BORDER, lightcolor=FIELD_BG, darkcolor=FIELD_BG)
    style.map("TCombobox",
              fieldbackground=[("readonly", FIELD_BG), ("disabled", PANEL_BG)],
              foreground=[("readonly", TEXT), ("disabled", DIM)],
              selectbackground=[("readonly", FIELD_BG)], selectforeground=[("readonly", TEXT)])
    style.configure("Vertical.TScrollbar", background=FIELD_BG, troughcolor=PANEL_BG,
                    bordercolor=PANEL_BG, arrowcolor=MUTED, lightcolor=FIELD_BG, darkcolor=FIELD_BG)
    root.option_add("*TCombobox*Listbox.background", FIELD_BG)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", BORDER)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)


def grab(win):
    """grab_set fails if the window isn't viewable yet on some window managers: retry shortly."""
    try:
        win.grab_set()
    except tk.TclError:
        win.after(30, lambda: grab(win) if win.winfo_exists() else None)


def place_over(win, parent):
    win.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_reqwidth()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_reqheight()) // 3
    win.geometry(f"+{max(0, x)}+{max(0, y)}")


# ----------------------------------------------------------------------------- dialogs
class Dialog(tk.Toplevel):
    """Modal dialog base: dark frame, error line, Escape = cancel. self.result is set on save."""

    def __init__(self, root, title):
        super().__init__(root)
        self.root_win, self.result = root, None
        self.title(title)
        self.configure(bg=PANEL_BG)
        self.transient(root)
        self.resizable(False, False)
        self.form = tk.Frame(self, bg=PANEL_BG, padx=18, pady=14)
        self.form.pack(fill="both", expand=True)
        self.error = tk.Label(self, bg=PANEL_BG, fg=RED, font=(FONT, 10), anchor="w", justify="left",
                              wraplength=440)
        self.buttons = tk.Frame(self, bg=PANEL_BG, padx=18, pady=12)
        self.bind("<Escape>", lambda e: self.destroy())

    def field(self, row, label, widget, hint=""):
        tk.Label(self.form, text=label, bg=PANEL_BG, fg=MUTED, font=(FONT, 10),
                 anchor="w").grid(row=row, column=0, sticky="nw", pady=4, padx=(0, 12))
        widget.grid(row=row, column=1, sticky="we", pady=4)
        if hint:
            tk.Label(self.form, text=hint, bg=PANEL_BG, fg=DIM, font=(FONT, 9),
                     anchor="w").grid(row=row, column=2, sticky="w", padx=(8, 0))

    def finish_layout(self, focus):
        self.error.pack(fill="x", padx=18)
        self.buttons.pack(fill="x")
        place_over(self, self.root_win)
        grab(self)
        focus.focus_set()

    def fail(self, msg):
        self.error.config(text=msg)


class EventDialog(Dialog):
    def __init__(self, root, ev=None, day=None, copy=False):
        editing = ev is not None and not copy
        super().__init__(root, "Edit event" if editing else "New event")
        ev = ev or {}
        f = self.form
        self.title_e = make_entry(f, 34)
        self.date_e = make_entry(f, 12)
        self.time_e = make_entry(f, 8)
        self.cat = ttk.Combobox(f, values=list(CATEGORIES), state="readonly", width=16)
        self.pri = ttk.Combobox(f, values=PRIORITIES, state="readonly", width=16)
        self.loc_e = make_entry(f, 34)
        rep_row = tk.Frame(f, bg=PANEL_BG)
        self.rep = ttk.Combobox(rep_row, values=REPEATS, state="readonly", width=10)
        self.rep.pack(side="left")
        tk.Label(rep_row, text="  every", bg=PANEL_BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        self.every = tk.Spinbox(rep_row, from_=1, to=365, width=4, bg=FIELD_BG, fg=TEXT,
                                buttonbackground=FIELD_BG, insertbackground=TEXT, relief="flat",
                                disabledbackground=PANEL_BG, disabledforeground=DIM, font=(FONT, 11))
        self.every.pack(side="left", padx=6)
        self.unit = tk.Label(rep_row, bg=PANEL_BG, fg=MUTED, font=(FONT, 10), width=9, anchor="w")
        self.unit.pack(side="left")
        self.until_e = make_entry(f, 12)
        self.notes = make_text(f, 5)

        self.field(0, "Title", self.title_e)
        self.field(1, "Date", self.date_e, "YYYY-MM-DD")
        self.field(2, "Time", self.time_e, "HH:MM, empty = all day")
        self.field(3, "Category", self.cat)
        self.field(4, "Priority", self.pri)
        self.field(5, "Level / place", self.loc_e)
        self.field(6, "Repeat", rep_row)
        self.field(7, "Repeat until", self.until_e, "empty = forever")
        self.field(8, "Notes", self.notes)
        if editing and ev.get("repeat", "None") != "None":
            tk.Label(f, text="Changes apply to every repeat of this event.", bg=PANEL_BG, fg=AMBER,
                     font=(FONT, 9)).grid(row=9, column=1, sticky="w")

        self.title_e.insert(0, ev.get("title", ""))
        self.date_e.insert(0, ev.get("date") or (day or dt.date.today()).isoformat())
        self.time_e.insert(0, ev.get("time", ""))
        self.cat.set(ev.get("category", "Other"))
        self.pri.set(ev.get("priority", "Normal"))
        self.loc_e.insert(0, ev.get("location", ""))
        self.rep.set(ev.get("repeat", "None"))
        self.every.delete(0, "end")
        self.every.insert(0, str(ev.get("interval", 1)))
        self.until_e.insert(0, ev.get("until", ""))
        self.notes.insert("1.0", ev.get("notes", ""))
        self.rep.bind("<<ComboboxSelected>>", lambda e: self._repeat_changed())
        self._repeat_changed()

        FlatButton(self.buttons, "Save", self.save, bg=ACCENT, fg="#0b1220", hover="#a5d7ff").pack(side="right")
        FlatButton(self.buttons, "Cancel", self.destroy).pack(side="right", padx=8)
        if editing:
            FlatButton(self.buttons, "Delete", self.delete, fg=RED).pack(side="left")
        self.bind("<Return>", self._enter)
        self.finish_layout(self.title_e)

    def _repeat_changed(self):
        on = self.rep.get() != "None"
        self.every.config(state="normal" if on else "disabled")
        self.until_e.config(state="normal" if on else "disabled",
                            disabledbackground=PANEL_BG, disabledforeground=DIM)
        self.unit.config(text=REPEAT_UNIT[self.rep.get()])

    def _enter(self, e):
        if e.widget is not self.notes:         # Enter in the notes box is a new line
            self.save()

    def save(self):
        try:
            title = self.title_e.get().strip()
            if not title:
                raise ValueError("Give the event a title.")
            start = parse_date(self.date_e.get())
            time = parse_time(self.time_e.get())
            repeat = self.rep.get()
            interval, until = 1, ""
            if repeat != "None":
                try:
                    interval = int(self.every.get())
                except ValueError:
                    raise ValueError("'Every' must be a whole number.") from None
                if not 1 <= interval <= 365:
                    raise ValueError("'Every' must be between 1 and 365.")
                if self.until_e.get().strip():
                    u = parse_date(self.until_e.get())
                    if u < start:
                        raise ValueError("'Repeat until' is before the start date.")
                    until = u.isoformat()
        except ValueError as e:
            self.fail(str(e))
            return
        self.result = {
            "title": title, "date": start.isoformat(), "time": time, "category": self.cat.get(),
            "priority": self.pri.get(), "location": self.loc_e.get().strip(), "repeat": repeat,
            "interval": interval, "until": until, "notes": self.notes.get("1.0", "end-1c").rstrip(),
        }
        self.destroy()

    def delete(self):
        self.result = "delete"
        self.destroy()


class SettingsDialog(Dialog):
    def __init__(self, root, settings):
        super().__init__(root, "Calendar settings")
        self.sealed_e = make_entry(self.form, 12)
        self.story_e = make_entry(self.form, 12)
        self.week = ttk.Combobox(self.form, values=list(WEEK_STARTS), state="readonly", width=10)
        self.field(0, "Sealed underground on", self.sealed_e, "starts the day counter; empty = none")
        self.field(1, "Story 'today'", self.story_e, "in-world date, e.g. 2087-03-14; empty = real date")
        self.field(2, "Weeks start on", self.week)
        self.sealed_e.insert(0, settings.get("sealed_on", ""))
        self.story_e.insert(0, settings.get("story_today", ""))
        self.week.set(settings.get("week_start", "Monday"))
        FlatButton(self.buttons, "Save", self.save, bg=ACCENT, fg="#0b1220", hover="#a5d7ff").pack(side="right")
        FlatButton(self.buttons, "Cancel", self.destroy).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.save())
        self.finish_layout(self.sealed_e)

    def save(self):
        out = {"week_start": self.week.get()}
        for key, entry in (("sealed_on", self.sealed_e), ("story_today", self.story_e)):
            text = entry.get().strip()
            try:
                out[key] = parse_date(text).isoformat() if text else ""
            except ValueError as e:
                self.fail(str(e))
                return
        self.result = out
        self.destroy()


# ----------------------------------------------------------------------------- main window
class SurvivalCalendarApp:
    def __init__(self, root, store):
        self.root, self.store = root, store
        today = store.today()
        self.view = today.replace(day=1)        # first day of the month on screen
        self.selected = today
        self.day_ids = []                       # event ids in the day list, in order
        self.upcoming_items = []                # (date, event id) in the upcoming list
        self._note_day = None                   # day whose log is in the note box
        self._redraw_job = None
        self._last_width = 0
        self.query = tk.StringVar()
        self.cat_filter = tk.StringVar(value=ALL_CATEGORIES)

        root.title("The Hollow - Survival Calendar")
        root.minsize(1040, 660)
        self._build_header()
        self._build_toolbar()
        self.status = tk.Label(root, bg=BG, fg=MUTED, anchor="w", font=(FONT, 9))
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 6))
        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(4, 6))
        self.side = tk.Frame(body, bg=PANEL_BG, width=380)
        self.side.pack(side="right", fill="y", padx=(10, 0))
        self.side.pack_propagate(False)
        self.grid_frame = tk.Frame(body, bg=BG, takefocus=True)
        self.grid_frame.pack(side="left", fill="both", expand=True)
        self._build_grid()
        self._build_side()
        self._bind_keys()

        self.query.trace_add("write", lambda *a: self._schedule_redraw(250))
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        self.flash(store.warning or f"Calendar file: {store.path}", RED if store.warning else MUTED)

    # ---- layout --------------------------------------------------------------
    def _build_header(self):
        head = tk.Frame(self.root, bg=BG)
        head.pack(side="top", fill="x", padx=14, pady=(10, 2))
        tk.Label(head, text="THE HOLLOW  |  SURVIVAL CALENDAR", bg=BG, fg=MUTED,
                 font=(FONT, 11, "bold")).pack(side="left")
        FlatButton(head, "Settings", self.open_settings).pack(side="right")
        self.today_lbl = tk.Label(head, bg=BG, fg=TEXT, font=(FONT, 11))
        self.today_lbl.pack(side="right", padx=14)
        self.counter_lbl = tk.Label(head, bg=BG, fg=AMBER, font=(FONT, 11, "bold"))
        self.counter_lbl.pack(side="right")

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(side="top", fill="x", padx=12, pady=(6, 4))
        for text, n in (("«", -12), ("‹", -1)):
            FlatButton(bar, text, lambda n=n: self.shift_month(n)).pack(side="left", padx=2)
        self.month_lbl = tk.Label(bar, bg=BG, fg=TEXT, font=(FONT, 18, "bold"), width=14)
        self.month_lbl.pack(side="left", padx=4)
        for text, n in (("›", 1), ("»", 12)):
            FlatButton(bar, text, lambda n=n: self.shift_month(n)).pack(side="left", padx=2)
        FlatButton(bar, "Today", self.go_today).pack(side="left", padx=(10, 0))

        FlatButton(bar, "+ New event", lambda: self.new_event(), bg=ACCENT, fg="#0b1220",
                   hover="#a5d7ff").pack(side="right")
        cat = ttk.Combobox(bar, textvariable=self.cat_filter, state="readonly", width=15,
                           values=[ALL_CATEGORIES] + list(CATEGORIES))
        cat.pack(side="right", padx=10)
        cat.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.search_e = make_entry(bar, 18)
        self.search_e.config(textvariable=self.query)
        self.search_e.pack(side="right")
        self.search_e.bind("<Escape>", lambda e: self.query.set(""))
        tk.Label(bar, text="Search", bg=BG, fg=MUTED, font=(FONT, 10)).pack(side="right", padx=6)

    def _build_grid(self):
        g = self.grid_frame
        self.weekday_lbls = []
        for c in range(7):
            lbl = tk.Label(g, bg=BG, fg=MUTED, font=(FONT, 9, "bold"))
            lbl.grid(row=0, column=c, sticky="ew", pady=(0, 3))
            self.weekday_lbls.append(lbl)
            g.grid_columnconfigure(c, weight=1, uniform="col")
        for r in range(1, 7):
            g.grid_rowconfigure(r, weight=1, uniform="row")
        self.cells = []
        for i in range(42):
            r, c = divmod(i, 7)
            frame = tk.Frame(g, bg=CELL_BG, width=100, height=96, highlightthickness=2,
                             highlightbackground=BG, highlightcolor=BG)
            frame.grid(row=r + 1, column=c, sticky="nsew", padx=2, pady=2)
            frame.pack_propagate(False)
            top = tk.Frame(frame, bg=CELL_BG)
            top.pack(fill="x", padx=5, pady=(3, 1))
            num = tk.Label(top, bg=CELL_BG, fg=TEXT, font=(FONT, 11, "bold"), anchor="w")
            num.pack(side="left")
            tag = tk.Label(top, bg=CELL_BG, fg=MUTED, font=(FONT, 8, "bold"), anchor="e")
            tag.pack(side="right")
            chips = [tk.Label(frame, anchor="w", font=(FONT, 9), padx=4) for _ in range(MAX_CHIPS)]
            more = tk.Label(frame, bg=CELL_BG, fg=MUTED, font=(FONT, 8), anchor="w")
            cell = {"frame": frame, "top": top, "num": num, "tag": tag, "chips": chips, "more": more,
                    "date": None, "ids": [], "shown": -1}
            self.cells.append(cell)
            for w in (frame, top, num, tag, more):
                w.bind("<Button-1>", lambda e, i=i: self._cell_click(i))
                w.bind("<Double-Button-1>", lambda e, i=i: self.new_event(self.cells[i]["date"]))
            for j, chip in enumerate(chips):
                chip.bind("<Button-1>", lambda e, i=i, j=j: self._cell_click(i, j))
                chip.bind("<Double-Button-1>", lambda e, i=i, j=j: self._chip_edit(i, j))
        g.bind("<Configure>", self._grid_resized)

    def _build_side(self):
        s = self.side
        self.date_lbl = tk.Label(s, bg=PANEL_BG, fg="white", font=(FONT, 15, "bold"), anchor="w")
        self.date_lbl.pack(fill="x", padx=14, pady=(14, 0))
        self.rel_lbl = tk.Label(s, bg=PANEL_BG, fg=MUTED, font=(FONT, 10), anchor="w")
        self.rel_lbl.pack(fill="x", padx=14)

        row = tk.Frame(s, bg=PANEL_BG)
        row.pack(fill="x", padx=14, pady=(10, 0))
        tk.Label(row, text="Day status", bg=PANEL_BG, fg=MUTED, font=(FONT, 10)).pack(side="left")
        self.status_cb = ttk.Combobox(row, values=list(DAY_STATUSES), state="readonly", width=12)
        self.status_cb.pack(side="left", padx=8)
        self.status_cb.bind("<<ComboboxSelected>>", lambda e: self._status_changed())

        section(s, "DAY LOG")
        self.note = make_text(s, 4)
        self.note.pack(fill="x", padx=14)
        self.note.bind("<FocusOut>", lambda e: self._commit_note())

        self.events_hdr = tk.Label(s, bg=PANEL_BG, fg=MUTED, font=(FONT, 9, "bold"), anchor="w")
        self.events_hdr.pack(fill="x", padx=14, pady=(12, 3))
        self.day_list = make_listbox(s, 7)
        self.day_list.pack(fill="x", padx=14)
        self.day_list.bind("<<ListboxSelect>>", lambda e: self._show_details())
        self.day_list.bind("<Double-Button-1>", lambda e: self.edit_selected())
        btns = tk.Frame(s, bg=PANEL_BG)
        btns.pack(fill="x", padx=14, pady=6)
        for text, cmd in (("+ Add", lambda: self.new_event(self.selected)), ("Edit", self.edit_selected),
                          ("Done", self.toggle_done), ("Copy", self.copy_selected),
                          ("Delete", self.delete_selected)):
            FlatButton(btns, text, cmd).pack(side="left", padx=(0, 5))
        self.detail = tk.Label(s, bg=PANEL_BG, fg=TEXT, font=(FONT, 10), anchor="w", justify="left",
                               wraplength=350)
        self.detail.pack(fill="x", padx=14)

        section(s, f"UPCOMING  ·  NEXT {UPCOMING_DAYS} DAYS")
        up = tk.Frame(s, bg=PANEL_BG)
        up.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.up_list = make_listbox(up, 8)
        sb = ttk.Scrollbar(up, orient="vertical", command=self.up_list.yview)
        self.up_list.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.up_list.pack(side="left", fill="both", expand=True)
        self.up_list.bind("<<ListboxSelect>>", lambda e: self._upcoming_pick(edit=False))
        self.up_list.bind("<Double-Button-1>", lambda e: self._upcoming_pick(edit=True))

    def _bind_keys(self):
        r = self.root
        for key, days in (("<Left>", -1), ("<Right>", 1), ("<Up>", -7), ("<Down>", 7)):
            r.bind(key, lambda e, d=days: self._key(e, lambda: self.select_day(self.selected + dt.timedelta(d))))
        r.bind("<Prior>", lambda e: self._key(e, lambda: self.shift_month(-1)))
        r.bind("<Next>", lambda e: self._key(e, lambda: self.shift_month(1)))
        r.bind("<Key-t>", lambda e: self._key(e, self.go_today))
        r.bind("<Return>", lambda e: self._key(e, self.edit_selected, lists_ok=True))
        r.bind("<space>", lambda e: self._key(e, self.toggle_done, lists_ok=True))
        r.bind("<Delete>", lambda e: self._key(e, self.delete_selected, lists_ok=True))
        r.bind("<Control-n>", lambda e: self.new_event())
        r.bind("<Control-f>", lambda e: (self.search_e.focus_set(), self.search_e.select_range(0, "end")))

    def _key(self, e, action, lists_ok=False):
        """Run a shortcut unless the user is typing in a field (or using a list's own keys)."""
        typing = (tk.Entry, tk.Text, tk.Spinbox, ttk.Combobox, ttk.Entry)
        if isinstance(e.widget, typing) or (isinstance(e.widget, tk.Listbox) and not lists_ok):
            return None
        action()
        return "break"

    # ---- drawing -------------------------------------------------------------
    def refresh(self):
        self._draw_header()
        self._draw_month()
        self._draw_side()

    def _schedule_redraw(self, ms=60):
        if self._redraw_job:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(ms, self._redraw_now)

    def _redraw_now(self):
        self._redraw_job = None
        self.refresh()

    def _grid_resized(self, e):
        if abs(e.width - self._last_width) > 6:           # chip text length depends on width
            self._last_width = e.width
            self._schedule_redraw()

    def _filter(self):
        q, cat = self.query.get().strip().lower(), self.cat_filter.get()
        if not q and cat == ALL_CATEGORIES:
            return None

        def keep(ev):
            if cat != ALL_CATEGORIES and ev["category"] != cat:
                return False
            return not q or q in f"{ev['title']} {ev['location']} {ev['notes']}".lower()
        return keep

    def _draw_header(self):
        today = self.store.today()
        story = " (story date)" if self.store.settings.get("story_today") else ""
        self.today_lbl.config(text=today.strftime("%a %d %b %Y") + story)
        self.counter_lbl.config(text=self.store.day_counter())
        ws = self.store.week_start()
        for c, lbl in enumerate(self.weekday_lbls):
            lbl.config(text=calendar.day_abbr[(ws + c) % 7].upper())

    def _draw_month(self):
        self.month_lbl.config(text=self.view.strftime("%B %Y"))
        first = self.view
        start = first - dt.timedelta(days=(first.weekday() - self.store.week_start()) % 7)
        today, keep = self.store.today(), self._filter()
        width = self.cells[0]["frame"].winfo_width()
        chars = max(6, (width - 12) // 6) if width > 20 else 16
        for i, cell in enumerate(self.cells):
            d = start + dt.timedelta(i)
            cell["date"] = d
            in_month = d.month == first.month
            selected = d == self.selected
            bg = CELL_SEL if selected else (CELL_BG if in_month else CELL_OUT_BG)
            info = self.store.day(d)
            status_col = DAY_STATUSES.get(info["status"], "")
            border = ACCENT if selected else (status_col or BG)
            cell["frame"].config(bg=bg, highlightbackground=border, highlightcolor=border)
            cell["top"].config(bg=bg)
            num_fg = AMBER if d == today else (TEXT if in_month else DIM)
            cell["num"].config(bg=bg, fg=num_fg, text=f"{d.day}  today" if d == today else str(d.day))
            tag = info["status"].upper() if status_col else ""
            if info["note"].strip():
                tag = (tag + " ✎").strip()
            cell["tag"].config(bg=bg, fg=status_col or MUTED, text=tag)

            evs = self.store.events_on(d, keep)
            cell["ids"] = [e["id"] for e in evs]
            show = evs[:MAX_CHIPS]
            for chip, ev in zip(cell["chips"], show):
                done = self.store.is_done(ev, d)
                colour = CATEGORIES.get(ev["category"], CATEGORIES["Other"])
                label = PRIORITY_MARK[ev["priority"]] + (f"{ev['time']} " if ev["time"] else "") + ev["title"]
                if done:
                    label = "✓ " + label
                if len(label) > chars:
                    label = label[:chars - 1] + "…"
                chip.config(text=label, bg=CHIP_DONE if done else colour,
                            fg=DIM if done else text_on(colour))
            extra = len(evs) - len(show)
            cell["more"].config(bg=bg, text=f"+{extra} more" if extra > 0 else "")
            n_shown = len(show) + (1 if extra > 0 else 0)
            if n_shown != cell["shown"]:                     # re-pack only when the count changes
                for w in cell["chips"] + [cell["more"]]:
                    w.pack_forget()
                for chip in cell["chips"][:len(show)]:
                    chip.pack(fill="x", padx=5, pady=1)
                if extra > 0:
                    cell["more"].pack(fill="x", padx=6)
                cell["shown"] = n_shown

    def _draw_side(self):
        d, today = self.selected, self.store.today()
        self.date_lbl.config(text=d.strftime("%A %d %B %Y"))
        self.rel_lbl.config(text=relative_day(d, today).capitalize())
        info = self.store.day(d)
        self.status_cb.set(info["status"])
        if self._note_day != d:                       # don't wipe text the user is typing
            self.note.delete("1.0", "end")
            self.note.insert("1.0", info["note"])
            self.note.edit_reset()
            self._note_day = d

        keep = self._filter()
        prev = self._selected_event_id()
        evs = self.store.events_on(d, keep)
        self.events_hdr.config(text=f"EVENTS ({len(evs)})" + ("  ·  filtered" if keep else ""))
        self.day_ids = [e["id"] for e in evs]
        self.day_list.delete(0, "end")
        for i, ev in enumerate(evs):
            done = self.store.is_done(ev, d)
            rep = " ↻" if ev["repeat"] != "None" else ""
            where = f"  [{ev['location']}]" if ev["location"] else ""
            line = (f"{'✓' if done else '•'} {ev['time'] or 'All day':>7}  "
                    f"{PRIORITY_MARK[ev['priority']]}{ev['title']}{rep}{where}")
            self.day_list.insert("end", line)
            fg = DIM if done else (RED if ev["priority"] == "Critical"
                                   else CATEGORIES.get(ev["category"], TEXT))
            self.day_list.itemconfig(i, fg=fg, selectforeground=fg)
        if not evs:
            self.day_list.insert("end", "  Nothing planned. Double-click a day or press + Add.")
            self.day_list.itemconfig(0, fg=DIM, selectforeground=DIM)
        if prev in self.day_ids:
            self.select_event(prev)
        self._show_details()

        # rebuild the upcoming list but keep its selection (a double-click's first click refreshes)
        sel = self.up_list.curselection()
        prev_up = self.upcoming_items[sel[0]] if sel and sel[0] < len(self.upcoming_items) else None
        self.upcoming_items = []
        self.up_list.delete(0, "end")
        for day, ev in self.store.upcoming(today, UPCOMING_DAYS, keep):
            when = "Today" if day == today else ("Tomorrow" if day == today + dt.timedelta(1)
                                                else day.strftime("%a %d %b"))
            self.up_list.insert("end", f"{when:<11}{ev['time'] or 'all day':>8}  "
                                       f"{PRIORITY_MARK[ev['priority']]}{ev['title']}")
            fg = RED if ev["priority"] == "Critical" else CATEGORIES.get(ev["category"], TEXT)
            self.up_list.itemconfig(len(self.upcoming_items), fg=fg, selectforeground=fg)
            self.upcoming_items.append((day, ev["id"]))
        if not self.upcoming_items:
            self.up_list.insert("end", "  Nothing coming up.")
            self.up_list.itemconfig(0, fg=DIM, selectforeground=DIM)
        elif prev_up in self.upcoming_items:
            i = self.upcoming_items.index(prev_up)
            self.up_list.selection_set(i)
            self.up_list.see(i)

    def _show_details(self):
        eid = self._selected_event_id()
        if not eid:
            self.detail.config(text="")
            return
        ev = self.store.events[eid]
        parts = [ev["category"], f"{ev['priority']} priority", repeat_text(ev)]
        text = "  ·  ".join(parts)
        if ev["location"]:
            text += f"\nWhere: {ev['location']}"
        if ev["notes"]:
            text += f"\n{ev['notes']}"
        self.detail.config(text=text)

    def flash(self, text, colour=MUTED):
        self.status.config(text=text, fg=colour)

    # ---- selection & navigation ----------------------------------------------
    def select_day(self, d, event_id=None):
        if d == self.selected and event_id is None:
            return
        self._commit_note()
        self.selected = d
        if (d.year, d.month) != (self.view.year, self.view.month):
            self.view = d.replace(day=1)
        self.refresh()
        if event_id:
            self.select_event(event_id)

    def select_event(self, eid):
        if eid in self.day_ids:
            i = self.day_ids.index(eid)
            self.day_list.selection_clear(0, "end")
            self.day_list.selection_set(i)
            self.day_list.see(i)
            self._show_details()

    def _selected_event_id(self):
        sel = self.day_list.curselection()
        if sel and sel[0] < len(self.day_ids):
            return self.day_ids[sel[0]]
        return None

    def shift_month(self, n):
        y, m = divmod(self.view.year * 12 + self.view.month - 1 + n, 12)
        if not 1 <= y <= 9999:
            return
        last = calendar.monthrange(y, m + 1)[1]
        self.select_day(dt.date(y, m + 1, min(self.selected.day, last)))

    def go_today(self):
        self.select_day(self.store.today())

    def _cell_click(self, i, chip=None):
        self.grid_frame.focus_set()                      # so the arrow keys move the selection
        ids = self.cells[i]["ids"]
        eid = ids[chip] if chip is not None and chip < len(ids) else None
        if self.cells[i]["date"] == self.selected and eid:
            self.select_event(eid)
        else:
            self.select_day(self.cells[i]["date"], eid)

    def _chip_edit(self, i, j):
        ids = self.cells[i]["ids"]
        if j < len(ids):
            self.edit_event(ids[j], self.cells[i]["date"])

    def _upcoming_pick(self, edit):
        sel = self.up_list.curselection()
        if not sel or sel[0] >= len(self.upcoming_items):
            return
        day, eid = self.upcoming_items[sel[0]]
        self.select_day(day, eid)
        self.select_event(eid)
        if edit:
            self.edit_event(eid, day)

    # ---- actions -------------------------------------------------------------
    def persist(self, what="Saved"):
        try:
            self.store.save()
            self.flash(f"{what}  ·  {dt.datetime.now():%H:%M:%S}", GREEN)
        except OSError as e:
            self.flash(f"Could not save: {e}", RED)

    def _run_dialog(self, dialog):
        self.root.wait_window(dialog)
        return dialog.result

    def new_event(self, day=None, template=None):
        result = self._run_dialog(EventDialog(self.root, ev=template, day=day or self.selected,
                                              copy=template is not None))
        if isinstance(result, dict):
            eid = self.store.add_event(result)
            self.persist(f"Added '{result['title']}'")
            self._commit_note()
            self.select_day(parse_date(result["date"]), eid)
            self.refresh()
            self.select_event(eid)

    def edit_event(self, eid, day):
        ev = self.store.events.get(eid)
        if not ev:
            return
        result = self._run_dialog(EventDialog(self.root, ev=ev, day=day))
        if result == "delete":
            self._delete(eid, day)
        elif isinstance(result, dict):
            self.store.update_event(eid, result)
            self.persist(f"Updated '{result['title']}'")
            ev = self.store.events[eid]
            target = day if self.store.occurs_on(ev, day) else ev["_start"]
            self.select_day(target, eid)
            self.refresh()
            self.select_event(eid)

    def edit_selected(self):
        eid = self._selected_event_id()
        if eid:
            self.edit_event(eid, self.selected)

    def copy_selected(self):
        eid = self._selected_event_id()
        if eid:
            template = dict(self.store.events[eid], date=self.selected.isoformat())
            template["title"] += " (copy)"
            self.new_event(self.selected, template)

    def toggle_done(self):
        eid = self._selected_event_id()
        if not eid:
            return
        done = self.store.toggle_done(eid, self.selected)
        self.persist(("Ticked off" if done else "Un-ticked") + f" '{self.store.events[eid]['title']}'")
        self.refresh()
        self.select_event(eid)

    def delete_selected(self):
        eid = self._selected_event_id()
        if eid:
            self._delete(eid, self.selected)

    def _delete(self, eid, day):
        ev = self.store.events.get(eid)
        if not ev:
            return
        if ev["repeat"] != "None":
            answer = messagebox.askyesnocancel(
                "Delete repeating event",
                f"'{ev['title']}' repeats ({repeat_text(ev).lower()}).\n\n"
                f"Yes: remove only {day:%a %d %b %Y}\nNo: delete every repeat\nCancel: keep it",
                parent=self.root)
            if answer is None:
                return
            if answer:
                self.store.skip_occurrence(eid, day)
                self.persist(f"Removed '{ev['title']}' on {day:%d %b}")
                self.refresh()
                return
        elif not messagebox.askyesno("Delete event", f"Delete '{ev['title']}'?", parent=self.root):
            return
        self.store.delete_event(eid)
        self.persist(f"Deleted '{ev['title']}'")
        self.refresh()

    def _status_changed(self):
        self.store.set_day(self.selected, self.status_cb.get(), self.note.get("1.0", "end-1c"))
        self.persist(f"{self.selected:%d %b} marked {self.status_cb.get()}")
        self.refresh()

    def _commit_note(self):
        d = self._note_day
        if d is None:
            return
        text = self.note.get("1.0", "end-1c").rstrip()
        info = self.store.day(d)
        if text != info["note"]:
            self.store.set_day(d, info["status"], text)
            self.persist(f"Saved log for {d:%d %b}")
            self._draw_month()

    def open_settings(self):
        result = self._run_dialog(SettingsDialog(self.root, self.store.settings))
        if isinstance(result, dict):
            self.store.settings.update(result)
            self.persist("Settings saved")
            self._commit_note()
            self.selected = self.store.today()
            self.view = self.selected.replace(day=1)
            self.refresh()

    def on_close(self):
        self._commit_note()
        self.root.destroy()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="The Hollow - survival calendar")
    ap.add_argument("--file", default=os.path.join(here, "survival_calendar.json"),
                    help="calendar file to open or create (default: survival_calendar.json next to this script)")
    ap.add_argument("--empty", action="store_true", help="start a new calendar without the sample events")
    args = ap.parse_args()

    store = CalendarStore(args.file, seed=not args.empty)
    root = tk.Tk()
    root.geometry("1280x%d" % min(820, root.winfo_screenheight() - 80))
    setup_style(root)
    SurvivalCalendarApp(root, store)
    root.mainloop()


if __name__ == "__main__":
    main()