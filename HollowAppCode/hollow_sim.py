import queue
import random
import threading
import time
from dataclasses import dataclass, field
import database

# ------------------------------------------------------------------ tuning
SYSTEMS = ["oxygen", "electricity", "water", "food",
           "medicine", "communication", "housing"]

TICK_SECONDS = 1.0
SIM_SECONDS_PER_TICK = 60.0

WEAR_PER_SIM_HOUR = {
    "oxygen": 0.6, "electricity": 1.2, "water": 0.9, "food": 1.0,
    "medicine": 1.4, "communication": 1.6, "housing": 0.5,
}
DEFAULT_WEAR = 1.0
WEAR_MULTIPLIER = 0.0      # as in your simulation.py: 0 = no slow wear, only events
LEVEL_VARIATION = (0.6, 1.4)
TICK_NOISE = 0.30
AGING_PER_SIM_HOUR = 0.01
DAMAGE_SCALE = 0.5

FLUSH_EVERY_TICKS = 15
FLUSH_PENDING_LIMIT = 3.0
REFRESH_EVERY_TICKS = 30
LOG_THRESHOLDS = (75, 50, 25, 10)

WARNING_TICKS = 30
SPAWN_GAP = (20, 60)
MAX_ACTIVE = 4

RED = "#ff7b72"
AMBER = "#f2c94c"


# ------------------------------------------------------------------ helpers
def format_clock(sim_seconds):
    days, rem = divmod(int(sim_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return f"Day {days} {hours:02d}:{minutes:02d}:{secs:02d}"


def pretty(s):
    return s.replace("_", " ").title()


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
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return "#111111" if lum > 150 else "#ffffff"


# ------------------------------------------------------------------ events
@dataclass(frozen=True)
class EventType:
    name: str
    message: str
    drops: dict = field(default_factory=dict)
    drain: dict = field(default_factory=dict)
    duration: int = 0
    weight: int = 1


EVENT_TYPES = [
    EventType("power_outage", "Power outage on level {level}",
              drops={"electricity": 50, "communication": 15}, weight=3),
    EventType("air_quality",
              "Air quality critical on level {level}: lung disease spreading, people eating more",
              drops={"oxygen": 20, "medicine": 10},
              drain={"food": 0.15}, duration=120, weight=2),
    EventType("oxygen_leak", "Oxygen levels dropping on level {level}",
              drops={"oxygen": 40}, drain={"oxygen": 0.10},
              duration=60, weight=2),
    EventType("water_main_burst", "Water main burst on level {level}",
              drops={"water": 45}, weight=2),
    EventType("crop_blight", "Crop blight on level {level}",
              drops={"food": 35}, drain={"food": 0.05},
              duration=90, weight=2),
    EventType("outbreak", "Disease outbreak on level {level}",
              drops={"medicine": 30}, drain={"medicine": 0.10},
              duration=90, weight=1),
    EventType("housing_collapse", "Structural collapse on level {level}",
              drops={"housing": 40, "electricity": 15}, weight=1),
]


class EventManager:
    def __init__(self, cur, levels, rng):
        self.cur = cur
        self.rng = rng
        self.levels = levels
        self.pending = []      # [ticks_left, EventType, level]
        self.active = []
        self._next_spawn = rng.randint(*SPAWN_GAP)

    def step(self, sim_time):
        msgs = []
        self._maybe_spawn(sim_time, msgs)
        self._advance_pending(sim_time, msgs)
        self._advance_active(sim_time, msgs)
        return msgs

    def trigger(self, name, level, sim_time):
        et = next(e for e in EVENT_TYPES if e.name == name)
        msgs = []
        self._fire(et, level, sim_time, msgs)
        return msgs

    def _log(self, sim_time, level, system, text, msgs):
        self.cur.execute(
            "INSERT INTO Event_Log (Sim_Time, [Level], System, Message) "
            "VALUES (?, ?, ?, ?)", (sim_time, level, system, text))
        msgs.append(text)

    def _change(self, level, system, delta):
        self.cur.execute(
            "UPDATE Level_Systems SET [Status] = "
            "IIF([Status] + ? > 100, 100, IIF([Status] + ? < 0, 0, [Status] + ?)) "
            "WHERE [Level] = ? AND System = ?",
            (delta, delta, delta, level, system))

    def _maybe_spawn(self, sim_time, msgs):
        self._next_spawn -= 1
        if self._next_spawn > 0 or len(self.pending) + len(self.active) >= MAX_ACTIVE:
            return
        self._next_spawn = self.rng.randint(*SPAWN_GAP)
        et = self.rng.choices(EVENT_TYPES, weights=[e.weight for e in EVENT_TYPES])[0]
        level = self.rng.choice(self.levels)
        self.pending.append([WARNING_TICKS, et, level])
        self._log(sim_time, level, next(iter(et.drops)),
                  f"WARNING: {et.name} expected on level {level} in {WARNING_TICKS}s",
                  msgs)

    def _advance_pending(self, sim_time, msgs):
        still = []
        for left, et, level in self.pending:
            left -= 1
            if left <= 0:
                self._fire(et, level, sim_time, msgs)
            else:
                still.append([left, et, level])
        self.pending = still

    def _fire(self, et, level, sim_time, msgs):
        for system, points in et.drops.items():
            self._change(level, system, -points)
        self._log(sim_time, level, next(iter(et.drops)),
                  et.message.format(level=level), msgs)
        if et.duration:
            self.active.append([et.duration, et, level])

    def _advance_active(self, sim_time, msgs):
        still = []
        for left, et, level in self.active:
            for system, per_tick in et.drain.items():
                self._change(level, system, -per_tick)
            left -= 1
            if left <= 0:
                self._log(sim_time, level, next(iter(et.drops)),
                          f"{et.name} on level {level} has subsided", msgs)
            else:
                still.append([left, et, level])
        self.active = still


# ------------------------------------------------------------------ simulation
class HollowSim:
    """Runs the world in a background thread. All database work happens in
    that thread; the UI only receives plain-dict snapshots via `listener`."""

    def __init__(self):
        self.listener = None        # callback(snapshot) set by the UI
        self.selected = None        # level shown in the detail panel
        self.last_snapshot = None
        self._thread = None
        self._stop = threading.Event()
        self._cmds = queue.Queue()

    # ---- control (called from the UI thread) ----
    def start(self):
        if self._thread and self._thread.is_alive() and not self._stop.is_set():
            return
        previous = self._thread
        self._stop = threading.Event()          # a fresh flag for every run
        self._thread = threading.Thread(
            target=self._run, args=(self._stop, previous), daemon=True)
        self._thread.start()

    def stop(self):
        """Returns immediately. The thread finishes its current tick and exits."""
        self._stop.set()
        self.listener = None
        self.last_snapshot = None

    def trigger(self, name, level):
        self._cmds.put((name, level))

    # ---- thread ----
    def _run(self, stop, previous):
        # If the previous run is still finishing its last tick, wait for it
        # HERE (in the background), never in the UI thread.
        if previous and previous.is_alive():
            previous.join()
        if stop.is_set():
            return

        try:
            conn = database.get_connection()
        except Exception as ex:
            print("Simulation cannot connect:", ex)
            return
        cur = conn.cursor()

        self.sim_time = 0.0
        self.ticks = 0
        self.ticker = "Simulation running"
        self._since_flush = 0
        self._since_refresh = 0
        self._avg = None
        self._avg_for = None
        self._rng = random.Random()
        levels = [r[0] for r in cur.execute("SELECT [Level] FROM Levels").fetchall()]
        self.events = EventManager(cur, levels, self._rng)
        self._wear = {(lvl, s): self._rng.uniform(*LEVEL_VARIATION)
                      for lvl in levels for s in SYSTEMS}

        start = time.monotonic()
        n = 0
        while not stop.is_set():
            try:
                self._step(conn, cur)
            except Exception as ex:
                print("Simulation error:", ex)
                self.ticker = f"Database error: {ex}"
                try:
                    conn.rollback()
                except Exception:
                    pass
            n += 1
            delay = start + n * TICK_SECONDS - time.monotonic()
            if delay > 0:
                stop.wait(delay)

        # No final flush: pending damage stays in Level_Effects for next time
        try:
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _step(self, conn, cur):
        while not self._cmds.empty():
            name, level = self._cmds.get_nowait()
            msgs = self.events.trigger(name, level, self.sim_time)
            if msgs:
                self.ticker = msgs[-1]

        self.sim_time += SIM_SECONDS_PER_TICK
        self.ticks += 1

        self._degrade(cur)
        msgs = self.events.step(self.sim_time)
        if msgs:
            self.ticker = msgs[-1]

        cur.execute("EXEC dbo.usp_RecomputeRates")
        cur.execute("EXEC dbo.usp_Tick ?", SIM_SECONDS_PER_TICK * DAMAGE_SCALE)
        conn.commit()

        self._maybe_flush(conn, cur)
        self._since_refresh += 1
        if self._since_refresh >= REFRESH_EVERY_TICKS:
            self._since_refresh = 0
            cur.execute("EXEC dbo.usp_RefreshPopulation")
            conn.commit()

        snap = self._snapshot(cur)
        conn.commit()
        self.last_snapshot = snap
        cb = self.listener
        if cb:
            try:
                cb(snap)
            except Exception as ex:
                print("Listener error:", ex)

    def _degrade(self, cur):
        aging = 1.0 + AGING_PER_SIM_HOUR * (self.sim_time / 3600.0)
        hours = SIM_SECONDS_PER_TICK / 3600.0
        rows = cur.execute(
            "SELECT [Level], System, [Status] FROM Level_Systems").fetchall()
        updates, logs = [], []
        for lvl, name, old in rows:
            old = float(old)
            wear = WEAR_PER_SIM_HOUR.get(name, DEFAULT_WEAR) * self._wear.get((lvl, name), 1.0)
            noise = self._rng.uniform(1 - TICK_NOISE, 1 + TICK_NOISE)
            new = max(0.0, old - wear * aging * hours * noise * WEAR_MULTIPLIER)
            if new == old:
                continue
            updates.append((new, lvl, name))
            for t in LOG_THRESHOLDS:
                if old >= t > new:
                    logs.append((self.sim_time, lvl, name, f"{name} fell below {t}%"))
        if updates:
            cur.executemany(
                "UPDATE Level_Systems SET [Status] = ? "
                "WHERE [Level] = ? AND System = ?", updates)
        if logs:
            cur.executemany(
                "INSERT INTO Event_Log (Sim_Time, [Level], System, Message) "
                "VALUES (?, ?, ?, ?)", logs)

    def _maybe_flush(self, conn, cur):
        self._since_flush += 1
        worst = cur.execute(
            "SELECT MAX(Pending_Health) FROM Level_Effects").fetchone()[0] or 0.0
        if self._since_flush < FLUSH_EVERY_TICKS and worst < FLUSH_PENDING_LIMIT:
            return
        self._since_flush = 0
        self._flush(conn, cur)

    def _flush(self, conn, cur):
        cur.execute("EXEC dbo.usp_FlushEffects")
        cur.fetchall()
        conn.commit()

    def _snapshot(self, cur):
        levels = {}
        for lvl, pop, alive in cur.execute(
                "SELECT [Level], Population, Alive FROM Levels "
                "ORDER BY [Level]").fetchall():
            levels[lvl] = dict(pop=pop, alive=alive, systems={})
        for lvl, system, status in cur.execute(
                "SELECT [Level], System, [Status] FROM Level_Systems").fetchall():
            levels[lvl]["systems"][system] = float(status)
        rates = {r[0]: float(r[1]) for r in cur.execute(
            "SELECT [Level], Rate_Health FROM Level_Effects").fetchall()}

        for lvl, d in levels.items():
            st = []
            for left, et, l in self.events.pending:
                if l == lvl:
                    st.append((f"Incoming: {pretty(et.name)} in {left}s", AMBER))
            for left, et, l in self.events.active:
                if l == lvl:
                    st.append((f"Ongoing: {pretty(et.name)} ({left}s left)", RED))
            for name in SYSTEMS:
                v = d["systems"].get(name, 100)
                if v <= 0:
                    st.append((f"{pretty(name)} OFFLINE", RED))
                elif v < 25:
                    st.append((f"{pretty(name)} critical ({v:.0f}%)", RED))
                elif v < 60:
                    st.append((f"{pretty(name)} low ({v:.0f}%)", RED))
                elif v < 90:
                    st.append((f"{pretty(name)} degraded ({v:.0f}%)", AMBER))
            if rates.get(lvl, 0) > 0.001:
                st.append((f"Residents losing {rates[lvl]:.2f} health per sim-second", RED))
            dead = (d["pop"] or 0) - (d["alive"] or 0)
            if dead > 0:
                st.append((f"{dead:,} residents dead", RED))
            d["statuses"] = st
            d["wname"] = min(d["systems"], key=d["systems"].get) if d["systems"] else "-"
            d["worst"] = d["systems"][d["wname"]] if d["systems"] else 100

        snap = dict(
            clock=format_clock(self.sim_time),
            ticker=self.ticker,
            alive=sum(d["alive"] or 0 for d in levels.values()),
            pop=sum(d["pop"] or 0 for d in levels.values()),
            levels=levels, avg_health=None, log=[],
        )

        sel = self.selected
        if sel in levels:
            if self.ticks % 5 == 0 or self._avg_for != sel:
                self._avg = cur.execute(
                    "SELECT AVG(CAST(Health AS FLOAT)) FROM Residents "
                    "WHERE [Level] = ? AND Health > 0", sel).fetchone()[0]
                self._avg_for = sel
            snap["avg_health"] = self._avg
            rows = cur.execute(
                "SELECT TOP 4 Sim_Time, Message FROM Event_Log "
                "WHERE [Level] = ? ORDER BY ID DESC", sel).fetchall()
            snap["log"] = [f"[{format_clock(r[0])}] {r[1]}" for r in rows]
        return snap


# one shared simulation for the whole app
sim = HollowSim()