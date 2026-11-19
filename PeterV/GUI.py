"""
The Hollow - level monitor GUI (tkinter), wired to your real code.

Put this file in the same folder as Hpeople.py, HollowEvents.py and simulation.py.

    python hollow_gui.py                      # 1,000,000 residents
    python hollow_gui.py --residents 100000   # faster startup / flushes
    python hollow_gui.py --speed 1800         # simulated seconds per real second

The GUI drives HollowClock.step() itself (once per real second) and reads the
same tables the console report uses. Nothing here touches residents per tick.
"""
import argparse
import time
import tkinter as tk

from HollowEvents import EVENT_TYPES
from Hpeople import NUM_RESIDENTS, SYSTEM_TYPES, build_database, level_dashboard, system_matrix
from simulation import SIM_SECONDS_PER_TICK, TICK_SECONDS, HollowClock, format_clock

# ------------------------------------------------------------------- colors
# worst system on a level: 100 -> blue, 75 -> yellow, 40 (or lower) -> red
STOPS = [(40, (214, 48, 49)), (75, (245, 196, 40)), (100, (52, 132, 240))]


def severity_color(v):
    v = max(STOPS[0][0], min(STOPS[-1][0], v))
    for (v0, c0), (v1, c1) in zip(STOPS, STOPS[1:]):
        if v <= v1:
            f = (v - v0) / (v1 - v0)
            return tuple(c0[i] + (c1[i] - c0[i]) * f for i in range(3))
    return STOPS[-1][1]


def hexc(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c)) for c in rgb)


def text_on(rgb):
    return "#111111" if 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 150 else "#ffffff"


def pretty(s):
    return s.replace("_", " ").title()


BG, PANEL_BG, MUTED, TEXT = "#14161c", "#1d2029", "#9aa3b5", "#dfe4ee"
ROW_H, GAP, VISIBLE, LIST_W, PANEL_W = 100, 8, 5, 540, 380
RED, AMBER = "#ff7b72", "#f2c94c"


class HollowApp:
    def __init__(self, root, con, clock):
        self.root, self.con, self.clock = root, con, clock
        self.selected = None
        self.state, self.items, self.shown = {}, {}, {}
        self.avg_health = None
        self.ticker = "Simulation running"
        self.systems = [s[0] for s in SYSTEM_TYPES]

        root.title("The Hollow - Level Monitor")
        root.configure(bg=BG)

        # header
        head = tk.Frame(root, bg=BG)
        head.pack(side="top", fill="x", padx=12, pady=(10, 0))
        tk.Label(head, text="THE HOLLOW  |  2087", bg=BG, fg=MUTED,
                 font=("Helvetica", 11, "bold")).pack(side="left")
        self.clock_lbl = tk.Label(head, bg=BG, fg=TEXT, font=("Helvetica", 11, "bold"))
        self.clock_lbl.pack(side="right")
        self.alive_lbl = tk.Label(head, bg=BG, fg=TEXT, font=("Helvetica", 11))
        self.alive_lbl.pack(side="right", padx=18)
        self.ticker_lbl = tk.Label(root, bg=BG, fg=AMBER, anchor="w", font=("Helvetica", 10))
        self.ticker_lbl.pack(side="bottom", fill="x", padx=12, pady=(0, 8))

        # scrollable level list
        left = tk.Frame(root, bg=BG)
        left.pack(side="left", fill="y", padx=12, pady=10)
        self.canvas = tk.Canvas(left, width=LIST_W, height=VISIBLE * (ROW_H + GAP),
                                bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(left, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left")
        sb.pack(side="left", fill="y")
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind_all(ev, self._wheel)

        self.panel = tk.Frame(root, bg=PANEL_BG, width=PANEL_W)
        self.panel.pack_propagate(False)       # only shown once a level is clicked

        self.snapshot()
        for lvl in sorted(self.state):
            self._build_row(lvl)
        self.canvas.configure(scrollregion=(0, 0, LIST_W, len(self.state) * (ROW_H + GAP)))
        self._build_panel()
        self.refresh()
        self.loop()
        self.animate()

    # ------------------------------------------------------------- data
    def snapshot(self):
        dash = {r["level"]: dict(r) for r in level_dashboard(self.con)}
        matrix = system_matrix(self.con)
        ev = self.clock.events
        for lvl, d in dash.items():
            systems = matrix.get(lvl, {})
            st = []
            for left, et, l in ev.pending:
                if l == lvl:
                    st.append((f"Incoming: {pretty(et.name)} in {left}s", AMBER))
            for left, et, l in ev.active:
                if l == lvl:
                    st.append((f"Ongoing: {pretty(et.name)} ({left}s left)", RED))
            for name in self.systems:
                v = systems.get(name, 100)
                if v <= 0:
                    st.append((f"{pretty(name)} OFFLINE", RED))
                elif v < 25:
                    st.append((f"{pretty(name)} critical ({v:.0f}%)", RED))
                elif v < 60:
                    st.append((f"{pretty(name)} low ({v:.0f}%)", RED))
                elif v < 90:
                    st.append((f"{pretty(name)} degraded ({v:.0f}%)", AMBER))
            if d["rate_health"] > 0.001:
                st.append((f"Residents losing {d['rate_health']:.2f} health per sim-second", RED))
            dead = d["population"] - d["alive"]
            if dead > 0:
                st.append((f"{dead:,} residents dead", RED))
            d["systems"], d["statuses"] = systems, st
            self.state[lvl] = d

    def refresh(self):
        self.snapshot()
        total_alive = sum(d["alive"] for d in self.state.values())
        total_pop = sum(d["population"] for d in self.state.values())
        self.alive_lbl.config(text=f"Alive {total_alive:,} / {total_pop:,}")
        self.clock_lbl.config(text=format_clock(self.clock.sim_time))
        if self.clock.last_events:
            self.ticker = self.clock.last_events[-1]
        self.ticker_lbl.config(text=f"\u25b8 {self.ticker}")
        for lvl, d in self.state.items():
            it, c = self.items[lvl], self.canvas
            worst = min(d["systems"].values()) if d["systems"] else 100
            d["worst"] = worst
            wname = min(d["systems"], key=d["systems"].get) if d["systems"] else "-"
            c.itemconfig(it["pop"], text=f"Alive {d['alive']:,} / {d['population']:,}")
            c.itemconfig(it["worst"], text=f"Weakest: {pretty(wname)} {worst:.0f}%")
            n = len(d["statuses"])
            c.itemconfig(it["badge"], text=f"{n} alert{'s' if n != 1 else ''}" if n else "")
        if self.selected:
            if self.clock.ticks % 5 == 0:
                self._load_avg_health()
            self._update_panel()

    def _load_avg_health(self):
        r = self.con.execute("SELECT AVG(health) FROM residents WHERE level=? AND health>0",
                             (self.selected,)).fetchone()
        self.avg_health = r[0]

    # ------------------------------------------------------------- loops
    def loop(self):
        t = time.monotonic()
        self.clock.step()
        self.refresh()
        wait = max(10, int(TICK_SECONDS * 1000 - (time.monotonic() - t) * 1000))
        self.root.after(wait, self.loop)

    def animate(self):                         # smooth fade toward the target color
        for lvl, d in self.state.items():
            target = severity_color(d.get("worst", 100))
            cur = self.shown.get(lvl, target)
            cur = tuple(c + (t - c) * 0.08 for c, t in zip(cur, target))
            self.shown[lvl] = cur
            it, fg = self.items[lvl], text_on(cur)
            self.canvas.itemconfig(it["rect"], fill=hexc(cur))
            for k in ("title", "pop", "worst", "badge"):
                self.canvas.itemconfig(it[k], fill=fg)
        self.root.after(50, self.animate)

    # ------------------------------------------------------------- rows
    def _build_row(self, lvl):
        y = (lvl - 1) * (ROW_H + GAP)
        tag = f"row{lvl}"
        r = 16
        x1, y1, x2, y2 = 4, y + 2, LIST_W - 8, y + ROW_H
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2,
               x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        rect = self.canvas.create_polygon(pts, smooth=True, outline="", fill="#3484f0", tags=(tag,))
        mk = lambda x, yy, **kw: self.canvas.create_text(x, yy, tags=(tag,), **kw)
        self.items[lvl] = dict(
            rect=rect,
            title=mk(24, y + 26, anchor="w", text=f"LEVEL {lvl}", font=("Helvetica", 17, "bold")),
            pop=mk(24, y + 56, anchor="w", font=("Helvetica", 11)),
            worst=mk(24, y + 79, anchor="w", font=("Helvetica", 10)),
            badge=mk(LIST_W - 28, y + 26, anchor="e", font=("Helvetica", 12, "bold")))
        self.canvas.tag_bind(tag, "<Button-1>", lambda e, l=lvl: self.select(l))
        self.canvas.tag_bind(tag, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.config(cursor=""))

    def _wheel(self, e):
        up = e.num == 4 or getattr(e, "delta", 0) > 0
        self.canvas.yview_scroll(-2 if up else 2, "units")

    # ------------------------------------------------------------- panel
    def _build_panel(self):
        P = self.panel
        top = tk.Frame(P, bg=PANEL_BG)
        top.pack(fill="x", padx=16, pady=(14, 4))
        self.p_title = tk.Label(top, bg=PANEL_BG, fg="white", font=("Helvetica", 18, "bold"))
        self.p_title.pack(side="left")
        tk.Button(top, text="x", command=self.close_panel, bd=0, bg=PANEL_BG, fg=MUTED,
                  activebackground=PANEL_BG, font=("Helvetica", 14)).pack(side="right")
        self.p_pop = tk.Label(P, bg=PANEL_BG, fg=TEXT, font=("Helvetica", 12))
        self.p_pop.pack(anchor="w", padx=16)
        self.p_health = tk.Label(P, bg=PANEL_BG, fg=TEXT, font=("Helvetica", 12))
        self.p_health.pack(anchor="w", padx=16)

        self._section("SYSTEMS")
        self.bars = {}
        for name in self.systems:
            row = tk.Frame(P, bg=PANEL_BG)
            row.pack(fill="x", padx=16, pady=2)
            tk.Label(row, text=pretty(name), width=14, anchor="w", bg=PANEL_BG, fg=TEXT,
                     font=("Helvetica", 11)).pack(side="left")
            bar = tk.Canvas(row, width=140, height=14, bg="#2b2f3b", highlightthickness=0)
            bar.pack(side="left", padx=6)
            fill = bar.create_rectangle(0, 0, 0, 14, outline="")
            val = tk.Label(row, bg=PANEL_BG, fg=TEXT, font=("Helvetica", 11), width=5, anchor="w")
            val.pack(side="left")
            self.bars[name] = (bar, fill, val)

        self._section("NEGATIVE STATUSES")
        self.status_box = tk.Frame(P, bg=PANEL_BG)
        self.status_box.pack(fill="x", padx=16)

        self._section("RECENT LOG")
        self.log_lbl = tk.Label(P, bg=PANEL_BG, fg=MUTED, justify="left", anchor="w",
                                wraplength=PANEL_W - 32, font=("Helvetica", 10))
        self.log_lbl.pack(fill="x", padx=16)

        self._section("TRIGGER EVENT HERE")
        ctl = tk.Frame(P, bg=PANEL_BG)
        ctl.pack(fill="x", padx=16)
        self.ev_choice = tk.StringVar(value=EVENT_TYPES[0].name)
        tk.OptionMenu(ctl, self.ev_choice, *[e.name for e in EVENT_TYPES]).pack(side="left")
        tk.Button(ctl, text="Trigger", command=self.trigger).pack(side="left", padx=8)

    def _section(self, text):
        tk.Label(self.panel, text=text, bg=PANEL_BG, fg=MUTED,
                 font=("Helvetica", 10, "bold")).pack(anchor="w", padx=16, pady=(14, 2))

    def select(self, lvl):
        self.selected = lvl
        if not self.panel.winfo_ismapped():
            self.panel.pack(side="right", fill="y", padx=(0, 12), pady=10)
        self._load_avg_health()
        self._update_panel()

    def close_panel(self):
        self.selected = None
        self.panel.pack_forget()

    def trigger(self):
        if self.selected:
            self.clock.events.trigger(self.ev_choice.get(), self.selected, self.clock.sim_time)
            self.refresh()

    def _update_panel(self):
        d = self.state[self.selected]
        self.p_title.config(text=f"Level {self.selected}")
        self.p_pop.config(text=f"Population  {d['alive']:,} alive / {d['population']:,}")
        ah = f"{self.avg_health:.1f}" if self.avg_health is not None else "-"
        self.p_health.config(text=f"Avg health (living)  {ah}")
        for name, (bar, fill, val) in self.bars.items():
            v = d["systems"].get(name, 0)
            bar.coords(fill, 0, 0, 140 * v / 100, 14)
            bar.itemconfig(fill, fill=hexc(severity_color(v)))
            val.config(text=f"{v:.0f}%")
        for w in self.status_box.winfo_children():
            w.destroy()
        if d["statuses"]:
            for text, col in d["statuses"]:
                tk.Label(self.status_box, text="\u25cf " + text, bg=PANEL_BG, fg=col,
                         wraplength=PANEL_W - 40, justify="left",
                         font=("Helvetica", 11)).pack(anchor="w", pady=1)
        else:
            tk.Label(self.status_box, text="None - all clear", bg=PANEL_BG, fg="#6ee7a0",
                     font=("Helvetica", 11)).pack(anchor="w")
        rows = self.con.execute("SELECT sim_time, message FROM event_log WHERE level = ? "
                                "ORDER BY id DESC LIMIT 4", (self.selected,)).fetchall()
        self.log_lbl.config(text="\n".join(f"[{format_clock(r['sim_time'])}] {r['message']}"
                                           for r in rows) or "No events yet")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--residents", type=int, default=NUM_RESIDENTS)
    ap.add_argument("--speed", type=float, default=SIM_SECONDS_PER_TICK)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    root = tk.Tk()
    root.geometry("1000x680")
    loading = tk.Label(root, text=f"Building {args.residents:,} residents...", bg=BG, fg=TEXT,
                       font=("Helvetica", 14))
    loading.pack(expand=True, fill="both")
    root.update()
    db = build_database(n=args.residents)
    clock = HollowClock(db, sim_seconds_per_tick=args.speed, seed=args.seed)
    loading.destroy()
    HollowApp(root, db, clock)
    root.mainloop()
