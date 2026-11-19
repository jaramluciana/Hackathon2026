"""
The Hollow: random disaster events.

Lifecycle of one event:
  scheduled -> (WARNING_TICKS later) fires -> instant drops applied
            -> optional drain each tick for `duration` ticks -> ends

Only level_systems.status is changed. hollow_db's recompute_rates/tick turn
low status into health damage, so residents are never touched here.
"""

import random
from dataclasses import dataclass, field

WARNING_TICKS = 30          # ticks (real seconds) between "incoming" and impact
SPAWN_GAP = (20, 60)        # random ticks between new events
MAX_ACTIVE = 4             # cap on events scheduled or running at once


@dataclass(frozen=True)
class EventType:
    name: str
    message: str                                   # {level} is filled in
    drops: dict = field(default_factory=dict)      # system -> status points lost instantly
    drain: dict = field(default_factory=dict)      # system -> points lost PER TICK while active
    duration: int = 0                              # ticks the drain lasts
    weight: int = 1                                # higher = more common


EVENT_TYPES = [
    EventType("power_outage", "Power outage on level {level}",
              drops={"electricity": 50, "communication": 15}, weight=3),
    EventType("air_quality", "Air quality critical on level {level}: lung disease spreading, people eating more",
              drops={"oxygen": 20, "medicine": 10},
              drain={"food": 0.15}, duration=120, weight=2),
    EventType("oxygen_leak", "Oxygen levels dropping on level {level}",
              drops={"oxygen": 40},
              drain={"oxygen": 0.10}, duration=60, weight=2),
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
    def __init__(self, con, rng=None):
        self.con = con
        self.rng = rng or random.Random()
        self.levels = [r[0] for r in con.execute("SELECT level FROM levels")]
        self.pending = []     # [ticks_left, EventType, level]
        self.active = []      # [ticks_left, EventType, level]
        self._next_spawn = self.rng.randint(*SPAWN_GAP)

    # ---- public --------------------------------------------------------------
    def step(self, sim_time):
        """Advance events by one tick. Returns a list of message strings
        (handy for console/GUI)."""
        msgs = []
        with self.con:
            self._maybe_spawn(sim_time, msgs)
            self._advance_pending(sim_time, msgs)
            self._advance_active(sim_time, msgs)
        return msgs

    def trigger(self, name, level, sim_time=0.0):
        """Force an event now (for demos / testing)."""
        et = next(e for e in EVENT_TYPES if e.name == name)
        msgs = []
        with self.con:
            self._fire(et, level, sim_time, msgs)
        return msgs

    # ---- internals -----------------------------------------------------------
    def _log(self, sim_time, level, system, text, msgs):
        self.con.execute(
            "INSERT INTO event_log (sim_time, level, system, message) VALUES (?,?,?,?)",
            (sim_time, level, system, text))
        msgs.append(text)

    def _change(self, level, system, delta):
        self.con.execute(
            "UPDATE level_systems SET status = MIN(100, MAX(0, status + ?)) "
            "WHERE level = ? AND system = ?", (delta, level, system))

    def _maybe_spawn(self, sim_time, msgs):
        self._next_spawn -= 1
        if self._next_spawn > 0 or len(self.pending) + len(self.active) >= MAX_ACTIVE:
            return
        self._next_spawn = self.rng.randint(*SPAWN_GAP)
        et = self.rng.choices(EVENT_TYPES, weights=[e.weight for e in EVENT_TYPES])[0]
        level = self.rng.choice(self.levels)
        self.pending.append([WARNING_TICKS, et, level])
        first_system = next(iter(et.drops))
        self._log(sim_time, level, first_system,
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
        self._log(sim_time, level, next(iter(et.drops)), et.message.format(level=level), msgs)
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
