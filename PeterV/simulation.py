"""
The Hollow: world clock + slow system degradation.

Sits on top of the database module (hollow_db.py) and reuses its helpers:
    build_database, recompute_rates, tick, flush_effects,
    refresh_population, level_dashboard, SYSTEM_TYPES

Every real second (one "tick") this file:
  1. advances the simulated clock by SIM_SECONDS_PER_TICK
  2. wears every system on every level down by a small, never-zero amount
  3. recomputes the per-level damage rates   (~10 rows)
  4. accumulates damage in level_effects      (~10 rows)
  5. flushes that damage onto residents only when it's worth it
     (a timer, or a level has built up a lot of pending damage)

Residents are never touched on a normal tick.

Run it:   python hollow_clock.py
Quick demo:  python hollow_clock.py --residents 50000 --speed 1800 --ticks 60
"""

import argparse
import random
import time
from HollowEvents import EventManager

# NOTE: change "hollow_db" to whatever you named the database file (no .py).
# Importing is safe: that file's demo only runs under its own __main__ block.
from Hpeople import (
    NUM_RESIDENTS,
    SYSTEM_TYPES,
    build_database,
    flush_effects,
    level_dashboard,
    recompute_rates,
    refresh_population,
    tick,
)

# ------------------------------------------------------------------ tuning ----

TICK_SECONDS = 1.0            # real seconds between ticks
SIM_SECONDS_PER_TICK = 60.0   # 1 real second = 1 simulated minute (so 1 real minute = 1 sim hour)

# Status points (out of 100) each system loses per SIMULATED hour, before
# per-level variation and aging. At the defaults (1 sim hour per real minute)
# a ~1.0 system is down ~10 points after ~10 real minutes.
WEAR_PER_SIM_HOUR = {
    "oxygen":        0.6,
    "electricity":   1.2,
    "water":         0.9,
    "food":          1.0,
    "medicine":      1.4,
    "communication": 1.6,
    "housing":       0.5,
}
DEFAULT_WEAR = 1.0            # for any system type not listed above
WEAR_MULTIPLIER = 0.0         # new constant near the other tuning values

LEVEL_VARIATION = (0.6, 1.4)  # each (level, system) pair gets a fixed wear multiplier in this range
TICK_NOISE = 0.30             # each tick's wear is jittered by +/- 30%
AGING_PER_SIM_HOUR = 0.01     # wear speeds up 1% per sim hour: things fall apart a bit faster over time

# hollow_db's max_rate values are "health lost per second at status 0" and are
# tuned for short crises. Multiplying the time passed to tick() by this turns
# them into a slow burn. Raise it for a harsher world, lower it for a gentler one.
DAMAGE_SCALE = 0.5

# Flush policy: apply pending damage to residents when EITHER is true.
FLUSH_EVERY_TICKS = 15        # on a timer (flush_effects skips levels with < 1 whole point pending)
FLUSH_PENDING_LIMIT = 3.0     # or as soon as any level has this many health points pending
REFRESH_EVERY_TICKS = 30      # recount alive/population (the slowest query) this often

REPORT_EVERY_TICKS = 10       # how often the console prints a status line
LOG_THRESHOLDS = (75, 50, 25, 10)   # write an event_log row when a system drops below these


# ------------------------------------------------------------------- clock ----

def format_clock(sim_seconds):
    days, rem = divmod(int(sim_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return f"Day {days} {hours:02d}:{minutes:02d}:{secs:02d}"


class HollowClock:
    def __init__(self, con, sim_seconds_per_tick=SIM_SECONDS_PER_TICK, seed=None):
        self.con = con
        self.sim_per_tick = sim_seconds_per_tick
        self.sim_time = 0.0
        self.ticks = 0
        self.last_flush_ms = 0.0
        self._since_flush = 0
        self._since_refresh = 0
        self._rng = random.Random(seed)
        self.events = EventManager(con, self._rng)
        self.last_events = []

        names = [s[0] for s in SYSTEM_TYPES]
        levels = [r[0] for r in con.execute("SELECT level FROM levels")]
        self._wear_factor = {(lvl, name): self._rng.uniform(*LEVEL_VARIATION)
                             for lvl in levels for name in names}

    # One call = one tick. A GUI can call this from its own timer instead of run().
    def step(self):
        self.sim_time += self.sim_per_tick
        self.ticks += 1
        self._degrade()
        self.last_events = self.events.step(self.sim_time)  # new
        recompute_rates(self.con)
        tick(self.con, self.sim_per_tick * DAMAGE_SCALE)
        applied = self._maybe_flush()
        self._maybe_refresh()
        return applied

    def _degrade(self):
        """Wear every (level, system) down a little. Re-reads status each tick, so
        repairs made by other modules are respected."""
        aging = 1.0 + AGING_PER_SIM_HOUR * (self.sim_time / 3600.0)
        hours = self.sim_per_tick / 3600.0
        rows = self.con.execute("SELECT level, system, status FROM level_systems").fetchall()

        updates, events = [], []
        for r in rows:
            lvl, name, old = r["level"], r["system"], r["status"]
            wear = WEAR_PER_SIM_HOUR.get(name, DEFAULT_WEAR) * self._wear_factor.get((lvl, name), 1.0)
            noise = self._rng.uniform(1.0 - TICK_NOISE, 1.0 + TICK_NOISE)
            new = max(0.0, old - wear * aging * hours * noise * WEAR_MULTIPLIER)
            if new == old:
                continue
            updates.append((new, lvl, name))
            for t in LOG_THRESHOLDS:
                if old >= t > new:
                    events.append((self.sim_time, lvl, name, f"{name} fell below {t}%"))

        with self.con:
            self.con.executemany(
                "UPDATE level_systems SET status = ? WHERE level = ? AND system = ?", updates)
            if events:
                self.con.executemany(
                    "INSERT INTO event_log (sim_time, level, system, message) VALUES (?,?,?,?)", events)

    def _maybe_flush(self):
        self._since_flush += 1
        worst = self.con.execute("SELECT MAX(pending_health) FROM level_effects").fetchone()[0] or 0.0
        if self._since_flush < FLUSH_EVERY_TICKS and worst < FLUSH_PENDING_LIMIT:
            return {}
        self._since_flush = 0
        t = time.perf_counter()
        applied = flush_effects(self.con)
        self.last_flush_ms = (time.perf_counter() - t) * 1000
        return applied

    def _maybe_refresh(self):
        self._since_refresh += 1
        if self._since_refresh >= REFRESH_EVERY_TICKS:
            self._since_refresh = 0
            refresh_population(self.con)

    def run(self, max_ticks=None, on_tick=None):
        """Blocking loop, one tick per TICK_SECONDS of wall time with no drift.
        If a flush runs long the loop catches up with back-to-back ticks."""
        start = time.monotonic()
        n = 0
        try:
            while max_ticks is None or n < max_ticks:
                applied = self.step()
                n += 1
                if on_tick:
                    on_tick(self, applied)
                delay = start + n * TICK_SECONDS - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        except KeyboardInterrupt:
            print("\nStopping...")
        flush_effects(self.con)
        refresh_population(self.con)


# --------------------------------------------------------------- reporting ----

def console_report(clock, applied):
    if applied:
        per_level = ", ".join(f"L{lvl} -{dh}hp" for lvl, (dh, _dm) in sorted(applied.items()))
        print(f"  flush ({clock.last_flush_ms:.0f} ms): {per_level}")

    if clock.ticks % REPORT_EVERY_TICKS:
        return
    dash = level_dashboard(clock.con)
    alive = sum(r["alive"] for r in dash)
    pop = sum(r["population"] for r in dash)
    worst = min(dash, key=lambda r: r["worst_status"])
    avg = clock.con.execute("SELECT AVG(status) FROM level_systems").fetchone()[0]
    print(f"[{format_clock(clock.sim_time)}] alive {alive:,}/{pop:,} | "
          f"avg system {avg:5.1f}% | "
          f"worst: L{worst['level']} {worst['worst_system']} {worst['worst_status']:.1f}%")

    #print events as they happen
    for m in clock.last_events:
        print(f"  !! {m}")

# -------------------------------------------------------------------- main ----

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run the Hollow world clock.")
    ap.add_argument("--residents", type=int, default=NUM_RESIDENTS)
    ap.add_argument("--ticks", type=int, default=None, help="stop after N ticks (default: run until Ctrl+C)")
    ap.add_argument("--speed", type=float, default=SIM_SECONDS_PER_TICK,
                    help="simulated seconds per real second")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    db = build_database(n=args.residents)
    print(f"Built {args.residents:,} residents in {time.time() - t0:.1f}s. Ctrl+C to stop.\n")

    clock = HollowClock(db, sim_seconds_per_tick=args.speed, seed=args.seed)
    clock.run(max_ticks=args.ticks, on_tick=console_report)

    print("\nFinal state:")
    for r in level_dashboard(db):
        print(dict(r))
