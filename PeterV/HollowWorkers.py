"""
The Hollow: workers who walk between levels to help.

Three trades travel:
    engineers -> repair electricity, communication, housing, water (simulation.REPAIR_ORDER)
    farmers   -> make food
    medics    -> make medicine

Every worker has a home level. When one of a trade's systems on a level drops below HELP_BELOW
(a disaster), levels that are doing fine lend part of their crew. Nearest levels are asked first,
because walking takes TRAVEL_MINUTES_PER_LEVEL simulated minutes per level crossed:
    level 3 -> 4 = 1 level  = 15 sim minutes = 15 real seconds at the default speed
    level 2 -> 4 = 2 levels = 30 sim minutes = 30 real seconds
Once the level is back above HELPED_AT (or the crew's own level gets into trouble) they walk home.

PRIORITY LEVELS. The same top levels that have power outages diverted away from them
(HollowEvents.PROTECTED_FRACTION: levels 1-2 of 10) also come first for help:
    * they ask for help sooner (PRIORITY_HELP_BELOW) and ask for the full cap sooner
      (PRIORITY_FULL_HELP_AT)
    * they are served before every other level, whatever state the others are in
    * lending levels dig deeper for them (keep only PRIORITY_ENGINEER_KEEP of their engineers)
    * if that's still not enough, crews already helping lower levels are pulled off the job
      and sent up (like a power outage being diverted, in reverse)
    * crews working on a priority level stay until it's fixed, even if their own level calls

Scaling is the same for every trade, measured against that trade's own home crew size:
    * cap per level: engineers MAX_ENGINEERS_PER_LEVEL (500, vs ~120 at home = ~4.2x).
      Farmers and medics get the same multiple of their own average home crew.
    * how many a level asks for grows with how bad it is: nothing extra at its help threshold,
      the full cap at its full-help threshold or lower.
    * a lending level always keeps enough to run itself: half its engineers (a quarter when
      lending to a priority level), and enough farmers / medics to still break even on food /
      medicine for its own living residents.
    * crews smaller than MIN_CREW_FRACTION of a home crew are not worth sending.

Database side:
    residents.moving = 1     while walking: they count on no level, so they neither repair
                             nor produce (refresh_population skips them too)
    residents.level          changes when they ARRIVE, so they share the new level's dangers
    residents.away_from      their home level while they are away (NULL at home)
    levels.engineers/farmers/medics, levels.population/alive and level_jobs are updated on
    leave/arrive, so repair, supply and refresh_population never need a full recount.
Only the moving workers' rows are touched (hundreds of engineers, a few thousand farmers/medics).
"""

import math
from dataclasses import dataclass

from HollowEvents import PROTECTED_FRACTION
from Hpeople import (
    CONSUMPTION_PER_RESIDENT_PER_SIM_HOUR,
    ENGINEERS_PER_LEVEL,
    MAX_ENGINEERS_PER_LEVEL,
    PRODUCTION_PER_WORKER_PER_SIM_HOUR,
)

TRAVEL_MINUTES_PER_LEVEL = 15     # sim minutes to cross one level
DISPATCH_EVERY_TICKS = 5          # how often each trade looks for help / sends crews home
                                  # (trades are staggered onto different ticks to spread the cost)
HELP_BELOW = 80.0                 # a level asks for help when a trade's system is below this
FULL_HELP_AT = 40.0               # ...and asks for the full cap at or below this
PRIORITY_HELP_BELOW = 90.0        # priority (top) levels ask sooner...
PRIORITY_FULL_HELP_AT = 60.0      # ...and get the full cap sooner
HELPED_AT = 95.0                  # visitors go home once all of their trade's systems reach this
DONOR_MIN = 90.0                  # a level only lends workers if their systems are all >= this
MIN_CREW_FRACTION = 0.05          # smallest crew worth sending, as a share of a home crew
CAP_RATIO = MAX_ENGINEERS_PER_LEVEL / ENGINEERS_PER_LEVEL   # 500 / 120: same headroom for all trades
ENGINEER_KEEP = 0.5               # a lending level keeps at least half its own engineers
PRIORITY_ENGINEER_KEEP = 0.25     # ...but only a quarter when a priority level needs them
PRODUCER_KEEP_MARGIN = 1.05       # ...and enough farmers/medics to feed itself at break-even + 5%
_CHUNK = 900                      # ids per "IN (...)" (old SQLite builds allow only 999 params)


@dataclass(frozen=True)
class Trade:
    work: str          # residents.work
    column: str        # levels column with the cached count
    systems: tuple     # systems this trade looks after
    label: str


@dataclass
class Crew:
    trade: Trade
    ids: list          # resident ids (the living ones, as of the last move)
    home: int
    src: int           # level they are walking from (only meaningful while walking)
    dest: int          # level they are helping
    state: str         # "outbound", "on_site", "returning", "done"
    ticks_left: int = 0

    @property
    def size(self):
        return len(self.ids)

    @property
    def where(self):   # level the crew walks to next
        return self.dest if self.state == "outbound" else self.home


class Workforce:
    def __init__(self, con, sim_seconds_per_tick, repair_systems):
        self.con = con
        self.sim_per_tick = sim_seconds_per_tick
        self.trades = [
            Trade("engineer", "engineers", tuple(repair_systems), "engineers"),
            Trade("farmer", "farmers", ("food",), "farmers"),
            Trade("medic", "medics", ("medicine",), "medics"),
        ]
        self.crews = []
        self._ticks = 0
        rows = con.execute("SELECT level, engineers, farmers, medics FROM levels ORDER BY level").fetchall()
        self.levels = [r["level"] for r in rows]
        # same rule as HollowEvents: the top PROTECTED_FRACTION of levels (lowest numbers)
        self.protected = set(self.levels[:round(len(self.levels) * PROTECTED_FRACTION)])
        # home crew size per (trade, level), taken at the start
        self.home = {(t.work, r["level"]): r[t.column] for t in self.trades for r in rows}
        self.cap = {}
        for t in self.trades:
            if t.work == "engineer":
                self.cap[t.work] = MAX_ENGINEERS_PER_LEVEL
            else:
                avg = sum(self.home[(t.work, l)] for l in self.levels) / max(1, len(self.levels))
                self.cap[t.work] = math.ceil(avg * CAP_RATIO)

    # ---- public --------------------------------------------------------------
    def step(self, sim_time):
        """Advance walking crews by one tick; every DISPATCH_EVERY_TICKS send crews out / home.
        Returns a list of message strings."""
        self._ticks += 1
        msgs = []
        due = [t for i, t in enumerate(self.trades) if (self._ticks + i) % DISPATCH_EVERY_TICKS == 0]
        if not due and not self.crews:
            return msgs                                  # nothing walking, nothing to decide
        with self.con:
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

    def summary(self, level):
        """For the GUI: per-trade counts of workers coming to / visiting / away from `level`, plus
        one line per crew that involves it."""
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
                    lines.append(f"{c.size:,} {c.trade.label} walking home from level {c.src}"
                                 f" ({c.ticks_left}s)")
                else:
                    s["away"] += c.size
                    if c.state == "on_site":
                        lines.append(f"{c.size:,} of our {c.trade.label} helping level {c.dest}")
        return out, lines

    def has_incoming(self, level):
        return any(c.dest == level and c.state == "outbound" for c in self.crews)

    # ---- helpers -------------------------------------------------------------
    def _status(self):
        grid = {}
        for r in self.con.execute("SELECT level, system, status FROM level_systems"):
            grid.setdefault(r["level"], {})[r["system"]] = r["status"]
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
        """Workers a level must keep at home to run itself."""
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
        self.con.execute("INSERT INTO event_log (sim_time, level, system, message) VALUES (?,?,?,?)",
                         (sim_time, level, system, text))
        if msgs is not None:
            msgs.append(text)

    # ---- movement ------------------------------------------------------------
    def _advance(self, sim_time, msgs):
        for c in self.crews:
            if c.state in ("outbound", "returning"):
                c.ticks_left -= 1
                if c.ticks_left <= 0:
                    self._arrive(c, sim_time, msgs)

    def _arrive(self, c, sim_time, msgs):
        to, home_now = c.where, c.state == "returning"
        alive = 0
        clear = ", away_from = NULL" if home_now else ""
        for part, marks in self._chunks(c.ids):
            self.con.execute(f"UPDATE residents SET level = ?, moving = 0{clear} WHERE id IN ({marks})",
                             (to, *part))
            alive += self.con.execute(f"SELECT COUNT(*) FROM residents WHERE id IN ({marks}) AND health > 0",
                                      part).fetchone()[0]
        # the crew counted towards src's head counts until now; move them to the new level
        col, n = c.trade.column, len(c.ids)
        self.con.execute("UPDATE levels SET population = population - ?, alive = MAX(0, alive - ?) "
                         "WHERE level = ?", (n, alive, c.src))
        self.con.execute(f"UPDATE levels SET population = population + ?, alive = alive + ?, "
                         f"{col} = {col} + ? WHERE level = ?", (n, alive, alive, to))
        self.con.executemany("UPDATE level_jobs SET total = total + ? WHERE level = ? AND work = ?",
                             [(-n, c.src, c.trade.work), (n, to, c.trade.work)])
        self.con.execute("INSERT OR IGNORE INTO level_jobs (level, work, total) VALUES (?, ?, ?)",
                         (to, c.trade.work, n))
        # newcomers may be hurt: let flush_effects heal on this level again
        self.con.execute("UPDATE level_effects SET healed_to = 0 WHERE level = ?", (to,))
        sys0 = c.trade.systems[0]
        if home_now:
            c.state = "done"
            self._log(sim_time, to, sys0, f"{alive:,} {c.trade.label} back home on level {to} "
                                          f"after helping level {c.dest}", msgs)
        else:
            c.state = "on_site"
            self._log(sim_time, to, sys0, f"{alive:,} {c.trade.label} from level {c.home} "
                                          f"arrived on level {to}", msgs)

    def _leave(self, c, frm, fresh=False):
        """Start walking from `frm` towards c.where. Dead members stay behind. Returns False if
        nobody is left. fresh=True: a new crew whose ids were just picked alive (one UPDATE)."""
        if fresh:
            living = c.ids
            for part, marks in self._chunks(living):
                self.con.execute(f"UPDATE residents SET moving = 1, away_from = ? WHERE id IN ({marks})",
                                 (c.home, *part))
        else:
            living = []
            for part, marks in self._chunks(c.ids):
                living += [r[0] for r in self.con.execute(
                    f"SELECT id FROM residents WHERE id IN ({marks}) AND health > 0", part)]
            for part, marks in self._chunks(living):
                self.con.execute(f"UPDATE residents SET moving = 1 WHERE id IN ({marks})", part)
        c.ids = living
        if not living:
            c.state = "done"
            return False
        col = c.trade.column
        self.con.execute(f"UPDATE levels SET {col} = MAX(0, {col} - ?) WHERE level = ?", (len(living), frm))
        c.src = frm
        c.ticks_left = self.travel_ticks(frm, c.where)
        return True

    def _send_home(self, trade, status, sim_time, msgs):
        for c in self.crews:
            if c.state != "on_site" or c.trade is not trade:
                continue
            fixed = self._worst(trade, status, c.dest) >= HELPED_AT
            # crews on a priority level stay until it is fixed, even if their own level calls
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
        # (not priority, worst status, level): priority levels first, then the worst-off
        needy = []
        for lvl in self.levels:
            worst = self._worst(t, status, lvl)
            if worst < self._thresholds(lvl)[0]:
                needy.append((lvl not in self.protected, worst, lvl))
        if not needy:
            return
        needy.sort()
        counts = {r["level"]: r for r in self.con.execute(
            "SELECT level, alive, engineers, farmers, medics FROM levels")}
        # each healthy level's own crew at home (visitors aren't lent on)
        at_home = {l: counts[l][t.column] - self._crew_sum(t, l, "on_site")
                   for l in self.levels if self._worst(t, status, l) >= DONOR_MIN}
        for not_priority, worst, lvl in needy:
            priority = not not_priority
            help_below, full_at = self._thresholds(lvl)
            home, cap = self.home[(t.work, lvl)], self.cap[t.work]
            urgency = min(1.0, (help_below - worst) / (help_below - full_at))
            target = home + max(0, cap - home) * urgency
            have = counts[lvl][t.column] + self._crew_sum(t, lvl, "outbound")
            want = int(min(target, cap) - have)
            min_crew = max(1, math.ceil(home * MIN_CREW_FRACTION))
            spare = {d: n - self._keep(t, d, counts[d]["alive"], priority) for d, n in at_home.items()}
            for d in sorted(spare, key=lambda d: (abs(d - lvl), -spare[d])):   # nearest first
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
        ids = [r[0] for r in self.con.execute(
            "SELECT id FROM residents WHERE work = ? AND level = ? AND health > 0 "
            "AND moving = 0 AND away_from IS NULL LIMIT ?", (t.work, src, n))]
        if not ids:
            return 0
        c = Crew(t, ids, home=src, src=src, dest=dest, state="outbound")
        self._leave(c, src, fresh=True)
        self.crews.append(c)
        sys0 = t.systems[0]
        tag = "PRIORITY: " if dest in self.protected else ""
        self._log(sim_time, src, sys0, f"{tag}Sent {c.size:,} {t.label} to help level {dest}")
        self._log(sim_time, dest, sys0, f"{tag}{c.size:,} {t.label} from level {src} on the way "
                                        f"({c.ticks_left}s)", msgs)
        return c.size

    def _divert(self, t, lvl, want, min_crew, sim_time, msgs):
        """Pull crews off jobs on lower (non-priority) levels and send them to priority level
        `lvl`, nearest first. Big crews are split so only what's needed is taken."""
        pool = sorted((c for c in self.crews
                       if c.trade is t and c.state == "on_site" and c.dest not in self.protected),
                      key=lambda c: abs(c.dest - lvl))
        for c in pool:
            if want < min_crew:
                break
            frm = c.dest
            if c.size > want:                                # split: the rest keep working
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
