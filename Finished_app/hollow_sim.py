"""The Hollow simulation on SQL Server (port of Hpeople / simulation / HollowEvents /
HollowWorkers).

Runs in ONE background thread, one tick per real second. All database work happens in that
thread; the UI only receives plain-dict snapshots through `sim.listener`.

Each tick:
  events -> workers walk / get sent -> engineers repair -> food & medicine supply
  -> recompute rates -> accumulate damage -> flush damage onto residents (staggered)
Residents are never touched on a normal tick.
"""
import math
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
SIM_SECONDS_PER_TICK = 60.0       # 1 real second = 1 simulated minute
DAMAGE_SCALE = 0.5

# passive wear (0 = off, only events break things)
WEAR_PER_SIM_HOUR = {"oxygen": 0.6, "electricity": 1.2, "water": 0.9, "food": 1.0,
                     "medicine": 1.4, "communication": 1.6, "housing": 0.5}
DEFAULT_WEAR = 1.0
WEAR_MULTIPLIER = 0.0
LEVEL_VARIATION = (0.6, 1.4)
TICK_NOISE = 0.30
AGING_PER_SIM_HOUR = 0.01
LOG_THRESHOLDS = (75, 50, 25, 10)

# engineers repair these systems one at a time, in this order
REPAIR_ORDER = ("electricity", "communication", "housing", "water")
ENGINEER_REPAIR_PER_SIM_HOUR = {s: 0.08 for s in REPAIR_ORDER}

FLUSH_EVERY_TICKS = 15
FLUSH_PENDING_LIMIT = 3.0
REFRESH_EVERY_TICKS = 30

# ---- food & medicine supply (same numbers as Hpeople.py) ----
WORKS = ["farmer", "medic", "miner", "technician", "teacher", "guard", "scavenger"]
WORK_WEIGHTS = [30, 8, 20, 10, 8, 4, 15]
ENGINEERS_PER_LEVEL = 120
MAX_ENGINEERS_PER_LEVEL = 500
CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR = {"food": 1.0, "medicine": 1.0}
SELF_SUFFICIENCY = {"food": 1.5, "medicine": 1.5}
PRODUCER_COLUMN = {"food": "Farmers", "medicine": "Medics"}
PRODUCER_WORK = {"food": "farmer", "medicine": "medic"}


def _job_share(work):
    return WORK_WEIGHTS[WORKS.index(work)] / sum(WORK_WEIGHTS)


PRODUCTION_PER_WORKER_PER_SIM_HOUR = {
    s: CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR[s] / _job_share(w) * SELF_SUFFICIENCY[s]
    for s, w in PRODUCER_WORK.items()}

# ---- events ----
WARNING_TICKS = 30
SPAWN_GAP = (20, 60)
MAX_ACTIVE = 4
PROTECTED_FRACTION = 0.30         # top levels (lowest numbers) are shielded and served first

# ---- workers (same numbers as HollowWorkers.py) ----
TRAVEL_MINUTES_PER_LEVEL = 15
DISPATCH_EVERY_TICKS = 5
HELP_BELOW = 80.0
FULL_HELP_AT = 40.0
PRIORITY_HELP_BELOW = 90.0
PRIORITY_FULL_HELP_AT = 60.0
HELPED_AT = 95.0
DONOR_MIN = 90.0
MIN_CREW_FRACTION = 0.05
CAP_RATIO = MAX_ENGINEERS_PER_LEVEL / ENGINEERS_PER_LEVEL
ENGINEER_KEEP = 0.5
PRIORITY_ENGINEER_KEEP = 0.25
PRODUCER_KEEP_MARGIN = 1.05
_CHUNK = 900                      # ids per IN (...) (SQL Server allows 2100 parameters)

RED = "#ff7b72"
AMBER = "#f2c94c"
HELP = "#7cc4ff"


# ------------------------------------------------------------------ helpers
def format_clock(sim_seconds):
    days, rem = divmod(int(sim_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return f"Day {days} {hours:02d}:{minutes:02d}:{secs:02d}"


def pretty(s):
    return s.replace("_", " ").title()


def compact(n):
    return f"{n / 1000:.1f}k" if n >= 10_000 else f"{n:,}"


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
    redirect: bool = False          # True = never hits a protected top level
    lung_disease: float = 0.0       # fraction of living residents infected


EVENT_TYPES = [
    EventType("power_outage", "Power outage on level {level}",
              drops={"electricity": 50, "communication": 15}, weight=3, redirect=True),
    EventType("air_quality",
              "Air quality critical on level {level}: lung disease spreading, people eating more",
              drops={"oxygen": 20, "medicine": 10}, drain={"food": 0.15},
              duration=120, weight=2, lung_disease=0.4),
    EventType("oxygen_leak", "Oxygen levels dropping on level {level}",
              drops={"oxygen": 40}, drain={"oxygen": 0.10}, duration=60, weight=2),
    EventType("water_main_burst", "Water main burst on level {level}",
              drops={"water": 45}, weight=2),
    EventType("crop_blight", "Crop blight on level {level}",
              drops={"food": 35}, drain={"food": 0.05}, duration=90, weight=2),
    EventType("outbreak", "Disease outbreak on level {level}",
              drops={"medicine": 30}, drain={"medicine": 0.10}, duration=90, weight=1),
    EventType("housing_collapse", "Structural collapse on level {level}",
              drops={"housing": 40, "electricity": 15}, weight=1),
]


class EventManager:
    def __init__(self, cur, levels, rng):
        self.cur = cur
        self.rng = rng
        self.levels = sorted(levels)
        n_protected = round(len(self.levels) * PROTECTED_FRACTION)
        self.protected = set(self.levels[:n_protected])
        self.safe_levels = [l for l in self.levels if l not in self.protected]
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
        level = self._redirect(et, level, sim_time, msgs)
        self._fire(et, level, sim_time, msgs)
        return msgs

    def _log(self, sim_time, level, system, text, msgs):
        self.cur.execute(
            "INSERT INTO Event_Log (Sim_Time, [Level], System, Message) VALUES (?, ?, ?, ?)",
            sim_time, level, system, text)
        msgs.append(text)

    def _change(self, level, system, delta):
        self.cur.execute(
            "UPDATE Level_Systems SET [Status] = "
            "IIF([Status] + ? > 100, 100, IIF([Status] + ? < 0, 0, [Status] + ?)) "
            "WHERE [Level] = ? AND System = ?",
            delta, delta, delta, level, system)

    def _redirect(self, et, level, sim_time, msgs):
        """Divert redirectable events (power outages) off protected top levels."""
        if et.redirect and level in self.protected and self.safe_levels:
            new = self.rng.choice(self.safe_levels)
            self._log(sim_time, level, next(iter(et.drops)),
                      f"Protected level {level}: {et.name} diverted to level {new}", msgs)
            return new
        return level

    def _maybe_spawn(self, sim_time, msgs):
        self._next_spawn -= 1
        if self._next_spawn > 0 or len(self.pending) + len(self.active) >= MAX_ACTIVE:
            return
        self._next_spawn = self.rng.randint(*SPAWN_GAP)
        et = self.rng.choices(EVENT_TYPES, weights=[e.weight for e in EVENT_TYPES])[0]
        level = self._redirect(et, self.rng.choice(self.levels), sim_time, msgs)
        self.pending.append([WARNING_TICKS, et, level])
        self._log(sim_time, level, next(iter(et.drops)),
                  f"WARNING: {et.name} expected on level {level} in {WARNING_TICKS}s", msgs)

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
        if et.lung_disease:
            # infected residents can't heal (see usp_FlushEffects)
            n = self.cur.execute(
                "UPDATE Residents SET LungDisease = 1 "
                "WHERE [Level] = ? AND Health > 0 AND LungDisease = 0 "
                "AND ABS(CAST(CHECKSUM(NEWID()) AS BIGINT)) % 1000 < ?",
                level, int(et.lung_disease * 1000)).rowcount
            self._log(sim_time, level, "oxygen",
                      f"{n:,} residents on level {level} developed lung disease", msgs)
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


# ------------------------------------------------------------------ workers
@dataclass(frozen=True)
class Trade:
    work: str          # Residents.Work
    column: str        # Levels column with the cached count
    systems: tuple
    label: str


@dataclass
class Crew:
    trade: Trade
    ids: list
    home: int
    src: int
    dest: int
    state: str         # outbound / on_site / returning / done
    ticks_left: int = 0

    @property
    def size(self):
        return len(self.ids)

    @property
    def where(self):
        return self.dest if self.state == "outbound" else self.home


# column positions in: SELECT [Level], Alive, Engineers, Farmers, Medics FROM Levels
_COL = {"Engineers": 2, "Farmers": 3, "Medics": 4}


class Workforce:
    """Engineers, farmers and medics walk between levels to help (see HollowWorkers.py)."""

    def __init__(self, cur, sim_seconds_per_tick, repair_systems):
        self.cur = cur
        self.sim_per_tick = sim_seconds_per_tick
        self.trades = [
            Trade("engineer", "Engineers", tuple(repair_systems), "engineers"),
            Trade("farmer", "Farmers", ("food",), "farmers"),
            Trade("medic", "Medics", ("medicine",), "medics"),
        ]
        self.crews = []
        self._ticks = 0
        rows = cur.execute("SELECT [Level], Alive, Engineers, Farmers, Medics "
                           "FROM Levels ORDER BY [Level]").fetchall()
        self.levels = [r[0] for r in rows]
        self.protected = set(self.levels[:round(len(self.levels) * PROTECTED_FRACTION)])
        self.home = {(t.work, r[0]): r[_COL[t.column]] for t in self.trades for r in rows}
        self.cap = {}
        for t in self.trades:
            if t.work == "engineer":
                self.cap[t.work] = MAX_ENGINEERS_PER_LEVEL
            else:
                avg = sum(self.home[(t.work, l)] for l in self.levels) / max(1, len(self.levels))
                self.cap[t.work] = math.ceil(avg * CAP_RATIO)

    # ---- public ----
    def step(self, sim_time):
        self._ticks += 1
        msgs = []
        due = [t for i, t in enumerate(self.trades)
               if (self._ticks + i) % DISPATCH_EVERY_TICKS == 0]
        if not due and not self.crews:
            return msgs
        self._advance(sim_time, msgs)
        if due:
            status = self._status()
            for t in due:
                self._send_home(t, status, sim_time, msgs)
                self._dispatch(t, status, sim_time, msgs)
        self.crews = [c for c in self.crews if c.state != "done"]
        return msgs

    def travel_ticks(self, a, b):
        sim_seconds = abs(a - b) * TRAVEL_MINUTES_PER_LEVEL * 60
        return max(1, math.ceil(sim_seconds / self.sim_per_tick))

    def is_priority(self, level):
        return level in self.protected

    def has_incoming(self, level):
        return any(c.dest == level and c.state == "outbound" for c in self.crews)

    def summary(self, level):
        out = {t.work: {"label": t.label, "incoming": 0, "visiting": 0, "away": 0, "returning": 0}
               for t in self.trades}
        lines = []
        for c in self.crews:
            s = out[c.trade.work]
            if c.dest == level and c.state == "outbound":
                s["incoming"] += c.size
                lines.append(f"{c.size:,} {c.trade.label} from level {c.src} arrive in {c.ticks_left}s")
            elif c.dest == level and c.state == "on_site":
                s["visiting"] += c.size
                lines.append(f"{c.size:,} {c.trade.label} from level {c.home} helping here")
            if c.home == level:
                if c.state == "returning":
                    s["returning"] += c.size
                    lines.append(f"{c.size:,} {c.trade.label} walking home from level {c.src} ({c.ticks_left}s)")
                else:
                    s["away"] += c.size
                    if c.state == "on_site":
                        lines.append(f"{c.size:,} of our {c.trade.label} helping level {c.dest}")
        return out, lines

    def recall_all(self):
        """Send every walking / visiting worker straight home (used when the simulation
        starts or stops, so nobody stays stranded)."""
        self.cur.execute("UPDATE Residents SET [Level] = AwayFrom WHERE AwayFrom IS NOT NULL")
        self.cur.execute("UPDATE Residents SET Moving = 0, AwayFrom = NULL "
                         "WHERE Moving = 1 OR AwayFrom IS NOT NULL")
        self.crews = []

    # ---- helpers ----
    def _status(self):
        grid = {}
        for lvl, system, st in self.cur.execute(
                "SELECT [Level], System, [Status] FROM Level_Systems").fetchall():
            grid.setdefault(lvl, {})[system] = float(st)
        return grid

    @staticmethod
    def _worst(trade, status, level):
        return min(status.get(level, {}).get(s, 100.0) for s in trade.systems)

    def _thresholds(self, level):
        if level in self.protected:
            return PRIORITY_HELP_BELOW, PRIORITY_FULL_HELP_AT
        return HELP_BELOW, FULL_HELP_AT

    def _crew_sum(self, trade, level, state):
        return sum(c.size for c in self.crews
                   if c.trade is trade and c.dest == level and c.state == state)

    def _keep(self, trade, level, alive, priority):
        if trade.work == "engineer":
            share = PRIORITY_ENGINEER_KEEP if priority else ENGINEER_KEEP
            return math.ceil(self.home[(trade.work, level)] * share)
        system = trade.systems[0]
        need = alive * CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR[system] / PRODUCTION_PER_WORKER_PER_SIM_HOUR[system]
        return math.ceil(need * PRODUCER_KEEP_MARGIN)

    @staticmethod
    def _chunks(ids):
        for i in range(0, len(ids), _CHUNK):
            part = ids[i:i + _CHUNK]
            yield part, ",".join("?" * len(part))

    def _log(self, sim_time, level, system, text, msgs=None):
        self.cur.execute(
            "INSERT INTO Event_Log (Sim_Time, [Level], System, Message) VALUES (?, ?, ?, ?)",
            sim_time, level, system, text)
        if msgs is not None:
            msgs.append(text)

    # ---- movement ----
    def _advance(self, sim_time, msgs):
        for c in self.crews:
            if c.state in ("outbound", "returning"):
                c.ticks_left -= 1
                if c.ticks_left <= 0:
                    self._arrive(c, sim_time, msgs)

    def _arrive(self, c, sim_time, msgs):
        to, home_now = c.where, c.state == "returning"
        alive = 0
        clear = ", AwayFrom = NULL" if home_now else ""
        for part, marks in self._chunks(c.ids):
            self.cur.execute(
                f"UPDATE Residents SET [Level] = ?, Moving = 0{clear} WHERE ID IN ({marks})",
                (to, *part))
            alive += self.cur.execute(
                f"SELECT COUNT(*) FROM Residents WHERE ID IN ({marks}) AND Health > 0",
                part).fetchone()[0]
        col, n = c.trade.column, len(c.ids)
        self.cur.execute(
            "UPDATE Levels SET Population = Population - ?, "
            "Alive = IIF(Alive - ? < 0, 0, Alive - ?) WHERE [Level] = ?",
            n, alive, alive, c.src)
        self.cur.execute(
            f"UPDATE Levels SET Population = Population + ?, Alive = Alive + ?, "
            f"{col} = {col} + ? WHERE [Level] = ?", n, alive, alive, to)
        # newcomers may be hurt: let the flush heal on this level again
        self.cur.execute("UPDATE Level_Effects SET Healed_To = 0 WHERE [Level] = ?", to)
        sys0 = c.trade.systems[0]
        if home_now:
            c.state = "done"
            self._log(sim_time, to, sys0,
                      f"{alive:,} {c.trade.label} back home on level {to} after helping level {c.dest}", msgs)
        else:
            c.state = "on_site"
            self._log(sim_time, to, sys0,
                      f"{alive:,} {c.trade.label} from level {c.home} arrived on level {to}", msgs)

    def _leave(self, c, frm, fresh=False):
        """Start walking from `frm` towards c.where. Dead members stay behind."""
        if fresh:
            living = c.ids
            for part, marks in self._chunks(living):
                self.cur.execute(
                    f"UPDATE Residents SET Moving = 1, AwayFrom = ? WHERE ID IN ({marks})",
                    (c.home, *part))
        else:
            living = []
            for part, marks in self._chunks(c.ids):
                living += [r[0] for r in self.cur.execute(
                    f"SELECT ID FROM Residents WHERE ID IN ({marks}) AND Health > 0", part).fetchall()]
            for part, marks in self._chunks(living):
                self.cur.execute(f"UPDATE Residents SET Moving = 1 WHERE ID IN ({marks})", part)
        c.ids = living
        if not living:
            c.state = "done"
            return False
        col = c.trade.column
        self.cur.execute(
            f"UPDATE Levels SET {col} = IIF({col} - ? < 0, 0, {col} - ?) WHERE [Level] = ?",
            len(living), len(living), frm)
        c.src = frm
        c.ticks_left = self.travel_ticks(frm, c.where)
        return True

    def _send_home(self, trade, status, sim_time, msgs):
        for c in self.crews:
            if c.state != "on_site" or c.trade is not trade:
                continue
            fixed = self._worst(trade, status, c.dest) >= HELPED_AT
            needed_home = (c.dest not in self.protected
                           and self._worst(trade, status, c.home) < self._thresholds(c.home)[0])
            if not (fixed or needed_home):
                continue
            c.state = "returning"
            if self._leave(c, c.dest):
                why = "job done" if fixed else "their own level needs them"
                self._log(sim_time, c.dest, trade.systems[0],
                          f"{c.size:,} {trade.label} leaving level {c.dest} for level {c.home} "
                          f"({why}, {c.ticks_left}s)", msgs)

    def _dispatch(self, t, status, sim_time, msgs):
        needy = []
        for lvl in self.levels:
            worst = self._worst(t, status, lvl)
            if worst < self._thresholds(lvl)[0]:
                needy.append((lvl not in self.protected, worst, lvl))
        if not needy:
            return
        needy.sort()
        counts = {r[0]: r for r in self.cur.execute(
            "SELECT [Level], Alive, Engineers, Farmers, Medics FROM Levels").fetchall()}
        idx = _COL[t.column]
        at_home = {l: counts[l][idx] - self._crew_sum(t, l, "on_site")
                   for l in self.levels if self._worst(t, status, l) >= DONOR_MIN}
        for not_priority, worst, lvl in needy:
            priority = not not_priority
            help_below, full_at = self._thresholds(lvl)
            home, cap = self.home[(t.work, lvl)], self.cap[t.work]
            urgency = min(1.0, (help_below - worst) / (help_below - full_at))
            target = home + max(0, cap - home) * urgency
            have = counts[lvl][idx] + self._crew_sum(t, lvl, "outbound")
            want = int(min(target, cap) - have)
            min_crew = max(1, math.ceil(home * MIN_CREW_FRACTION))
            spare = {d: n - self._keep(t, d, counts[d][1], priority) for d, n in at_home.items()}
            for d in sorted(spare, key=lambda d: (abs(d - lvl), -spare[d])):
                if want < min_crew:
                    break
                n = min(spare[d], want)
                if n < min_crew:
                    continue
                sent = self._send(t, d, lvl, n, sim_time, msgs)
                at_home[d] -= sent
                want -= sent
            if priority and want >= min_crew:
                self._divert(t, lvl, want, min_crew, sim_time, msgs)

    def _send(self, t, src, dest, n, sim_time, msgs):
        # residents that belong to a login account are never sent away
        ids = [r[0] for r in self.cur.execute(
            "SELECT TOP (?) ID FROM Residents "
            "WHERE Work = ? AND [Level] = ? AND Health > 0 AND Moving = 0 AND AwayFrom IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM Account a WHERE a.ResidentID = Residents.ID)",
            n, t.work, src).fetchall()]
        if not ids:
            return 0
        c = Crew(t, ids, home=src, src=src, dest=dest, state="outbound")
        self._leave(c, src, fresh=True)
        self.crews.append(c)
        sys0 = t.systems[0]
        tag = "PRIORITY: " if dest in self.protected else ""
        self._log(sim_time, src, sys0, f"{tag}Sent {c.size:,} {t.label} to help level {dest}")
        self._log(sim_time, dest, sys0,
                  f"{tag}{c.size:,} {t.label} from level {src} on the way ({c.ticks_left}s)", msgs)
        return c.size

    def _divert(self, t, lvl, want, min_crew, sim_time, msgs):
        """Pull crews off jobs on lower levels and send them to priority level `lvl`."""
        pool = sorted((c for c in self.crews
                       if c.trade is t and c.state == "on_site" and c.dest not in self.protected),
                      key=lambda c: abs(c.dest - lvl))
        for c in pool:
            if want < min_crew:
                break
            frm = c.dest
            if c.size > want:
                moved = Crew(t, c.ids[:want], home=c.home, src=frm, dest=lvl, state="outbound")
                c.ids = c.ids[want:]
                self.crews.append(moved)
            else:
                moved, c.dest, c.state = c, lvl, "outbound"
            if not self._leave(moved, frm):
                continue
            want -= moved.size
            self._log(sim_time, frm, t.systems[0],
                      f"PRIORITY: {moved.size:,} {t.label} pulled off level {frm} for level {lvl}")
            self._log(sim_time, lvl, t.systems[0],
                      f"PRIORITY: {moved.size:,} {t.label} diverted from level {frm} "
                      f"({moved.ticks_left}s)", msgs)


# ------------------------------------------------------------------ simulation
class HollowSim:
    """Background simulation. stop() returns immediately; the thread cleans up by itself."""

    def __init__(self):
        self.listener = None
        self.selected = None
        self.last_snapshot = None
        self._thread = None
        self._stop = threading.Event()
        self._cmds = queue.Queue()

    # ---- control (UI thread) ----
    def start(self):
        if self._thread and self._thread.is_alive() and not self._stop.is_set():
            return
        previous = self._thread
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, args=(self._stop, previous), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.listener = None
        self.last_snapshot = None

    def trigger(self, name, level):
        self._cmds.put((name, level))

    # ---- thread ----
    def _run(self, stop, previous):
        if previous and previous.is_alive():
            previous.join()          # wait here, in the background, never in the UI thread
        if stop.is_set():
            return
        try:
            conn = database.get_connection()
        except Exception as ex:
            print("Simulation cannot connect:", ex)
            return
        cur = conn.cursor()

        try:
            # start from a clean state: nobody stranded from an earlier run
            cur.execute("UPDATE Residents SET [Level] = AwayFrom WHERE AwayFrom IS NOT NULL")
            cur.execute("UPDATE Residents SET Moving = 0, AwayFrom = NULL "
                        "WHERE Moving = 1 OR AwayFrom IS NOT NULL")
            cur.execute("EXEC dbo.usp_RefreshPopulation")
            conn.commit()
        except Exception as ex:
            print("Simulation setup error:", ex)

        self.sim_time = 0.0
        self.ticks = 0
        self.ticker = "Simulation running"
        self._since_refresh = 0
        self._avg = None
        self._avg_for = None
        self._rng = random.Random()
        levels = [r[0] for r in cur.execute("SELECT [Level] FROM Levels").fetchall()]
        self._levels = sorted(levels)
        self.events = EventManager(cur, levels, self._rng)
        self.workforce = Workforce(cur, SIM_SECONDS_PER_TICK, REPAIR_ORDER)
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

        # bring walking workers home so levels are consistent while nothing is running
        try:
            conn.rollback()
            self.workforce.recall_all()
            cur.execute("EXEC dbo.usp_RefreshPopulation")
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
        msgs += self.workforce.step(self.sim_time)
        if msgs:
            self.ticker = msgs[-1]
        self._repair(cur)
        self._supply(cur)

        cur.execute("EXEC dbo.usp_RecomputeRates")
        cur.execute("EXEC dbo.usp_Tick ?", SIM_SECONDS_PER_TICK * DAMAGE_SCALE)
        conn.commit()

        self._maybe_flush(conn, cur)
        self._since_refresh += 1
        if self._since_refresh >= REFRESH_EVERY_TICKS:
            self._since_refresh = 0
            cur.execute("EXEC dbo.usp_RefreshPopulation")
            conn.commit()

        cb = self.listener
        if cb is None:
            return      # nobody is watching: skip the snapshot queries
        snap = self._snapshot(cur)
        conn.commit()
        self.last_snapshot = snap
        try:
            cb(snap)
        except Exception as ex:
            print("Listener error:", ex)

    # ---- systems ----
    def _degrade(self, cur):
        if WEAR_MULTIPLIER <= 0:
            return
        aging = 1.0 + AGING_PER_SIM_HOUR * (self.sim_time / 3600.0)
        hours = SIM_SECONDS_PER_TICK / 3600.0
        updates, logs = [], []
        for lvl, name, old in cur.execute(
                "SELECT [Level], System, [Status] FROM Level_Systems").fetchall():
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
            cur.executemany("UPDATE Level_Systems SET [Status] = ? "
                            "WHERE [Level] = ? AND System = ?", updates)
        if logs:
            cur.executemany("INSERT INTO Event_Log (Sim_Time, [Level], System, Message) "
                            "VALUES (?, ?, ?, ?)", logs)

    def _repair(self, cur):
        """Engineers bring damaged systems back up, one system at a time per level."""
        hours = SIM_SECONDS_PER_TICK / 3600.0
        engineers = {r[0]: r[1] for r in cur.execute("SELECT [Level], Engineers FROM Levels").fetchall()}
        marks = ",".join("?" * len(REPAIR_ORDER))
        grid = {}
        for lvl, system, st in cur.execute(
                f"SELECT [Level], System, [Status] FROM Level_Systems WHERE System IN ({marks})",
                REPAIR_ORDER).fetchall():
            grid.setdefault(lvl, {})[system] = float(st)
        updates = []
        for lvl, n in engineers.items():
            if n <= 0:
                continue
            for name in REPAIR_ORDER:
                status = grid.get(lvl, {}).get(name)
                if status is None or status >= 100:
                    continue
                gain = n * ENGINEER_REPAIR_PER_SIM_HOUR.get(name, 0.0) * hours
                updates.append((min(100.0, status + gain), lvl, name))
                break
        if updates:
            cur.executemany("UPDATE Level_Systems SET [Status] = ? "
                            "WHERE [Level] = ? AND System = ?", updates)

    def _supply(self, cur):
        """Food and medicine: residents use them, farmers / medics make more."""
        hours = SIM_SECONDS_PER_TICK / 3600.0
        updates = []
        rows = cur.execute(
            "SELECT s.[Level], s.System, s.Capacity, ls.[Status], l.Alive, l.Farmers, l.Medics "
            "FROM Level_Supply s "
            "JOIN Level_Systems ls ON ls.[Level] = s.[Level] AND ls.System = s.System "
            "JOIN Levels l ON l.[Level] = s.[Level]").fetchall()
        for lvl, system, capacity, status, alive, farmers, medics in rows:
            if capacity <= 0:
                continue
            workers = farmers if system == "food" else medics
            used = alive * CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR[system]
            made = workers * PRODUCTION_PER_WORKER_PER_SIM_HOUR[system]
            status = float(status)
            new = max(0.0, min(100.0, status + 100.0 * (made - used) * hours / capacity))
            if new != status:
                updates.append((new, lvl, system))
        if updates:
            cur.executemany("UPDATE Level_Systems SET [Status] = ? "
                            "WHERE [Level] = ? AND System = ?", updates)

    def _maybe_flush(self, conn, cur):
        """Staggered: each level is flushed once every FLUSH_EVERY_TICKS ticks, on different
        ticks, so the cost is spread out. A level with lots of pending damage goes at once."""
        due = [lvl for i, lvl in enumerate(self._levels)
               if (self.ticks + i) % FLUSH_EVERY_TICKS == 0]
        urgent = [r[0] for r in cur.execute(
            "SELECT [Level] FROM Level_Effects WHERE Pending_Health >= ?",
            FLUSH_PENDING_LIMIT).fetchall()]
        for lvl in sorted(set(due) | set(urgent)):
            cur.execute("EXEC dbo.usp_FlushEffects ?", lvl)
            cur.fetchall()
            conn.commit()

    # ---- snapshot for the UI ----
    def _snapshot(self, cur):
        levels = {}
        for lvl, pop, alive, eng, farm, med in cur.execute(
                "SELECT [Level], Population, Alive, Engineers, Farmers, Medics "
                "FROM Levels ORDER BY [Level]").fetchall():
            levels[lvl] = dict(pop=pop or 0, alive=alive or 0, eng=eng or 0,
                               farm=farm or 0, med=med or 0, systems={})
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
            dead = d["pop"] - d["alive"]
            if dead > 0:
                st.append((f"{dead:,} residents dead", RED))
            d["statuses"] = st
            d["wname"] = min(d["systems"], key=d["systems"].get) if d["systems"] else "-"
            d["worst"] = d["systems"][d["wname"]] if d["systems"] else 100
            d["priority"] = self.workforce.is_priority(lvl)
            d["help"] = self.workforce.has_incoming(lvl)

        snap = dict(
            clock=format_clock(self.sim_time),
            ticker=self.ticker,
            alive=sum(d["alive"] for d in levels.values()),
            pop=sum(d["pop"] for d in levels.values()),
            levels=levels, avg_health=None, log=[], workforce=None,
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
                "SELECT TOP 3 Sim_Time, Message FROM Event_Log "
                "WHERE [Level] = ? ORDER BY ID DESC", sel).fetchall()
            snap["log"] = [f"[{format_clock(r[0])}] {r[1]}" for r in rows]
            snap["workforce"] = self.workforce.summary(sel)
        return snap


# one shared simulation for the whole app
sim = HollowSim()